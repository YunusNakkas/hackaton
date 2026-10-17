"""S0 spike: Gemma 4 + Transformers (MPS) üzerinde ASR, müşteri cevabı ve değerlendirme ölçümü.

Kullanım (model-service venv'i ile, repo kökünden):
  PYTORCH_ENABLE_MPS_FALLBACK=1 model-service/.venv/bin/python eval/s0/spike_transformers.py \
      --model google/gemma-4-E2B-it

Önce: eval/s0/make_samples.sh
Çıktı: var/s0-results/<model>-transformers.json
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import time
from pathlib import Path

import psutil
import torch
from transformers import AutoModelForMultimodalLM, AutoProcessor
from transformers import __version__ as transformers_version

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data/audio_test_manifest/s0_synthetic_tr.json"
AUDIO_DIR = ROOT / "var/s0-audio"
OUT_DIR = ROOT / "var/s0-results"

# Model kartındaki resmî ASR prompt'u, Türkçe için uyarlanmış.
ASR_PROMPT = (
    "Transcribe the following speech segment in Turkish into Turkish text. "
    "Follow these specific instructions for formatting the answer:\n"
    "* Only output the transcription, with no newlines.\n"
    "* When transcribing numbers, write the digits, i.e. write 1.7 and not one point seven, "
    "and write 3 instead of three."
)

CUSTOMER_SYSTEM = (
    "Sen bir mağazada iade yapmak isteyen müşteri Ayşe Hanım'sın. Üç hafta önce bir mont aldın, "
    "fişin yok ama kart ekstren telefonunda. Biraz sinirlisin ama kaba değilsin. Hediye çeki "
    "istemiyorsun, paranı kartına geri istiyorsun. Yalnızca müşteri olarak, kısa ve doğal Türkçe "
    "konuş (en fazla 2 cümle). Asla mağaza çalışanı gibi konuşma."
)
CUSTOMER_HISTORY = [
    {"role": "assistant", "content": "Merhaba, bu montu iade etmek istiyorum ama fişim yok."},
    {"role": "user", "content": "Merhaba, yardımcı olayım. Ödemeyi nasıl yapmıştınız?"},
    {"role": "assistant", "content": "Kartla ödemiştim, ekstrem telefonumda var."},
    {"role": "user", "content": "Kartla ödenen alışverişlerde kayıt bulunursa iadeyi kartınıza yapabiliyoruz."},
]

EVAL_PROMPT = """Aşağıdaki müşteri hizmetleri görüşmesini çalışan açısından değerlendir.

Politika P1 (Fişsiz iade): Kartlı ödemede POS kaydı bulunursa iade karta yapılır, 3 iş günü içinde yansır.

Transkript:
[t1] customer: Merhaba, bu montu iade etmek istiyorum ama fişim yok.
[t2] employee: Merhaba, yardımcı olayım. Ödemeyi nasıl yapmıştınız?
[t3] customer: Kartla ödemiştim, ekstrem telefonumda var.
[t4] employee: Kartla ödenen alışverişlerde kayıt bulunursa iadeyi kartınıza yapabiliyoruz.
[t5] customer: Peki ne kadar sürer?
[t6] employee: Bilmiyorum, muhasebe bakıyor.

Boyutlar: empathy, policy_accuracy, solution, clarity. Her boyuta 0-4 tam sayı puan ver; kanıt yetersizse null.
Kanıt olarak yalnızca transkriptten BİREBİR alıntı yap ve tur kimliğini ver.
YALNIZCA şu JSON'u döndür, başka metin yazma:
{"dimensions":[{"dimension_id":"...","score":0,"rationale":"...","evidence":[{"turn_id":"t2","quote":"..."}],"policy_refs":["P1"]}],"strengths":["..."],"improvements":["..."]}"""

SAMPLING = {"do_sample": True, "temperature": 1.0, "top_p": 0.95, "top_k": 64}


def normalize(text: str) -> list[str]:
    text = text.replace("I", "ı").replace("İ", "i").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return text.split()


def edit_distance(a: list, b: list) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def mem_gb() -> dict:
    out = {"rss_gb": round(psutil.Process().memory_info().rss / 1e9, 2)}
    if torch.backends.mps.is_available():
        out["mps_driver_gb"] = round(torch.mps.driver_allocated_memory() / 1e9, 2)
    out["system_available_gb"] = round(psutil.virtual_memory().available / 1e9, 2)
    return out


def generate(model, processor, messages, max_new_tokens, sampling=None) -> tuple[str, float, int]:
    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
        add_generation_prompt=True,
        enable_thinking=False,
    ).to(model.device)
    input_len = inputs["input_ids"].shape[-1]
    kwargs = sampling or {"do_sample": False}
    t0 = time.perf_counter()
    with torch.inference_mode():
        out = model.generate(**inputs, max_new_tokens=max_new_tokens, **kwargs)
    if torch.backends.mps.is_available():
        torch.mps.synchronize()
    elapsed = time.perf_counter() - t0
    new_tokens = out.shape[-1] - input_len
    text = processor.decode(out[0][input_len:], skip_special_tokens=True).strip()
    return text, elapsed, int(new_tokens)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="google/gemma-4-E2B-it")
    ap.add_argument("--reply-runs", type=int, default=5)
    ap.add_argument("--eval-runs", type=int, default=3)
    args = ap.parse_args()

    result: dict = {
        "model": args.model,
        "runtime": "transformers",
        "device": "mps" if torch.backends.mps.is_available() else "cpu",
        "env": {
            "machine": platform.machine(),
            "macos": platform.mac_ver()[0],
            "total_ram_gb": round(psutil.virtual_memory().total / 1e9, 1),
            "torch": torch.__version__,
            "transformers": transformers_version,
        },
        "audio_set": "s0_synthetic_tr (macOS Yelda TTS, 16 kHz)",
    }
    print("başlangıç bellek", mem_gb(), flush=True)

    t0 = time.perf_counter()
    processor = AutoProcessor.from_pretrained(args.model)
    # device_map="auto" bellek az görünürse katmanları diske taşıyor ve MPS'te "meta device"
    # hatası veriyor; birleşik bellekte tüm modeli doğrudan cihaza yüklüyoruz.
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = AutoModelForMultimodalLM.from_pretrained(args.model, dtype="auto", device_map=device)
    result["load_s"] = round(time.perf_counter() - t0, 1)
    result["dtype"] = str(next(model.parameters()).dtype)
    result["mem_after_load"] = mem_gb()
    print(f"yükleme {result['load_s']} sn, {result['dtype']}, {result['mem_after_load']}", flush=True)

    # ---- ASR
    items = json.loads(MANIFEST.read_text(encoding="utf-8"))["items"]
    asr_rows, total_err, total_ref, total_cerr, total_cref = [], 0, 0, 0, 0
    for i, it in enumerate(items):
        wav = AUDIO_DIR / f"{it['id']}.wav"
        messages = [{"role": "user", "content": [
            {"type": "text", "text": ASR_PROMPT},
            {"type": "audio", "audio": str(wav)},
        ]}]
        hyp, secs, _ = generate(model, processor, messages, max_new_tokens=128)
        ref_w, hyp_w = normalize(it["text"]), normalize(hyp)
        werr = edit_distance(ref_w, hyp_w)
        ref_c, hyp_c = list(" ".join(ref_w)), list(" ".join(hyp_w))
        cerr = edit_distance(ref_c, hyp_c)
        total_err, total_ref = total_err + werr, total_ref + len(ref_w)
        total_cerr, total_cref = total_cerr + cerr, total_cref + len(ref_c)
        row = {"id": it["id"], "ref": it["text"], "hyp": hyp, "wer": round(werr / len(ref_w), 3),
               "seconds": round(secs, 2), "warmup": i == 0}
        asr_rows.append(row)
        print(f"ASR {it['id']} {row['seconds']}s wer={row['wer']} | {hyp}", flush=True)
    timed = [r["seconds"] for r in asr_rows if not r["warmup"]]
    result["asr"] = {
        "wer": round(total_err / total_ref, 3),
        "cer": round(total_cerr / total_cref, 3),
        "median_s": sorted(timed)[len(timed) // 2],
        "max_s": max(timed),
        "rows": asr_rows,
    }
    result["mem_after_asr"] = mem_gb()

    # ---- müşteri cevabı
    reply_rows = []
    messages = [{"role": "system", "content": CUSTOMER_SYSTEM}, *CUSTOMER_HISTORY]
    for _ in range(args.reply_runs):
        text, secs, ntok = generate(model, processor, messages, max_new_tokens=80, sampling=SAMPLING)
        reply_rows.append({"text": text, "seconds": round(secs, 2), "tokens": ntok,
                           "tok_per_s": round(ntok / secs, 1)})
        print(f"CEVAP {secs:.2f}s {ntok} tok | {text}", flush=True)
    result["customer_reply"] = {
        "median_s": sorted(r["seconds"] for r in reply_rows)[len(reply_rows) // 2],
        "median_tok_per_s": sorted(r["tok_per_s"] for r in reply_rows)[len(reply_rows) // 2],
        "rows": reply_rows,
    }

    # ---- değerlendirme (tek çağrı, JSON)
    eval_rows = []
    for _ in range(args.eval_runs):
        text, secs, ntok = generate(model, processor, [{"role": "user", "content": EVAL_PROMPT}],
                                    max_new_tokens=900, sampling=SAMPLING)
        raw = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
        try:
            parsed = json.loads(raw)
            dims = {d.get("dimension_id"): d.get("score") for d in parsed.get("dimensions", [])}
            ok = set(dims) == {"empathy", "policy_accuracy", "solution", "clarity"}
        except json.JSONDecodeError:
            parsed, dims, ok = None, {}, False
        eval_rows.append({"seconds": round(secs, 2), "tokens": ntok, "json_ok": parsed is not None,
                          "all_dimensions": ok, "scores": dims, "raw": text})
        print(f"DEĞERLENDİRME {secs:.2f}s {ntok} tok json={parsed is not None} boyutlar={ok} {dims}", flush=True)
    result["evaluation"] = {
        "json_ok_rate": sum(r["json_ok"] for r in eval_rows) / len(eval_rows),
        "median_s": sorted(r["seconds"] for r in eval_rows)[len(eval_rows) // 2],
        "rows": eval_rows,
    }
    result["mem_peak_end"] = mem_gb()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.model.split('/')[-1]}-transformers.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nÖZET", json.dumps({k: result[k] for k in ("load_s", "dtype", "mem_after_load")}, ensure_ascii=False))
    print(f"ASR wer={result['asr']['wer']} cer={result['asr']['cer']} medyan={result['asr']['median_s']}s")
    print(f"cevap medyan={result['customer_reply']['median_s']}s {result['customer_reply']['median_tok_per_s']} tok/s")
    print(f"değerlendirme medyan={result['evaluation']['median_s']}s json_ok={result['evaluation']['json_ok_rate']}")
    print("kaydedildi:", out)


if __name__ == "__main__":
    main()

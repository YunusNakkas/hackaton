"""Çalışan model servisini HTTP üzerinden ölçer; runtime'dan bağımsız (transformers, mlx, ...).

Kullanım (model servisi localhost:8100'de çalışırken, repo kökünden):
  model-service/.venv-mlx/bin/python eval/s0/spike_service.py --label mlx-e4b-4bit

Ölçülenler: ASR doğruluğu/süresi, boşta beklemeden sonraki ilk çağrı (swap belirtisi),
müşteri cevabı, değerlendirme JSON'u, servis süreç belleği ve swap.
Çıktı: var/s0-results/<label>.json
"""

import argparse
import base64
import json
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

import httpx
import psutil

sys.path.insert(0, str(Path(__file__).parent))
from common import (  # noqa: E402
    ASR_PROMPT,
    CUSTOMER_HISTORY,
    CUSTOMER_SYSTEM,
    EVAL_PROMPT,
    edit_distance,
    normalize,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data/audio_test_manifest/s0_synthetic_tr.json"
AUDIO_DIR = ROOT / "var/s0-audio"
OUT_DIR = ROOT / "var/s0-results"
URL = "http://localhost:8100"
SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 64}


def service_proc() -> psutil.Process | None:
    for p in psutil.process_iter(["cmdline"]):
        cmd = " ".join(p.info.get("cmdline") or [])
        if "uvicorn" in cmd and "8100" in cmd:
            return p
    return None


def mem(proc: psutil.Process | None) -> dict:
    swap = subprocess.run(["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True).stdout
    used = re.search(r"used = ([\d,.]+)M", swap)
    return {
        "service_rss_gb": round(proc.memory_info().rss / 1e9, 2) if proc else None,
        "system_available_gb": round(psutil.virtual_memory().available / 1e9, 2),
        "swap_used_gb": round(float(used.group(1).replace(",", ".")) / 1024, 2) if used else None,
    }


def gen(client: httpx.Client, messages, max_new_tokens, sampling=None, priority=0) -> tuple[dict, float]:
    t0 = time.perf_counter()
    r = client.post("/v1/generate", json={"messages": messages, "max_new_tokens": max_new_tokens,
                                          "sampling": sampling, "priority": priority})
    r.raise_for_status()
    return r.json(), time.perf_counter() - t0


def asr_messages(wav: Path) -> list:
    return [{"role": "user", "content": [
        {"type": "text", "text": ASR_PROMPT},
        {"type": "audio", "audio_b64": base64.b64encode(wav.read_bytes()).decode()},
    ]}]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--idle-s", type=float, default=20.0, help="çalışanın konuşma süresini taklit eden bekleme")
    ap.add_argument("--idle-runs", type=int, default=5)
    args = ap.parse_args()

    client = httpx.Client(base_url=URL, timeout=300)
    health = client.get("/v1/health").json()
    proc = service_proc()
    result: dict = {"label": args.label, "health": health, "machine": platform.machine(),
                    "mem_start": mem(proc)}
    print("servis:", health, result["mem_start"], flush=True)

    items = json.loads(MANIFEST.read_text(encoding="utf-8"))["items"]
    rows, err, ref, cerr, cref = [], 0, 0, 0, 0
    for it in items:
        out, secs = gen(client, asr_messages(AUDIO_DIR / f"{it['id']}.wav"), 128)
        r_w, h_w = normalize(it["text"]), normalize(out["text"])
        e = edit_distance(r_w, h_w)
        rc, hc = list(" ".join(r_w)), list(" ".join(h_w))
        ce = edit_distance(rc, hc)
        err, ref, cerr, cref = err + e, ref + len(r_w), cerr + ce, cref + len(rc)
        rows.append({"id": it["id"], "ref": it["text"], "hyp": out["text"], "wer": round(e / len(r_w), 3),
                     "seconds": round(secs, 2)})
        print(f"ASR {it['id']} {secs:5.2f}s wer={rows[-1]['wer']:.2f} | {out['text']}", flush=True)
    times = sorted(r["seconds"] for r in rows)
    result["asr"] = {"wer": round(err / ref, 3), "cer": round(cerr / cref, 3),
                     "median_s": times[len(times) // 2], "max_s": times[-1], "rows": rows}

    idle = []
    for i in range(args.idle_runs):
        time.sleep(args.idle_s)
        _, secs = gen(client, asr_messages(AUDIO_DIR / f"{items[i]['id']}.wav"), 128)
        idle.append({"seconds": round(secs, 2), **mem(proc)})
        print(f"BOŞTA {args.idle_s:.0f}s SONRA ASR {secs:5.2f}s {idle[-1]}", flush=True)
    result["after_idle"] = idle

    replies = []
    msgs = [{"role": "system", "content": CUSTOMER_SYSTEM}, *CUSTOMER_HISTORY]
    for _ in range(5):
        out, secs = gen(client, msgs, 80, SAMPLING)
        replies.append({"text": out["text"], "seconds": round(secs, 2), "tokens": out["new_tokens"]})
        print(f"CEVAP {secs:5.2f}s {out['new_tokens']} tok | {out['text']}", flush=True)
    result["customer_reply"] = {"median_s": sorted(r["seconds"] for r in replies)[2], "rows": replies}

    evals = []
    for _ in range(3):
        out, secs = gen(client, [{"role": "user", "content": EVAL_PROMPT}], 1200, SAMPLING, priority=10)
        raw = re.sub(r"^\s*```(?:json)?|```\s*$", "", out["text"].strip(), flags=re.M).strip()
        try:
            data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            dims = {d.get("dimension_id"): d.get("score") for d in data.get("dimensions", [])}
            ok = set(dims) == {"empathy", "policy_accuracy", "solution", "clarity"}
        except (json.JSONDecodeError, ValueError):
            dims, ok = {}, False
        evals.append({"seconds": round(secs, 2), "tokens": out["new_tokens"], "valid": ok, "scores": dims,
                      "raw": out["text"]})
        print(f"DEĞERLENDİRME {secs:5.2f}s {out['new_tokens']} tok geçerli={ok} {dims}", flush=True)
    result["evaluation"] = {"valid_rate": sum(e["valid"] for e in evals) / 3,
                            "median_s": sorted(e["seconds"] for e in evals)[1], "rows": evals}
    result["mem_end"] = mem(proc)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{args.label}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nÖZET {args.label}: ASR wer={result['asr']['wer']} cer={result['asr']['cer']} "
          f"medyan={result['asr']['median_s']}s | boşta sonrası maks={max(i['seconds'] for i in idle)}s | "
          f"cevap medyan={result['customer_reply']['median_s']}s | değerlendirme medyan="
          f"{result['evaluation']['median_s']}s geçerli={result['evaluation']['valid_rate']:.2f} | "
          f"bellek={result['mem_end']}")


if __name__ == "__main__":
    main()

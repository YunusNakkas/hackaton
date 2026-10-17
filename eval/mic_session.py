"""Gerçek mikrofonla etkileşimli prova: konuş → Gemma duyar → müşteri sesli cevap verir → değerlendirme.

Kendi Terminal pencerende çalıştır (macOS mikrofon izni ister):
  cd ~/Desktop/hackahton/provamusteri
  backend/.venv/bin/python eval/mic_session.py              # Fişsiz iade senaryosu
  backend/.venv/bin/python eval/mic_session.py --list       # senaryoları listele
  backend/.venv/bin/python eval/mic_session.py --training "klima"
  backend/.venv/bin/python eval/mic_session.py --mic "MacBook"   # mikrofon seç (adından bir parça)

Bağımlılık: backend/.venv/bin/pip install sounddevice
Bluetooth kulaklık mikrofonu (AirPods vb.) dar bantlıdır ve ASR'yi belirgin biçimde kötüleştirir;
ölçüm için dahili mikrofon önerilir.

Model servisi çalışmıyorsa otomatik başlatılır (MLX, ~10 sn) ve sonunda kapatılır.
Kayıtlar ve transkriptler: var/mic-tests/<zaman>/  (session.json + kayıt WAV'ları)
"""

import argparse
import io
import json
import os
import queue
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import wave
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="pm-mic-"))
os.environ.update(PM_ENV="test", PM_DATABASE_URL=f"sqlite:///{TMP / 'mic.sqlite3'}", PM_MEDIA_DIR=str(TMP / "media"),
                  PM_MODEL_MODE="real", PM_TTS_PROVIDER="local")
sys.path.insert(0, str(ROOT / "backend"))

import httpx  # noqa: E402
import numpy as np  # noqa: E402

import app.models  # noqa: E402,F401

try:
    import sounddevice as sd
except ImportError:
    sys.exit("sounddevice gerekli: backend/.venv/bin/pip install sounddevice")
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, get_engine, get_sessionmaker  # noqa: E402
from app.main import create_app  # noqa: E402
from app.seed import seed  # noqa: E402
from app.worker.jobs import run_once  # noqa: E402

CSRF = {"X-Requested-With": "provamusteri"}
MAX_S = 30
MODEL_URL = "http://localhost:8100"


def model_up() -> bool:
    try:
        return httpx.get(f"{MODEL_URL}/v1/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def start_model_service() -> subprocess.Popen | None:
    if model_up():
        return None
    print("Model servisi başlatılıyor (MLX, Gemma 4 E4B 4-bit)...", flush=True)
    env = {**os.environ, "PM_RUNTIME": "mlx", "PM_MODEL_ID": "mlx-community/gemma-4-e4b-it-4bit",
           "TOKENIZERS_PARALLELISM": "false"}
    proc = subprocess.Popen([str(ROOT / "model-service/.venv-mlx/bin/uvicorn"), "app.main:app", "--port", "8100"],
                            cwd=ROOT / "model-service", env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(300):
        if model_up():
            print("Model hazır.\n")
            return proc
        if proc.poll() is not None:
            sys.exit("Model servisi başlatılamadı. model-service/README.md'deki kurulumu kontrol et.")
        time.sleep(1)
    proc.terminate()
    sys.exit("Model servisi 5 dakikada hazır olmadı.")


BLUETOOTH_HINTS = ("airpods", "bluetooth", "buds", "headset", "kulaklık")


def pick_mic(name_part: str | None) -> tuple[int, str]:
    mics = [(i, d["name"]) for i, d in enumerate(sd.query_devices()) if d["max_input_channels"] > 0]
    if name_part:
        found = [m for m in mics if name_part.lower() in m[1].lower()]
        if not found:
            sys.exit(f"'{name_part}' adlı mikrofon yok. Mevcut: {', '.join(n for _, n in mics)}")
        return found[0]
    default = sd.query_devices(kind="input")
    return next(m for m in mics if m[1] == default["name"])


def record_until_enter(device: int) -> tuple[bytes, float]:
    """Seçili mikrofondan Enter'a basılana (veya 30 sn dolana) kadar kaydeder; 16 kHz mono WAV döner.

    PortAudio callback'i ile sürekli okunur; cihazın kendi örnekleme hızında alınıp 16 kHz'e çevrilir.
    """
    rate = int(sd.query_devices(device)["default_samplerate"])
    q: queue.Queue[np.ndarray] = queue.Queue()
    overflow = threading.Event()
    stop = threading.Event()

    def callback(indata, frames, t, status):
        if status.input_overflow:
            overflow.set()
        q.put(indata[:, 0].copy())

    print(f"  🎙  Kayıtta... bitirmek için Enter (en fazla {MAX_S} sn)", flush=True)
    waiter = threading.Thread(target=lambda: (input(), stop.set()), daemon=True)
    try:
        with sd.InputStream(device=device, samplerate=rate, channels=1, dtype="float32", callback=callback):
            waiter.start()
            stop.wait(timeout=MAX_S)
    except sd.PortAudioError as exc:
        sys.exit(f"Mikrofon açılamadı: {exc}\nSistem Ayarları > Gizlilik ve Güvenlik > Mikrofon'dan "
                 "Terminal'e izin ver ve tekrar dene.")
    if not stop.is_set():
        print("  (30 sn doldu, kayıt durdu — devam etmek için Enter)")
        waiter.join()
    if overflow.is_set():
        print("  uyarı: kayıt sırasında ses tamponu taştı, bir kısım kaybolmuş olabilir")
    chunks = list(q.queue)
    audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    if rate != 16_000 and len(audio):  # doğrusal ara değerleme; konuşma için yeterli
        n = int(len(audio) * 16_000 / rate)
        audio = np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio)
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16_000)
        w.writeframes(pcm.tobytes())
    return buf.getvalue(), len(pcm) / 16_000


def play(c: TestClient, sid: str, turn_id: str) -> None:
    res = c.get(f"/api/v1/sessions/{sid}/turns/{turn_id}/audio")
    if res.status_code == 200:
        f = TMP / f"{turn_id}.m4a"
        f.write_bytes(res.content)
        subprocess.run(["afplay", str(f)], check=False)


def drain() -> float:
    t0 = time.perf_counter()
    while run_once():
        pass
    return time.perf_counter() - t0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--training", default="Fişsiz iade", help="senaryo başlığından bir parça")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--mic", help="mikrofon adından bir parça (varsayılan: sistemin varsayılanı)")
    args = ap.parse_args()
    # Pencere kapanınca da finally çalışsın; yoksa model servisi arkada açık kalıyordu.
    for sig in (signal.SIGHUP, signal.SIGTERM):
        signal.signal(sig, lambda *_: sys.exit(1))

    Base.metadata.create_all(get_engine())
    with get_sessionmaker()() as db:
        seed(db, "mic-sifre")
    c = TestClient(create_app())
    c.post("/api/v1/auth/login", headers=CSRF, json={"email": "elif@demo.test", "password": "mic-sifre"})
    trainings = c.get("/api/v1/trainings").json()["items"]
    if args.list:
        for t in trainings:
            print(f"- {t['title']} ({t['sector']}, {t['difficulty']}): {t['summary']}")
        return
    matches = [t for t in trainings if args.training.lower() in t["title"].lower()]
    if not matches:
        sys.exit(f"'{args.training}' bulunamadı. --list ile senaryolara bak.")
    training = matches[0]
    detail = c.get(f"/api/v1/trainings/{training['id']}").json()

    mic_id, mic_name = pick_mic(args.mic)
    print(f"Mikrofon: {mic_name}")
    if any(h in mic_name.lower() for h in BLUETOOTH_HINTS):
        print("  uyarı: Bluetooth mikrofon dar bantlıdır, ASR kötüleşir. Dahili mikrofon için: --mic MacBook")
    proc = start_model_service()
    out_dir = ROOT / "var/mic-tests" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    log: dict = {"training": training["title"], "mic": mic_name, "turns": []}

    def save_log() -> None:
        (out_dir / "session.json").write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        print(f"SENARYO: {training['title']}\n{training['summary']}")
        print(f"Müşteri: {detail['customer']['name']} — {detail['customer']['context']}")
        print("Sen mağaza çalışanısın. Her turda Enter'a bas, konuş, tekrar Enter'a bas.")
        print("Görüşmeyi bitirip değerlendirme almak için tur başında 'b' yazıp Enter'a bas.\n")

        created = c.post("/api/v1/sessions", headers=CSRF,
                         json={"training_id": training["id"], "client_request_id": str(uuid.uuid4())}).json()
        sid = created["session"]["id"]
        drain()
        opening = c.get(f"/api/v1/sessions/{sid}").json()["turns"][0]
        print(f"MÜŞTERİ: {opening['text']}")
        play(c, sid, opening["id"])

        n = 0
        while True:
            cmd = input("\n[Enter] konuş  |  [b + Enter] bitir: ").strip().lower()
            if cmd == "b":
                break
            wav, secs = record_until_enter(mic_id)
            n += 1
            (out_dir / f"tur{n}.wav").write_bytes(wav)
            if secs < 0.5:
                print("  Kayıt çok kısa, tekrar dene.")
                continue
            r = c.post(f"/api/v1/sessions/{sid}/turns", headers=CSRF, data={"client_request_id": str(uuid.uuid4())},
                       files={"audio": (f"tur{n}.wav", wav, "audio/wav")})
            if r.status_code != 202:
                print("  Hata:", r.json()["error"]["message"])
                continue
            took = drain()
            job = c.get(f"/api/v1/jobs/{r.json()['job_id']}").json()
            if job["status"] != "ready":
                print("  Hata:", job["error"]["message"])
                continue
            res = job["result"]
            print(f"  SEN (Gemma'nın duyduğu): {res['employee_turn']['text']}")
            print(f"MÜŞTERİ: {res['customer_turn']['text']}   ({took:.1f} sn)")
            log["turns"].append({"file": f"tur{n}.wav", "seconds": round(secs, 1), "asr": res["employee_turn"]["text"],
                                 "reply": res["customer_turn"]["text"], "latency_s": round(took, 2),
                                 "said": None})  # gerçekte ne söylendiği sonradan elle doldurulabilir
            save_log()
            play(c, sid, res["customer_turn"]["id"])
            if res["session_should_end"]:
                print("\n(Müşteri görüşmeyi bitirdi.)")
                break

        if not log["turns"]:
            print("Hiç tur yok, değerlendirme yapılmadı.")
            return
        c.post(f"/api/v1/sessions/{sid}/finish", headers=CSRF)
        print("\nDeğerlendiriliyor (~30 sn)...")
        took = drain()
        ev = c.get(f"/api/v1/sessions/{sid}/evaluation").json()
        log["evaluation"] = ev
        print(f"\nDEĞERLENDİRME ({ev['status']}, {took:.0f} sn)")
        if ev["report"]:
            rep = ev["report"]
            for d in rep["dimensions"]:
                print(f"  {d['name']:22} {d['score'] if d['score'] is not None else '-'} / 4   {d['rationale']}")
            tot = rep["total"]
            print(f"  TOPLAM: {tot['score']} / {tot['max_score']}" if tot["complete"] else "  TOPLAM: eksik boyut var")
            for s in rep["strengths"]:
                print(f"  + {s}")
            for s in rep["improvements"]:
                print(f"  - {s}")
            if rep["flags"]:
                print(f"  bayraklar: {rep['flags']}")
    finally:
        save_log()
        print(f"\nKayıtlar: {out_dir}")
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()

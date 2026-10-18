import { useEffect, useRef, useState } from "react";
import { extensionFor, isBluetoothLabel, isBuiltinLabel, listMics, recordUntilSilence, type MicInput } from "../lib/recorder";

export function VoiceComposer({
  disabled,
  onUpload,
  variant = "dock",
  handsFree = false,
  idleLabel = "Bağlanıyor",
}: {
  disabled: boolean;
  variant?: "dock" | "call";
  handsFree?: boolean;
  idleLabel?: string;
  onUpload: (file: { blob: Blob; durationMs: number; filename: string; clientRequestId: string }) => Promise<void>;
}) {
  const [mics, setMics] = useState<MicInput[]>([]);
  const [deviceId, setDeviceId] = useState("");
  const [recording, setRecording] = useState(false);
  const [level, setLevel] = useState(0);
  const [quiet, setQuiet] = useState(false);
  const [bluetooth, setBluetooth] = useState(false);
  const [deviceLabel, setDeviceLabel] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [failed, setFailed] = useState<{ blob: Blob; durationMs: number; filename: string; clientRequestId: string } | null>(null);
  const handle = useRef<ReturnType<typeof recordUntilSilence> | null>(null);
  const heard = useRef(false);
  const busy = useRef(false);
  const live = useRef(true);
  // Telefon kanalında ses duyulmayınca dinleme kendini yeniden başlatıyordu; üst üste iki kez olursa dur.
  const emptyRounds = useRef(0);
  const [paused, setPaused] = useState(false);
  const [manualOnly, setManualOnly] = useState(false);
  // Önceki kayıt hâlâ gönderilirken dinleme isteği gelirse (müşteri cevabı çabuk bitti) istek kaybolmasın;
  // gönderim bitince uygulanır. Yoksa ekranda "Seni dinliyor" yazar ama kayıt başlamazdı.
  const wantStart = useRef(false);
  const handsFreeNow = useRef(handsFree);
  const disabledNow = useRef(disabled);
  handsFreeNow.current = handsFree;
  disabledNow.current = disabled;

  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
      handle.current?.cancel();
    };
  }, []);

  useEffect(() => {
    void listMics()
      .then((next) => {
        setMics(next);
        const risky = next.some((mic) => mic.bluetooth);
        const internal = next.find((mic) => mic.builtin || isBuiltinLabel(mic.label));
        if (risky) setBluetooth(true);
        if (risky && internal) setDeviceId((current) => current || internal.deviceId);
      })
      .catch(() => setMics([]));
  }, []);

  const selected = mics.find((mic) => mic.deviceId === deviceId);
  const builtin = mics.find((mic) => mic.builtin || isBuiltinLabel(mic.label));
  const warnBluetooth = bluetooth || Boolean(selected && isBluetoothLabel(selected.label));

  async function refreshMics() {
    const next = await listMics();
    setMics(next);
    if (next.some((mic) => mic.bluetooth)) setBluetooth(true);
  }

  async function upload(file: { blob: Blob; durationMs: number; filename: string; clientRequestId: string }) {
    setSending(true);
    setError(null);
    try {
      await onUpload(file);
      setFailed(null);
    } catch (reason) {
      setFailed(file);
      setError(reason instanceof Error ? reason.message : "Ses gönderilemedi.");
    } finally {
      setSending(false);
    }
  }

  async function start() {
    if (disabledNow.current) return;
    if (busy.current) {
      wantStart.current = true;
      return;
    }
    wantStart.current = false;
    busy.current = true;
    setError(null);
    setQuiet(false);
    setPaused(false);
    heard.current = false;
    setRecording(true);
    const session = recordUntilSilence({
      deviceId: deviceId || undefined,
      onLevel: (value) => {
        setLevel(value);
        if (value >= 0.2) heard.current = true;
        setQuiet(value < 0.08 && !heard.current);
      },
      onDevice: (device) => {
        setDeviceLabel(device.label);
        setBluetooth(device.bluetooth);
      },
      onVadUnavailable: () => setManualOnly(true),
    });
    handle.current = session;
    let retry = false;
    try {
      const result = await session.done;
      await refreshMics();
      if (result && !result.heardSpeech) {
        emptyRounds.current += 1;
        retry = handsFree && live.current && emptyRounds.current < 2;
        if (!handsFree) {
          setError("Ses algılanmadı. Kayıt gönderilmedi.");
          setQuiet(true);
        } else if (!retry) {
          setPaused(true);
          setError("Sesini duyamadım. Mikrofonu kontrol edip “Tekrar dinle”ye bas.");
        }
      } else if (result) {
        emptyRounds.current = 0;
        const filename = `cevap.${extensionFor(result.blob.type)}`;
        await upload({
          blob: result.blob,
          durationMs: result.durationMs,
          filename,
          clientRequestId: crypto.randomUUID(),
        });
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Mikrofon açılamadı.");
    } finally {
      handle.current = null;
      busy.current = false;
      setRecording(false);
      setLevel(0);
    }
    const pending = wantStart.current && handsFreeNow.current && !disabledNow.current && live.current;
    wantStart.current = false;
    if (retry || pending) void start();
  }

  const begin = useRef(start);
  begin.current = start;

  useEffect(() => {
    if (!handsFree || disabled) return;
    emptyRounds.current = 0;
    void begin.current();
    return () => {
      wantStart.current = false;
      handle.current?.cancel();
    };
  }, [handsFree, disabled]);

  const call = variant === "call";

  return (
    <div className={call ? "flex flex-col items-center" : "py-3"}>
      <div className={call ? "flex flex-col items-center gap-4" : "flex flex-wrap items-center gap-3"}>
        {call ? (
          <div
            className={`grid h-28 w-28 shrink-0 place-items-center rounded-full text-sm font-semibold text-white ${
              recording ? "bg-pine" : idleLabel === "Dokun" ? "bg-accent" : "bg-white/25"
            }`}
            aria-hidden
          >
            {sending ? "Gidiyor" : recording ? "Hatta" : idleLabel}
          </div>
        ) : (
          <button
            type="button"
            disabled={disabled || sending}
            aria-pressed={recording}
            onClick={() => {
              if (recording) handle.current?.stop();
              else void start();
            }}
            className="rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
          >
            {sending ? "Gidiyor" : recording ? "Dinliyor" : "Konuş"}
          </button>
        )}
        {recording && !call && (
          <button type="button" className="text-sm text-muted underline" onClick={() => handle.current?.cancel()}>
            Vazgeç
          </button>
        )}
        {call && recording && (
          // Otomatik sessizlik algılaması her ortamda çalışmayabilir (gürültü, Safari); elle bitirme her zaman var.
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              handle.current?.stop();
            }}
            className="rounded-full bg-white px-5 py-2 text-sm font-semibold text-ink"
          >
            Bitti, gönder
          </button>
        )}
        {call && handsFree && !disabled && !recording && !sending && !paused && (
          // Güvenlik ağı: dinleme sırası bizde ama kayıt başlamadıysa (tarayıcı, yarış) elle başlatılabilir.
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              void start();
            }}
            className="rounded-full bg-white/15 px-5 py-2 text-sm font-semibold text-white"
          >
            Konuşmaya başla
          </button>
        )}
        {call && paused && !recording && !disabled && (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              emptyRounds.current = 0;
              void start();
            }}
            className="rounded-full bg-white/15 px-5 py-2 text-sm font-semibold text-white"
          >
            Tekrar dinle
          </button>
        )}
        <div className={`flex items-center gap-2 ${call ? "w-40" : "min-w-36 flex-1"}`} aria-label="Mikrofon seviyesi">
          <span className={`h-2 flex-1 overflow-hidden rounded-full ${call ? "bg-white/20" : "bg-line"}`}>
            <span className="block h-full bg-primary transition-[width]" style={{ width: `${Math.round(level * 100)}%` }} />
          </span>
        </div>
      </div>

      {mics.length > 1 && (
        <label className={`mt-3 block text-sm ${call ? "w-full max-w-xs text-white/70" : "text-muted"}`}>
          Mikrofon
          <select
            className="mt-1 w-full rounded-xl border border-line bg-card p-2 text-ink"
            value={deviceId}
            disabled={recording || sending}
            onChange={(event) => {
              setDeviceId(event.target.value);
              setBluetooth(false);
              setDeviceLabel("");
            }}
          >
            <option value="">Tarayıcının seçtiği</option>
            {mics.map((mic) => (
              <option key={mic.deviceId || mic.label} value={mic.deviceId}>
                {mic.label}
              </option>
            ))}
          </select>
        </label>
      )}

      {warnBluetooth && (
        <p className="mt-2 text-sm text-warn">
          {isBluetoothLabel(deviceLabel || selected?.label || "")
            ? `Kayıt ${deviceLabel || selected?.label || "Bluetooth mikrofonuna"} düşebilir. Dahili mikrofon önerilir.`
            : "Listede iPhone veya Bluetooth mikrofon var. Kayıt dahili mikrofona alındı."}
          {builtin && isBluetoothLabel(deviceLabel || selected?.label || "") && (
            <button
              type="button"
              className="ml-2 underline"
              disabled={recording || sending}
              onClick={() => setDeviceId(builtin.deviceId)}
            >
              Dahiliye geç
            </button>
          )}
        </p>
      )}
      {recording && manualOnly && (
        <p className="mt-2 text-sm text-warn">Otomatik algılama bu tarayıcıda çalışmıyor. Konuşman bitince “Bitti, gönder”e bas.</p>
      )}
      {recording && quiet && !manualOnly && (
        <p className="mt-2 text-sm text-warn">Ses gelmiyor. Mikrofona yaklaş ya da dahili mikrofonu seç.</p>
      )}
      {error && <p className="mt-2 text-sm text-accent">{error}</p>}
      {failed && error && (
        <button type="button" className="mt-2 text-sm underline" onClick={() => void upload(failed)}>
          Kaydı tekrar gönder
        </button>
      )}
      {!call && (
        <p className="mt-2 text-xs text-muted">Bir kez bas. Sustuğunda kayıt yaklaşık 1,5 saniye sonra kendiliğinden gider.</p>
      )}
    </div>
  );
}

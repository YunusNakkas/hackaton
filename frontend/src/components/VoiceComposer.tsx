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

  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
      handle.current?.cancel();
    };
  }, []);

  useEffect(() => {
    void listMics().then(setMics).catch(() => setMics([]));
  }, []);

  const selected = mics.find((mic) => mic.deviceId === deviceId);
  const builtin = mics.find((mic) => mic.builtin || isBuiltinLabel(mic.label));
  const warnBluetooth = bluetooth || Boolean(selected && isBluetoothLabel(selected.label));

  async function refreshMics() {
    const next = await listMics();
    setMics(next);
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
    if (disabled || busy.current) return;
    busy.current = true;
    setError(null);
    setQuiet(false);
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
    });
    handle.current = session;
    let retry = false;
    try {
      const result = await session.done;
      await refreshMics();
      if (result && !result.heardSpeech) {
        retry = handsFree && live.current;
        if (!handsFree) {
          setError("Ses algılanmadı. Kayıt gönderilmedi.");
          setQuiet(true);
        }
      } else if (result) {
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
    if (retry) void start();
  }

  const begin = useRef(start);
  begin.current = start;

  useEffect(() => {
    if (!handsFree || disabled) return;
    void begin.current();
    return () => {
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
          Dahili mikrofon önerilir{deviceLabel ? ` (${deviceLabel})` : ""}.
          {builtin && (
            <button
              type="button"
              className="ml-2 underline"
              disabled={recording || sending}
              onClick={() => {
                setDeviceId(builtin.deviceId);
                setBluetooth(false);
              }}
            >
              Dahiliye geç
            </button>
          )}
        </p>
      )}
      {recording && quiet && <p className="mt-2 text-sm text-warn">Ses gelmiyor. Mikrofona yaklaş ya da dahili mikrofonu seç.</p>}
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

const CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];
const BLUETOOTH = /airpod|bluetooth|headset|hands-free|handsfree|earbud|buds|jabra|bose|beats|iphone/;
const BUILTIN = /built-in|internal|macbook|dahili|imac/;

export function supportedMime() {
  if (typeof MediaRecorder === "undefined") return "";
  return CANDIDATES.find((type) => MediaRecorder.isTypeSupported(type)) ?? "";
}

export function extensionFor(mime: string) {
  if (mime.includes("mp4")) return "mp4";
  if (mime.includes("ogg")) return "ogg";
  if (mime.includes("wav")) return "wav";
  return "webm";
}

export function isBluetoothLabel(label: string) {
  return BLUETOOTH.test(label.toLowerCase());
}

export function isBuiltinLabel(label: string) {
  return BUILTIN.test(label.toLowerCase());
}

export interface MicInput {
  deviceId: string;
  label: string;
  bluetooth: boolean;
  builtin: boolean;
}

export async function listMics(): Promise<MicInput[]> {
  if (!navigator.mediaDevices?.enumerateDevices) return [];
  const devices = await navigator.mediaDevices.enumerateDevices();
  return devices
    .filter((device) => device.kind === "audioinput")
    .map((device) => ({
      deviceId: device.deviceId,
      label: device.label || "Mikrofon",
      bluetooth: isBluetoothLabel(device.label),
      builtin: isBuiltinLabel(device.label),
    }));
}

// ---------------------------------------------------------------- ses analizcisi (sessizlik algılama)
// Safari, kullanıcı dokunuşu olmadan oluşturulan AudioContext'i askıda bırakır; telefon kanalında dinleme
// müşteri konuştuktan sonra kendiliğinden başladığı için seviye hep 0 okunuyor ve sessizlik/konuşma
// algılanamıyordu. Tek bir bağlamı ilk dokunuşta açıp sonra yeniden kullanıyoruz.
type AudioCtxCtor = typeof AudioContext;
let sharedContext: AudioContext | null = null;

function audioContextCtor(): AudioCtxCtor | undefined {
  if (typeof window === "undefined") return undefined;
  return window.AudioContext || (window as unknown as { webkitAudioContext?: AudioCtxCtor }).webkitAudioContext;
}

/** Bir kullanıcı dokunuşu içinde çağrılmalı (Safari). Sonraki kayıtlar bu bağlamı kullanır. */
export function unlockAudio() {
  const Ctor = audioContextCtor();
  if (!Ctor) return;
  sharedContext ??= new Ctor();
  if (sharedContext.state === "suspended") void sharedContext.resume();
}

if (typeof window !== "undefined") {
  for (const type of ["pointerdown", "keydown", "touchend"] as const) {
    window.addEventListener(type, unlockAudio, { capture: true, passive: true });
  }
}

/** Sessizlik eşiği ortam gürültüsüne göre: sabit 0,015 eşiği gürültülü odada hiç "sustu" demeyebilir. */
export function createSpeechDetector(silenceMs: number) {
  let floor: number | null = null;
  let heard = false;
  let silentSince: number | null = null;
  return {
    /** Her ~100 ms'de çağrılır. "stop" dönerse konuşma bitti. */
    push(rms: number, now: number): "speech" | "silence" | "stop" {
      // Gürültü tabanı: hızla aşağı, yavaşça yukarı izlenir (konuşma tabanı fazla yükseltmesin).
      floor = floor === null ? rms : rms < floor ? rms : floor + (rms - floor) * 0.01;
      const speechAt = Math.max(0.015, floor * 2);
      const silenceAt = Math.max(0.01, floor * 1.5);
      if (rms >= speechAt) {
        heard = true;
        silentSince = null;
        return "speech";
      }
      if (heard && rms < silenceAt) {
        silentSince ??= now;
        if (now - silentSince >= silenceMs) return "stop";
      }
      return "silence";
    },
    get heardSpeech() {
      return heard;
    },
  };
}

export interface Recording {
  blob: Blob;
  durationMs: number;
  heardSpeech: boolean;
  deviceLabel: string;
  bluetooth: boolean;
  /** Ses analizcisi çalışmadı (ör. askıda AudioContext); konuşma var/yok bilinmiyor, kayıt yine gönderilir. */
  vadUnavailable: boolean;
}

export function recordUntilSilence(
  options: {
    maxMs?: number;
    silenceMs?: number;
    deviceId?: string;
    onLevel?: (level: number) => void;
    onDevice?: (device: { label: string; bluetooth: boolean }) => void;
    /** Otomatik sessizlik algılama çalışmıyor; kullanıcı kaydı elle bitirmeli. */
    onVadUnavailable?: () => void;
  } = {},
): { stop: () => void; cancel: () => void; done: Promise<Recording | null> } {
  const maxMs = options.maxMs ?? 30_000;
  const silenceMs = options.silenceMs ?? 1_500;
  const mime = supportedMime();
  if (typeof MediaRecorder === "undefined") {
    return {
      stop: () => undefined,
      cancel: () => undefined,
      done: Promise.reject(new Error("Bu tarayıcı ses kaydını desteklemiyor. Safari 14.3 veya daha yenisi gerekir.")),
    };
  }
  // Dokunuşla açılmış ortak bağlam varsa onu kullan; yoksa geçici bir bağlam aç (kayıt bitince kapanır).
  const Ctor = audioContextCtor();
  const ownContext = !sharedContext && Ctor ? new Ctor() : null;
  const audioContext = sharedContext ?? ownContext;
  // Safari, <audio> çalarken bağlamı "interrupted" duruma alabiliyor; her kayıtta yeniden uyandır.
  if (audioContext && audioContext.state !== "running") void audioContext.resume().catch(() => undefined);
  const detector = createSpeechDetector(silenceMs);
  let vadUnavailable = !audioContext;
  let recorder: MediaRecorder | null = null;
  let mode: "run" | "stop" | "cancel" = "run";
  let timer = 0;
  const chunks: Blob[] = [];
  let started = 0;

  const done = navigator.mediaDevices
    .getUserMedia({ audio: options.deviceId ? { deviceId: { exact: options.deviceId } } : true })
    .then(
      (stream) =>
        new Promise<Recording | null>((resolve, reject) => {
          const track = stream.getAudioTracks()[0];
          const label = track?.label ?? "";
          const bluetooth = isBluetoothLabel(label);
          options.onDevice?.({ label, bluetooth });

          const media = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
          recorder = media;
          let source: MediaStreamAudioSourceNode | null = null;
          media.ondataavailable = (event) => {
            if (event.data.size) chunks.push(event.data);
          };
          const finish = () => {
            window.clearInterval(timer);
            source?.disconnect();
            void ownContext?.close();
            stream.getTracks().forEach((item) => item.stop());
            if (mode === "cancel") {
              resolve(null);
              return;
            }
            const type = media.mimeType || mime || "audio/webm";
            resolve({
              blob: new Blob(chunks, { type }),
              durationMs: Date.now() - started,
              // Analizci çalışmadıysa konuşma olup olmadığını bilemeyiz: kaydı at(ma), sunucu sessizliği ayıklar.
              heardSpeech: detector.heardSpeech || vadUnavailable,
              deviceLabel: label,
              bluetooth,
              vadUnavailable,
            });
          };
          media.onerror = () => {
            window.clearInterval(timer);
            source?.disconnect();
            void ownContext?.close();
            stream.getTracks().forEach((item) => item.stop());
            reject(new Error("Kayıt alınamadı."));
          };
          media.onstop = finish;

          if (audioContext) {
            source = audioContext.createMediaStreamSource(stream);
            const analyser = audioContext.createAnalyser();
            analyser.fftSize = 2048;
            source.connect(analyser);
            const data = new Uint8Array(analyser.fftSize);
            let flatTicks = 0;
            timer = window.setInterval(() => {
              const now = Date.now();
              if (now - started >= maxMs) media.stop();
              // Askıdaki bağlam düz (128) veri döndürür: 1,5 sn boyunca hiç dalga yoksa analizci çalışmıyor.
              if (audioContext.state !== "running") {
                flatTicks += 1;
                if (flatTicks === 15 && !vadUnavailable) {
                  vadUnavailable = true;
                  options.onVadUnavailable?.();
                }
                return;
              }
              analyser.getByteTimeDomainData(data);
              let sum = 0;
              for (let index = 0; index < data.length; index += 1) {
                const sample = (data[index] - 128) / 128;
                sum += sample * sample;
              }
              const rms = Math.sqrt(sum / data.length);
              options.onLevel?.(Math.min(1, rms / 0.08));
              if (detector.push(rms, now) === "stop") media.stop();
            }, 100);
          } else {
            options.onVadUnavailable?.();
            timer = window.setInterval(() => {
              if (Date.now() - started >= maxMs) media.stop();
            }, 200);
          }

          started = Date.now();
          media.start();
          if (mode === "cancel") media.stop();
          if (mode === "stop") media.stop();
        }),
    )
    .catch((error: unknown) => {
      void ownContext?.close();
      throw error;
    });

  return {
    done,
    stop: () => {
      mode = "stop";
      if (recorder?.state === "recording") recorder.stop();
    },
    cancel: () => {
      mode = "cancel";
      if (recorder?.state === "recording") recorder.stop();
    },
  };
}

/** Mesaj kanalındaki tek basışlık kayıt. Telefon kanalı recordUntilSilence kullanır. */
export function recordOnce(maxMs = 30_000, onTick?: (elapsed: number) => void): {
  stop: () => void;
  done: Promise<{ blob: Blob; durationMs: number }>;
} {
  const mime = supportedMime();
  let recorder: MediaRecorder | null = null;
  let stopRequested = false;
  let timer = 0;
  const chunks: Blob[] = [];
  let started = 0;

  const done = navigator.mediaDevices.getUserMedia({ audio: true }).then(
    (stream) =>
      new Promise<{ blob: Blob; durationMs: number }>((resolve, reject) => {
        const media = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
        recorder = media;
        media.ondataavailable = (event) => {
          if (event.data.size) chunks.push(event.data);
        };
        media.onerror = () => {
          stream.getTracks().forEach((track) => track.stop());
          reject(new Error("Kayıt alınamadı."));
        };
        media.onstop = () => {
          window.clearInterval(timer);
          stream.getTracks().forEach((track) => track.stop());
          const type = media.mimeType || mime || "audio/webm";
          resolve({
            blob: new Blob(chunks, { type }),
            durationMs: Date.now() - started,
          });
        };
        started = Date.now();
        media.start();
        if (stopRequested) {
          media.stop();
          return;
        }
        timer = window.setInterval(() => {
          const elapsed = Date.now() - started;
          onTick?.(elapsed);
          if (elapsed >= maxMs) media.stop();
        }, 200);
      }),
  );

  return {
    done,
    stop: () => {
      stopRequested = true;
      if (recorder?.state === "recording") recorder.stop();
    },
  };
}

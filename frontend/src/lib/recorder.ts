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

function captureConstraints(deviceId?: string): MediaTrackConstraints {
  const audio: MediaTrackConstraints = {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
  };
  if (deviceId) audio.deviceId = { exact: deviceId };
  return audio;
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

export interface Recording {
  blob: Blob;
  durationMs: number;
  heardSpeech: boolean;
  deviceLabel: string;
  bluetooth: boolean;
}

export function recordUntilSilence(
  options: {
    maxMs?: number;
    silenceMs?: number;
    deviceId?: string;
    onLevel?: (level: number) => void;
    onDevice?: (device: { label: string; bluetooth: boolean }) => void;
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
  const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  const audioContext = AudioCtx ? new AudioCtx() : null;
  void audioContext?.resume();
  let recorder: MediaRecorder | null = null;
  let mode: "run" | "stop" | "cancel" = "run";
  let timer = 0;
  const chunks: Blob[] = [];
  let started = 0;
  let heardSpeech = false;
  let silentSince: number | null = null;

  const done = navigator.mediaDevices
    .getUserMedia({ audio: captureConstraints(options.deviceId) })
    .then(
      (stream) =>
        new Promise<Recording | null>((resolve, reject) => {
          const track = stream.getAudioTracks()[0];
          const label = track?.label ?? "";
          const bluetooth = isBluetoothLabel(label);
          options.onDevice?.({ label, bluetooth });

          const media = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
          recorder = media;
          media.ondataavailable = (event) => {
            if (event.data.size) chunks.push(event.data);
          };
          const finish = () => {
            window.clearInterval(timer);
            void audioContext?.close();
            stream.getTracks().forEach((item) => item.stop());
            if (mode === "cancel") {
              resolve(null);
              return;
            }
            const type = media.mimeType || mime || "audio/webm";
            resolve({
              blob: new Blob(chunks, { type }),
              durationMs: Date.now() - started,
              heardSpeech,
              deviceLabel: label,
              bluetooth,
            });
          };
          media.onerror = () => {
            window.clearInterval(timer);
            void audioContext?.close();
            stream.getTracks().forEach((item) => item.stop());
            reject(new Error("Kayıt alınamadı."));
          };
          media.onstop = finish;

          if (audioContext) {
            const source = audioContext.createMediaStreamSource(stream);
            const analyser = audioContext.createAnalyser();
            analyser.fftSize = 2048;
            source.connect(analyser);
            const data = new Uint8Array(analyser.fftSize);
            timer = window.setInterval(() => {
              analyser.getByteTimeDomainData(data);
              let sum = 0;
              for (let index = 0; index < data.length; index += 1) {
                const sample = (data[index] - 128) / 128;
                sum += sample * sample;
              }
              const rms = Math.sqrt(sum / data.length);
              options.onLevel?.(Math.min(1, rms / 0.08));
              if (Date.now() - started < 600) return;
              if (rms >= 0.015) {
                heardSpeech = true;
                silentSince = null;
              } else if (heardSpeech) {
                silentSince ??= Date.now();
                if (Date.now() - silentSince >= silenceMs) media.stop();
              }
              if (Date.now() - started >= maxMs) media.stop();
            }, 100);
          } else {
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
      void audioContext?.close();
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

  const done = navigator.mediaDevices.getUserMedia({ audio: captureConstraints() }).then(
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

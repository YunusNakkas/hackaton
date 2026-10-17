const CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];

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

export interface Recording {
  blob: Blob;
  durationMs: number;
}

export function recordOnce(maxMs = 30_000, onTick?: (elapsed: number) => void): {
  stop: () => void;
  done: Promise<Recording>;
} {
  const mime = supportedMime();
  let recorder: MediaRecorder | null = null;
  let stopRequested = false;
  let timer = 0;
  const chunks: Blob[] = [];
  let started = 0;

  const done = navigator.mediaDevices.getUserMedia({ audio: true }).then(
    (stream) =>
      new Promise<Recording>((resolve, reject) => {
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

const SILENT =
  "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";

let primed: HTMLAudioElement | null = null;

/** Tıklama anında aynı ses öğesini açar; sonraki otomatik çalma Safari'de bloklanmasın. */
export function primeCallAudio() {
  const audio = new Audio(SILENT);
  primed = audio;
  void audio.play().catch(() => undefined);
}

export function takePrimedAudio() {
  const audio = primed;
  primed = null;
  if (audio) audio.pause();
  return audio;
}

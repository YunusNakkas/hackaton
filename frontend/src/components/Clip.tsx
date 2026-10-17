import { useEffect, useRef, useState } from "react";

export function Clip({ src, autoPlay = false }: { src: string; autoPlay?: boolean }) {
  const audio = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    const element = audio.current;
    if (!element || !autoPlay) return;
    element.play().then(
      () => setPlaying(true),
      () => setBlocked(true),
    );
  }, [src, autoPlay]);

  return (
    <div className="mt-2">
      <button
        type="button"
        className="rounded-full border border-line bg-card px-3 py-1 text-sm text-ink hover:border-ink/30"
        onClick={() => {
          const element = audio.current;
          if (!element) return;
          if (element.paused) {
            setError(false);
            element.play().then(() => { setPlaying(true); setBlocked(false); }, () => { setPlaying(false); setError(true); });
          } else {
            element.pause();
            setPlaying(false);
          }
        }}
      >
        {playing ? "Durdur" : blocked ? "Dinlemek için dokun" : "Dinle"}
      </button>
      {error && <p role="alert" className="mt-1 text-xs text-accent">Ses oynatılamadı. Tekrar deneyin.</p>}
      <audio
        ref={audio}
        src={src}
        preload="auto"
        onEnded={() => setPlaying(false)}
        onPause={() => setPlaying(false)}
        onError={() => { setPlaying(false); setError(true); }}
      />
    </div>
  );
}

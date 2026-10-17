import { useEffect, useRef, useState } from "react";

export function Clip({ src, autoPlay = false }: { src: string; autoPlay?: boolean }) {
  const audio = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [blocked, setBlocked] = useState(false);

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
            void element.play();
            setPlaying(true);
            setBlocked(false);
          } else {
            element.pause();
            setPlaying(false);
          }
        }}
      >
        {playing ? "Durdur" : blocked ? "Dinlemek için dokun" : "Dinle"}
      </button>
      <audio
        ref={audio}
        src={src}
        preload="auto"
        onEnded={() => setPlaying(false)}
        onPause={() => setPlaying(false)}
      />
    </div>
  );
}

import { useEffect, useRef, useState } from "react";
import type { Turn } from "../api/types";
import { takePrimedAudio } from "../lib/callAudio";
import { VoiceComposer } from "./VoiceComposer";

export function PhoneCall({
  title,
  turns,
  sessionId,
  waiting,
  canTalk,
  notice,
  onUpload,
  onHangup,
  hangupDisabled,
  hangupLabel = "Aramayı kapat",
}: {
  title: string;
  turns: Turn[];
  sessionId: string;
  waiting: boolean;
  canTalk: boolean;
  notice: string | null;
  onUpload: (file: { blob: Blob; durationMs: number; filename: string; clientRequestId: string }) => Promise<void>;
  onHangup: () => void;
  hangupDisabled: boolean;
  hangupLabel?: string;
}) {
  const holder = useRef<HTMLDivElement>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const customerId = useRef<string | null>(null);
  const [heardId, setHeardId] = useState<string | null>(null);
  const [audioReady, setAudioReady] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const customer = [...turns].reverse().find((turn) => turn.speaker === "customer");
  const mine = [...turns].reverse().find((turn) => turn.speaker === "employee" && turn.text);
  const src = customer?.has_audio ? `/api/v1/sessions/${sessionId}/turns/${customer.id}/audio` : "";
  const unheard = Boolean(src && customer && heardId !== customer.id);
  customerId.current = customer?.id ?? null;

  useEffect(() => {
    const element = takePrimedAudio() ?? new Audio();
    audio.current = element;
    element.preload = "auto";
    const onEnded = () => {
      const id = customerId.current;
      if (id) setHeardId(id);
      setPlaying(false);
    };
    element.addEventListener("ended", onEnded);
    holder.current?.appendChild(element);
    setAudioReady(true);
    return () => {
      setAudioReady(false);
      element.pause();
      element.removeEventListener("ended", onEnded);
      element.remove();
      if (audio.current === element) audio.current = null;
    };
  }, []);

  useEffect(() => {
    const element = audio.current;
    if (!audioReady || !element || !unheard || !src) return;
    setPlaying(true);
    setBlocked(false);
    element.src = src;
    void element.play().catch(() => {
      setPlaying(false);
      setBlocked(true);
    });
  }, [audioReady, src, unheard, customer?.id]);

  const listening = canTalk && !unheard && !playing && !blocked;
  const line = blocked
    ? "Arama açık. Devam etmek için ekrana dokun."
    : unheard || playing
      ? "Müşteri konuşuyor"
      : waiting || customer?.status === "processing"
        ? "Müşteri cevap veriyor"
        : listening
          ? "Seni dinliyor. Sustuğunda söz ona geçer."
          : "Hat kuruluyor";

  return (
    <section
      className="mt-4 flex min-h-0 flex-1 flex-col justify-between overflow-y-auto rounded-[2rem] bg-[#0c1e3a] px-6 py-8 text-[#f0f7ff]"
      onClick={() => {
        if (!blocked || !audio.current) return;
        void audio.current.play().then(
          () => {
            setBlocked(false);
            setPlaying(true);
          },
          () => setBlocked(true),
        );
      }}
    >
      <div className="text-center">
        <p className="text-xs tracking-[0.2em] text-white/50">TELEFON</p>
        <h2 className="mt-3 font-serif text-4xl tracking-tight">{title}</h2>
        <p className="mt-2 text-sm text-white/70">{notice ?? line}</p>
      </div>

      <div className="mx-auto w-full max-w-md space-y-3 text-sm">
        {customer?.text && (
          <p className="rounded-2xl bg-white/10 px-4 py-3">
            <span className="block text-xs text-white/50">Müşteri</span>
            {customer.text}
          </p>
        )}
        {mine && (
          <p className="rounded-2xl bg-white/5 px-4 py-3 text-white/80">
            <span className="block text-xs text-white/50">Sen</span>
            {mine.text}
          </p>
        )}
      </div>

      <div className="mx-auto w-full max-w-md">
        <div ref={holder} className="hidden" />
        <VoiceComposer
          variant="call"
          handsFree={listening}
          disabled={!listening}
          idleLabel={blocked ? "Dokun" : "Bağlanıyor"}
          onUpload={onUpload}
        />
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onHangup();
          }}
          disabled={hangupDisabled}
          className="mx-auto mt-6 block rounded-full bg-accent px-5 py-2 text-sm text-white disabled:opacity-40"
        >
          {hangupLabel}
        </button>
      </div>
    </section>
  );
}

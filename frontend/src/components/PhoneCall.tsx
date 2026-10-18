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
  ended,
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
  ended?: boolean;
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
  const [ear, setEar] = useState(false);
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
    if (!audioReady || !element || !unheard || !src || ended) return;
    setPlaying(true);
    setBlocked(false);
    element.src = src;
    void element.play().catch(() => {
      setPlaying(false);
      setBlocked(true);
    });
  }, [audioReady, src, unheard, customer?.id, ended]);

  useEffect(() => {
    if (ended || unheard || playing || blocked || !canTalk) {
      setEar(false);
      return;
    }
    const timer = window.setTimeout(() => setEar(true), 800);
    return () => window.clearTimeout(timer);
  }, [ended, unheard, playing, blocked, canTalk, customer?.id]);

  const listening = !ended && canTalk && !unheard && !playing && !blocked && ear;
  const line = ended
    ? (notice ?? "Arama bitti")
    : blocked
      ? "Arama açık. Devam etmek için ekrana dokun."
      : unheard || playing
        ? "Müşteri konuşuyor"
        : waiting || customer?.status === "processing"
          ? "Müşteri cevap veriyor"
          : listening
            ? "Seni dinliyor. Sustuğunda söz ona geçer."
            : canTalk
              ? "Sıra sana geliyor"
              : "Hat kuruluyor";
  const idleLabel = ended ? "Kapandı" : blocked ? "Dokun" : waiting ? "Bekliyor" : "Bağlanıyor";

  return (
    <section
      className="mt-3 flex min-h-0 flex-1 flex-col overflow-hidden rounded-[2rem] bg-[var(--pm-call)] text-[#f0f7ff]"
      onClick={() => {
        if (ended || !blocked || !audio.current) return;
        void audio.current.play().then(
          () => {
            setBlocked(false);
            setPlaying(true);
          },
          () => setBlocked(true),
        );
      }}
    >
      <header className="flex shrink-0 items-start justify-between gap-3 px-5 pt-5">
        <div>
          <p className="text-[11px] tracking-[0.28em] text-white/40">TELEFON</p>
          <p className="mt-1.5 text-sm text-white/80">{line}</p>
        </div>
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onHangup();
          }}
          disabled={hangupDisabled}
          className="shrink-0 rounded-full bg-[#ff5b6e] px-3.5 py-1.5 text-xs font-medium text-white disabled:opacity-40"
        >
          {hangupLabel}
        </button>
      </header>

      <div className="min-h-[7rem] flex-1 overflow-y-auto px-5 py-4">
        <div className="mx-auto w-full max-w-md space-y-3 text-sm">
          {customer?.text ? (
            <p className="rounded-2xl bg-white/10 px-4 py-3 leading-relaxed">
              <span className="mb-1 block text-[11px] uppercase tracking-wider text-white/45">Müşteri</span>
              {customer.text}
            </p>
          ) : (
            <p className="rounded-2xl bg-white/5 px-4 py-3 text-sm text-white/50">
              Hat açılıyor. Müşteri birazdan konuşacak.
            </p>
          )}
          {mine && (
            <p className="rounded-2xl bg-white/5 px-4 py-3 leading-relaxed text-white/85">
              <span className="mb-1 block text-[11px] uppercase tracking-wider text-white/45">Sen</span>
              {mine.text}
            </p>
          )}
        </div>
      </div>

      <footer className="shrink-0 px-5 pb-5 pt-1">
        <div ref={holder} className="hidden" />
        <VoiceComposer
          variant="call"
          handsFree={listening}
          disabled={!listening}
          hideInputs={ended}
          idleLabel={idleLabel}
          onUpload={onUpload}
        />
        <p className="sr-only">{title}</p>
      </footer>
    </section>
  );
}

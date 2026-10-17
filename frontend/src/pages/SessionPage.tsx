import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, isApiError } from "../api/client";
import type { EvaluationEnvelope, Job, Session, TurnAccepted } from "../api/types";
import { Clip } from "../components/Clip";
import { ReportView } from "../components/ReportView";
import { evaluationLabel, formatClock, jobLabel, speakerLabel } from "../lib/labels";
import { extensionFor, recordOnce, supportedMime } from "../lib/recorder";

const ACTIVE = new Set(["queued", "transcribing", "generating", "synthesizing", "evaluating"]);

export function SessionPage() {
  const { sessionId = "" } = useParams();
  const queryClient = useQueryClient();
  const bottom = useRef<HTMLDivElement>(null);
  const seenAudio = useRef<Set<string> | null>(null);
  const [freshAudioId, setFreshAudioId] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const stopRef = useRef<(() => void) | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [shouldEnd, setShouldEnd] = useState(false);

  const sessionQuery = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => api<Session>(`/sessions/${sessionId}`),
  });
  const session = sessionQuery.data;
  const liveJobId = session?.status === "active" ? session.pending_job_id : null;

  const jobQuery = useQuery({
    queryKey: ["job", liveJobId],
    enabled: Boolean(liveJobId),
    queryFn: () => api<Job>(`/jobs/${liveJobId}`),
    refetchInterval: (query) => {
      const job = query.state.data;
      if (!job || job.status === "ready" || job.status === "error") return false;
      return job.poll_after_ms;
    },
  });

  const evaluation = useQuery({
    queryKey: ["evaluation", sessionId],
    enabled: session?.status === "finished",
    queryFn: () => api<EvaluationEnvelope>(`/sessions/${sessionId}/evaluation`),
    refetchInterval: (query) => (query.state.data?.status === "pending" ? 1500 : false),
  });

  const evalJobId = evaluation.data?.status === "pending" ? evaluation.data.evaluation_job_id : null;
  const evalJob = useQuery({
    queryKey: ["job", evalJobId],
    enabled: Boolean(evalJobId),
    queryFn: () => api<Job>(`/jobs/${evalJobId}`),
    refetchInterval: (query) => {
      const job = query.state.data;
      if (!job || job.status === "ready" || job.status === "error") return false;
      return job.poll_after_ms;
    },
  });

  const job = jobQuery.data;
  const jobBusy = Boolean(job && ACTIVE.has(job.status));

  useEffect(() => {
    if (job?.status !== "ready" && job?.status !== "error") return;
    void queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
    if (job.result?.kind === "turn" && job.result.session_should_end) setShouldEnd(true);
  }, [job?.status, job?.result, queryClient, sessionId]);

  useEffect(() => {
    if (evalJob.data?.status === "ready" || evalJob.data?.status === "error") {
      void queryClient.invalidateQueries({ queryKey: ["evaluation", sessionId] });
      void queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
    }
  }, [evalJob.data?.status, queryClient, sessionId]);

  useEffect(() => {
    if (!session) return;
    const playable = session.turns.filter((turn) => turn.speaker === "customer" && turn.has_audio).map((turn) => turn.id);
    if (seenAudio.current === null) {
      seenAudio.current = new Set(playable);
      return;
    }
    const added = playable.find((id) => !seenAudio.current?.has(id));
    for (const id of playable) seenAudio.current.add(id);
    if (added) setFreshAudioId(added);
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [session]);

  async function send(blob: Blob, durationMs: number, clientRequestId: string) {
    const body = new FormData();
    const mime = blob.type || "audio/webm";
    body.append("audio", blob, `cevap.${extensionFor(mime)}`);
    body.append("client_request_id", clientRequestId);
    body.append("client_duration_ms", String(durationMs));
    await api<TurnAccepted>(`/sessions/${sessionId}/turns`, { method: "POST", body });
    await queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
  }

  async function startRecording() {
    if (!supportedMime() && typeof MediaRecorder === "undefined") {
      setNotice("Bu tarayıcı ses kaydını desteklemiyor.");
      return;
    }
    setNotice(null);
    setElapsed(0);
    setRecording(true);
    const handle = recordOnce(30_000, setElapsed);
    stopRef.current = handle.stop;
    try {
      const taken = await handle.done;
      setRecording(false);
      stopRef.current = null;
      if (taken.durationMs < 500) {
        setNotice("Biraz daha konuş. En az yarım saniye.");
        return;
      }
      setUploading(true);
      await send(taken.blob, taken.durationMs, crypto.randomUUID());
    } catch (error) {
      setRecording(false);
      const denied = error instanceof DOMException && (error.name === "NotAllowedError" || error.name === "NotFoundError");
      setNotice(
        denied
          ? "Mikrofona erişilemedi. Tarayıcı iznini kontrol et."
          : isApiError(error)
            ? error.message
            : "Kayıt gönderilemedi.",
      );
    } finally {
      setUploading(false);
    }
  }

  async function retryJob() {
    if (!liveJobId) return;
    setNotice(null);
    try {
      await api(`/jobs/${liveJobId}/retry`, { method: "POST" });
      await queryClient.invalidateQueries({ queryKey: ["job", liveJobId] });
      await queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
    } catch (error) {
      setNotice(isApiError(error) ? error.message : "Tekrar denenemedi.");
    }
  }

  async function finish() {
    setNotice(null);
    try {
      await api(`/sessions/${sessionId}/finish`, { method: "POST" });
      await queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
      await queryClient.invalidateQueries({ queryKey: ["assignments"] });
    } catch (error) {
      setNotice(isApiError(error) ? error.message : "Görüşme bitirilemedi.");
    }
  }

  if (sessionQuery.isLoading) return <p className="text-muted">Yükleniyor…</p>;
  if (sessionQuery.isError || !session) {
    return (
      <p className="text-accent">
        Oturum bulunamadı. <Link to="/">Geri dön</Link>
      </p>
    );
  }

  const finished = session.status === "finished";
  const evalStatus = evaluation.data?.status ?? session.evaluation_status;
  const atLimit = session.employee_turn_count >= session.max_turns;
  const canTalk = !finished && !atLimit && !recording && !uploading && !jobBusy;

  return (
    <div className="mx-auto max-w-3xl pb-28">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link to="/" className="text-sm text-muted hover:text-ink">
            ← Eğitimler
          </Link>
          <h1 className="mt-2 font-serif text-3xl tracking-tight">{session.training.title}</h1>
          <p className="mt-1 text-sm text-muted">
            {session.employee_turn_count} / {session.max_turns} cevap
            {finished && evalStatus ? ` · ${evaluationLabel[evalStatus]}` : ""}
          </p>
        </div>
        {!finished && (
          <button
            type="button"
            onClick={() => void finish()}
            disabled={session.employee_turn_count === 0 || jobBusy || uploading || recording}
            className="rounded-full border border-ink px-4 py-2 text-sm disabled:opacity-40"
          >
            Bitir ve değerlendir
          </button>
        )}
      </div>

      {finished && (
        <div className="mt-8">
          {evaluation.data?.report ? (
            <>
              {evaluation.data.status === "needs_review" && (
                <p className="mb-4 text-sm text-warn">
                  Rapor çıktı ama bazı kanıtlar doğrulanamadı. Sonuç, yönetici bakmadan kesin sayılmıyor.
                </p>
              )}
              <ReportView report={evaluation.data.report} />
            </>
          ) : evaluation.data?.status === "error" ? (
            <p className="text-accent">{evaluation.data.error?.message ?? "Değerlendirme tamamlanamadı."}</p>
          ) : (
            <p className="text-muted">{evalJob.data ? jobLabel[evalJob.data.status] : "Değerlendirme hazırlanıyor…"}</p>
          )}
        </div>
      )}

      <ol className={`space-y-4 ${finished ? "mt-10 border-t border-line pt-8" : "mt-8"}`}>
        {finished && <li className="text-sm text-muted">Konuşma</li>}
        {session.turns.map((turn) => (
          <li key={turn.id} className={turn.speaker === "employee" ? "flex justify-end" : ""}>
            <article
              className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                turn.speaker === "employee" ? "bg-ink text-paper" : "border border-line bg-card"
              }`}
            >
              <p className={`text-xs ${turn.speaker === "employee" ? "text-paper/70" : "text-muted"}`}>
                {speakerLabel[turn.speaker]}
                {turn.status === "processing" ? " · hazırlanıyor" : ""}
                {turn.status === "error" ? " · işlenemedi" : ""}
              </p>
              <p className="mt-1 whitespace-pre-wrap">{turn.text ?? (turn.status === "processing" ? "…" : "")}</p>
              {turn.has_audio && (
                <Clip
                  src={`/api/v1/sessions/${session.id}/turns/${turn.id}/audio`}
                  autoPlay={turn.id === freshAudioId}
                />
              )}
            </article>
          </li>
        ))}
      </ol>
      <div ref={bottom} />

      {!finished && (
        <div className="fixed inset-x-0 bottom-0 border-t border-line bg-paper/95 backdrop-blur">
          <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-4 px-5 py-4">
            <button
              type="button"
              disabled={!canTalk && !recording}
              onClick={() => {
                if (recording) stopRef.current?.();
                else void startRecording();
              }}
              className={`grid h-14 w-14 place-items-center rounded-full text-paper ${
                recording ? "bg-accent" : "bg-ink disabled:opacity-40"
              }`}
              aria-label={recording ? "Kaydı bitir" : "Konuş"}
            >
              <span className={recording ? "h-3.5 w-3.5 rounded-sm bg-paper" : "h-3.5 w-3.5 rounded-full bg-accent"} />
            </button>
            <div className="min-w-0 flex-1">
              <p className="text-sm">
                {recording
                  ? `Kayıt ${formatClock(elapsed)} / 0:30`
                  : uploading
                    ? "Gönderiliyor…"
                    : jobBusy && job
                      ? jobLabel[job.status]
                      : job?.status === "error"
                        ? job.error?.message
                        : shouldEnd
                          ? "Müşteri konuşmayı kapattı. İstersen bitir."
                          : atLimit
                            ? "Tur doldu. Değerlendirme için bitir."
                            : "Konuş, sonra düğmeye bas."}
              </p>
              {notice && <p className="text-sm text-accent">{notice}</p>}
            </div>
            {job?.status === "error" && job.error?.retryable && (
              <button type="button" onClick={() => void retryJob()} className="text-sm underline">
                Tekrar dene
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

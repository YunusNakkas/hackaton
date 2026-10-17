import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, isApiError } from "../api/client";
import type { EvaluationEnvelope, Job, Session, TurnAccepted } from "../api/types";
import { Clip } from "../components/Clip";
import { ReportView } from "../components/ReportView";
import { evaluationLabel, jobLabel, speakerLabel } from "../lib/labels";

const ACTIVE = new Set(["queued", "transcribing", "generating", "synthesizing", "evaluating"]);

export function SessionPage() {
  const { sessionId = "" } = useParams();
  const queryClient = useQueryClient();
  const thread = useRef<HTMLOListElement>(null);
  const seenAudio = useRef<Set<string> | null>(null);
  const [freshAudioId, setFreshAudioId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [shouldEnd, setShouldEnd] = useState(false);
  const requestId = useRef<string | null>(null);

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
    const box = thread.current;
    if (box) box.scrollTop = box.scrollHeight;
    const playable = session.turns.filter((turn) => turn.speaker === "customer" && turn.has_audio).map((turn) => turn.id);
    if (seenAudio.current === null) {
      seenAudio.current = new Set(playable);
      return;
    }
    const added = playable.find((id) => !seenAudio.current?.has(id));
    for (const id of playable) seenAudio.current.add(id);
    if (added) setFreshAudioId(added);
  }, [session]);

  async function sendMessage() {
    const text = draft.trim();
    if (!text || sending) return;
    setNotice(null);
    const clientRequestId = requestId.current ?? crypto.randomUUID();
    requestId.current = clientRequestId;
    setSending(true);
    try {
      await api<TurnAccepted>(`/sessions/${sessionId}/messages`, {
        method: "POST",
        body: JSON.stringify({ text, client_request_id: clientRequestId }),
      });
      requestId.current = null;
      setDraft("");
      await queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
    } catch (error) {
      setNotice(isApiError(error) ? error.message : "Mesaj gönderilemedi.");
    } finally {
      setSending(false);
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
  const canSend = !finished && !atLimit && !sending && !jobBusy;

  return (
    <div
      className={`mx-auto max-w-3xl ${finished ? "" : "flex h-[calc(100dvh-7.75rem)] flex-col"}`}
    >
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
            disabled={session.employee_turn_count === 0 || jobBusy || sending}
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

      <ol
        ref={thread}
        className={`min-h-0 flex-1 space-y-4 overflow-y-auto ${finished ? "mt-10 border-t border-line pt-8" : "my-4"}`}
      >
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
      {!finished && (
        <form
          className="shrink-0 border-t border-line pt-3"
          onSubmit={(event) => {
            event.preventDefault();
            void sendMessage();
          }}
        >
          <div className="py-3">
            <p className="mb-2 text-sm text-muted">
              {sending
                ? "Gönderiliyor…"
                : jobBusy && job
                  ? jobLabel[job.status]
                  : job?.status === "error"
                    ? job.error?.message
                    : shouldEnd
                      ? "Müşteri konuşmayı kapattı. İstersen bitir."
                      : atLimit
                        ? "Tur doldu. Değerlendirme için bitir."
                        : "Yaz, Enter ile gönder."}
              {notice ? <span className="text-accent"> {notice}</span> : null}
              {job?.status === "error" && job.error?.retryable && (
                <button type="button" onClick={() => void retryJob()} className="ml-2 underline">
                  Tekrar dene
                </button>
              )}
            </p>
            <div className="flex items-end gap-2">
              <textarea
                value={draft}
                rows={2}
                maxLength={1000}
                disabled={!canSend}
                placeholder="Cevabını yaz"
                className="min-h-12 flex-1 resize-none rounded-2xl border border-line bg-card px-4 py-3 outline-none focus:border-ink disabled:opacity-50"
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void sendMessage();
                  }
                }}
              />
              <button
                type="submit"
                disabled={!canSend || draft.trim().length === 0}
                className="rounded-full bg-ink px-4 py-2.5 text-paper disabled:opacity-40"
              >
                Gönder
              </button>
            </div>
          </div>
        </form>
      )}
    </div>
  );
}

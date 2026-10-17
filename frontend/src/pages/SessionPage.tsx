import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { api, isApiError } from "../api/client";
import type { CreateSessionResponse, EvaluationEnvelope, Job, Me, Session, TurnAccepted } from "../api/types";
import { Clip } from "../components/Clip";
import { ReportView } from "../components/ReportView";
import { PhoneCall } from "../components/PhoneCall";
import { ReviewModal } from "../components/ReviewModal";
import { evaluationLabel, formatClock, jobLabel, speakerLabel } from "../lib/labels";
import { extensionFor, recordOnce, supportedMime } from "../lib/recorder";

const ACTIVE = new Set(["queued", "transcribing", "generating", "synthesizing", "evaluating"]);

export function SessionPage() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const focus = (location.state as { focus?: { title: string; instructions: string; names: string[] } } | null)?.focus;
  const queryClient = useQueryClient();
  const thread = useRef<HTMLOListElement>(null);
  const seenAudio = useRef<Set<string> | null>(null);
  const [freshAudioId, setFreshAudioId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [shouldEnd, setShouldEnd] = useState(false);
  const requestId = useRef<{ id: string; text: string } | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const stopRecording = useRef<(() => void) | null>(null);
  const canRecord = typeof MediaRecorder !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia);
  const [restarting, setRestarting] = useState(false);

  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });

  const sessionQuery = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => api<Session>(`/sessions/${sessionId}`),
    refetchInterval: query => query.state.data?.status === "active" ? 3000 : 15000,
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
    refetchInterval: (query) => (query.state.data?.status === "pending" ? 1500 : 15000),
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
  const jobBusy = Boolean(liveJobId && (!job || ACTIVE.has(job.status)));

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
    if (!text || !canSend) return;
    setNotice(null);
    const clientRequestId = requestId.current?.text === text ? requestId.current.id : crypto.randomUUID();
    requestId.current = { id: clientRequestId, text };
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

  // Sayfadan çıkılırsa mikrofon açık kalmasın.
  useEffect(() => () => stopRecording.current?.(), []);

  async function sendRecording() {
    setNotice(null);
    setElapsed(0);
    setRecording(true);
    const handle = recordOnce(30_000, setElapsed);
    stopRecording.current = handle.stop;
    try {
      const taken = await handle.done;
      setRecording(false);
      stopRecording.current = null;
      if (taken.durationMs < 500) {
        setNotice("Biraz daha konuş, en az yarım saniye.");
        return;
      }
      setSending(true);
      const body = new FormData();
      const mime = taken.blob.type || supportedMime() || "audio/webm";
      body.append("audio", taken.blob, `cevap.${extensionFor(mime)}`);
      body.append("client_request_id", crypto.randomUUID());
      body.append("client_duration_ms", String(taken.durationMs));
      await api<TurnAccepted>(`/sessions/${sessionId}/turns`, { method: "POST", body });
      await queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
    } catch (error) {
      setRecording(false);
      stopRecording.current = null;
      const denied = error instanceof DOMException && (error.name === "NotAllowedError" || error.name === "NotFoundError");
      setNotice(
        denied
          ? "Mikrofona erişilemedi. Tarayıcı iznini kontrol et ya da yazarak cevap ver."
          : isApiError(error)
            ? error.code === "no_speech"
              ? `${error.message} İstersen yazarak da gönderebilirsin.`
              : error.message
            : "Kayıt gönderilemedi.",
      );
    } finally {
      setSending(false);
    }
  }

  async function sendAudio(file: { blob: Blob; durationMs: number; filename: string; clientRequestId: string }) {
    setNotice(null);
    const body = new FormData();
    body.append("audio", file.blob, file.filename);
    body.append("client_request_id", file.clientRequestId);
    body.append("client_duration_ms", String(file.durationMs));
    await api<TurnAccepted>(`/sessions/${sessionId}/turns`, { method: "POST", body });
    await queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
  }

  async function practiceAgain() {
    const drill = evaluation.data?.report?.practice_drill;
    if (!session || !drill || restarting) return;
    setRestarting(true);
    setNotice(null);
    try {
      const focusIds = drill.focus_dimension_ids.filter(Boolean).slice(0, 3);
      const created = await api<CreateSessionResponse>("/sessions", {
        method: "POST",
        body: JSON.stringify({
          training_id: session.training.id,
          channel: session.channel,
          client_request_id: crypto.randomUUID(),
          ...(focusIds.length
            ? { practice: { of_session_id: session.id, mode: "adaptive", focus_dimension_ids: focusIds } }
            : {}),
        }),
      });
      const names = focusIds.map(
        (id) => evaluation.data?.report?.dimensions.find((dimension) => dimension.dimension_id === id)?.name ?? id,
      );
      navigate(`/sessions/${created.session.id}`, {
        state: { focus: { title: drill.title, instructions: drill.instructions, names } },
      });
    } catch (error) {
      setNotice(isApiError(error) ? error.message : "Yeni prova açılamadı.");
    } finally {
      setRestarting(false);
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

  async function retryEvaluation() {
    const id = evaluation.data?.evaluation_job_id;
    if (!id) return;
    setNotice(null);
    try {
      await api(`/jobs/${id}/retry`, { method: "POST" });
      await queryClient.invalidateQueries({ queryKey: ["evaluation", sessionId] });
      await queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
      await queryClient.invalidateQueries({ queryKey: ["job", id] });
    } catch (error) {
      setNotice(isApiError(error) ? error.message : "Değerlendirme yeniden başlatılamadı.");
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
  const isOwner = me.data?.user.id === session.employee.id;
  const evalStatus = evaluation.data?.status ?? session.evaluation_status;
  const atLimit = session.employee_turn_count >= session.max_turns;
  const canSend = isOwner && !finished && !atLimit && !sending && !jobBusy && !recording;
  const noSpeech = job?.status === "error" && job.error?.code === "no_speech";
  const phone = session.channel === "phone";
  const callNote =
    job?.status === "error"
      ? (job.error?.message ?? "Hat koptu")
      : shouldEnd
        ? "Müşteri kapattı"
        : atLimit
          ? "Süre doldu"
          : notice;

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
            {finished && evalStatus ? ` · ${session.review_status === "reviewed" ? "İncelendi" : evaluationLabel[evalStatus]}` : ""}
          </p>
        </div>
        {!finished && isOwner && !phone && (
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
          {me.data?.user.role === "manager" && evaluation.data?.report && (
            <div className="mb-6 rounded-3xl border border-primary/30 bg-primary/5 p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-ink text-base">Yönetici İnceleme Paneli</span>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      session.review_status === "reviewed"
                        ? "bg-pine-soft text-pine"
                        : "bg-warn-soft text-warn"
                    }`}
                  >
                    {session.review_status === "reviewed" ? "✓ İncelendi" : session.review_status === "pending" ? "İnceleme Bekliyor" : "İnceleme İsteğe Bağlı"}
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted">
                  {session.review_status === "reviewed"
                    ? "Bu oturum için inceleme tamamlandı. Karar ve puan düzeltmelerini güncelleyebilirsiniz."
                    : "Model değerlendirmesini onaylayabilir veya boyut puanlarını gerekçeleriyle düzeltebilirsiniz."}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setReviewOpen(true)}
                className="rounded-full bg-primary px-5 py-2.5 text-xs font-semibold text-white hover:opacity-95 transition-opacity whitespace-nowrap self-start sm:self-center"
              >
                {session.review_status === "reviewed" ? "İncelemeyi Düzenle" : "İncele ve Onayla →"}
              </button>
            </div>
          )}

          {evaluation.data?.report ? (
            <>
              {evaluation.data.status === "needs_review" && session.review_status !== "reviewed" && (
                <p className="mb-4 text-sm text-warn">
                  Rapor çıktı ama bazı kanıtlar doğrulanamadı. Sonuç, yönetici bakmadan kesin sayılmıyor.
                </p>
              )}
              <ReportView report={evaluation.data.report} onPracticeAgain={isOwner ? () => void practiceAgain() : undefined} />
            </>
          ) : evaluation.data?.status === "error" ? (
            <div className="space-y-3"><p role="alert" className="text-accent">{evaluation.data.error?.message ?? "Değerlendirme tamamlanamadı."}</p>{evaluation.data.error?.retryable && <button type="button" onClick={() => void retryEvaluation()} className="rounded-full border border-line px-4 py-2 text-sm text-primary">Değerlendirmeyi tekrar dene</button>}</div>
          ) : (
            <p className="text-muted">{evalJob.data ? jobLabel[evalJob.data.status] : "Değerlendirme hazırlanıyor…"}</p>
          )}
        </div>
      )}

      {!finished && focus && (
        <p className="mt-4 rounded-2xl bg-pine-soft px-4 py-3 text-sm text-pine">
          Bu provanın odağı: {focus.names.filter(Boolean).join(", ") || focus.title}. {focus.instructions}
        </p>
      )}

      {finished && notice && <p role="alert" className="mt-4 text-accent">{notice}</p>}
      {jobQuery.isError && <p role="alert" className="mt-4 text-accent">İş durumu alınamadı. <button type="button" className="underline" onClick={() => void jobQuery.refetch()}>Tekrar kontrol et</button></p>}

      {phone && !finished && (
        <PhoneCall
          title={session.training.title}
          turns={session.turns}
          sessionId={session.id}
          waiting={jobBusy || sending}
          canTalk={canSend && job?.status !== "error" && !shouldEnd}
          notice={callNote}
          onUpload={sendAudio}
          onHangup={() => void finish()}
          hangupDisabled={session.employee_turn_count === 0 || jobBusy || sending}
          hangupLabel={session.employee_turn_count === 0 ? "Önce bir cevap ver" : "Aramayı kapat"}
        />
      )}

      <ol
        ref={thread}
        className={`min-h-0 flex-1 space-y-4 overflow-y-auto ${phone && !finished ? "hidden" : ""} ${finished ? "mt-10 border-t border-line pt-8" : "my-4"}`}
      >
        <li className="text-sm text-muted">{finished ? "Konuşma · " : ""}Yazılı tur sesleri metinden üretilir.</li>
        {session.turns.map((turn) => (
          <li key={turn.id} className={turn.speaker === "employee" ? "flex justify-end" : ""}>
            <article
              className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                turn.speaker === "employee" ? "bg-ink text-paper" : "border border-line bg-card"
              }`}
            >
              <p className={`text-xs ${turn.speaker === "employee" ? "text-paper/70" : "text-muted"}`}>
                {turn.speaker === "employee" && !isOwner ? session.employee.display_name : speakerLabel[turn.speaker]}
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
      {!finished && isOwner && !phone && (
        <form
          className="shrink-0 border-t border-line pt-3"
          onSubmit={(event) => {
            event.preventDefault();
            void sendMessage();
          }}
        >
          <div className="py-3">
            <p className="mb-2 text-sm text-muted">
              {recording
                ? `Kayıtta ${formatClock(elapsed)} / 0:30 · bitirmek için tekrar bas`
                : sending
                ? "Gönderiliyor…"
                : jobBusy && job
                  ? jobLabel[job.status]
                  : job?.status === "error"
                    ? `${job.error?.message ?? ""}${noSpeech ? " İstersen yazarak da gönderebilirsin." : ""}`
                    : shouldEnd
                      ? "Müşteri konuşmayı kapattı. İstersen bitir."
                      : atLimit
                        ? "Tur doldu. Değerlendirme için bitir."
                        : canRecord
                          ? "Mikrofona basıp konuş ya da yaz, Enter ile gönder."
                          : "Yaz, Enter ile gönder."}
              {notice ? <span className="text-accent"> {notice}</span> : null}
              {job?.status === "error" && job.error?.retryable && (
                <button type="button" onClick={() => void retryJob()} className="ml-2 underline">
                  Tekrar dene
                </button>
              )}
            </p>
            <div className="flex items-end gap-2">
              {canRecord && (
                <button
                  type="button"
                  disabled={!canSend && !recording}
                  onClick={() => (recording ? stopRecording.current?.() : void sendRecording())}
                  aria-label={recording ? "Kaydı bitir ve gönder" : "Konuşarak cevap ver"}
                  title={recording ? "Kaydı bitir ve gönder" : "Konuşarak cevap ver"}
                  className={`grid h-12 w-12 shrink-0 place-items-center rounded-full text-paper disabled:opacity-40 ${
                    recording ? "bg-accent" : "bg-ink"
                  }`}
                >
                  <span className={recording ? "h-3.5 w-3.5 rounded-sm bg-paper" : "h-3.5 w-3.5 rounded-full bg-accent"} />
                </button>
              )}
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

      {reviewOpen && evaluation.data?.report && (
        <ReviewModal
          open={reviewOpen}
          onClose={() => setReviewOpen(false)}
          sessionId={sessionId}
          report={evaluation.data.report}
        />
      )}
    </div>
  );
}

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { allPages, api, isApiError } from "../api/client";
import type { Assignment, CreateSessionResponse, Health, Me, PracticeChannel, TrainingDetail } from "../api/types";
import { AssignModal } from "../components/AssignModal";
import { difficultyLabel, sectorLabel } from "../lib/labels";

export function TrainingPage() {
  const { trainingId = "" } = useParams();
  const [params] = useSearchParams();
  const assignmentId = params.get("assignment");
  const navigate = useNavigate();
  const [assignOpen, setAssignOpen] = useState(false);

  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/health") });
  // Ses desteklemeyen kurulumda (ör. Windows/Ollama) telefon provası açılmaz.
  const audioOk = health.data?.audio_input === true;
  const isManager = me.data?.user.role === "manager";

  const training = useQuery({
    queryKey: ["training", trainingId],
    queryFn: () => api<TrainingDetail>(`/trainings/${trainingId}`),
  });
  const assignments = useQuery({
    queryKey: ["assignments"],
    queryFn: () => allPages<Assignment>("/assignments?limit=100"),
    enabled: Boolean(assignmentId),
  });
  const assignedChannel = assignments.data?.items.find((item) => item.id === assignmentId)?.channel;

  const start = useMutation({
    mutationFn: (channel: PracticeChannel) =>
      api<CreateSessionResponse>("/sessions", {
        method: "POST",
        body: JSON.stringify({
          training_id: trainingId,
          channel: assignedChannel ?? channel,
          ...(assignmentId ? { assignment_id: assignmentId } : {}),
          client_request_id: crypto.randomUUID(),
        }),
      }),
    onSuccess: (created) => navigate(`/sessions/${created.session.id}`),
  });

  if (training.isLoading) return <p className="text-muted">Yükleniyor…</p>;
  if (training.isError || !training.data) {
    return (
      <div className="p-8 text-center space-y-3">
        <p className="text-accent">Eğitim bulunamadı.</p>
        <Link to="/" className="text-sm text-primary hover:underline">
          ← Eğitim listesine dön
        </Link>
      </div>
    );
  }

  const item = training.data;
  return (
    <div className="mx-auto max-w-3xl space-y-8 animate-in fade-in duration-200">
      <div className="flex items-center justify-between">
        <Link to="/" className="text-sm font-medium text-muted hover:text-ink transition-colors">
          ← Tüm Eğitimler
        </Link>
        {isManager && (
          <button
            type="button"
            onClick={() => setAssignOpen(true)}
            className="flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3.5 py-1.5 text-xs font-semibold text-primary hover:bg-primary hover:text-white transition-all"
          >
            <span>+</span>
            <span>Bu Eğitimi Çalışanlara Ata</span>
          </button>
        )}
      </div>

      <header className="space-y-3">
        <div className="flex items-center gap-2 text-xs text-muted">
          <span className="font-semibold text-primary">{sectorLabel(item.sector)}</span>
          <span>·</span>
          <span className="rounded-full bg-card-subtle px-2 py-0.5 border border-line">
            {difficultyLabel[item.difficulty]}
          </span>
          <span>·</span>
          <span>{item.estimated_minutes} dakika</span>
          <span>·</span>
          <span>En fazla {item.max_turns} tur</span>
        </div>

        <h1 className="font-serif text-3xl sm:text-4xl tracking-tight text-ink font-semibold">
          {item.title}
        </h1>
        <p className="text-base text-muted leading-relaxed">{item.summary}</p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        <article className="rounded-3xl border border-line bg-card p-6 shadow-xs">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">
            Müşteri Profili & Senaryo
          </p>
          <h2 className="mt-2 font-serif text-2xl text-ink font-medium">
            {item.customer.name}
          </h2>
          <p className="mt-2 text-sm text-muted leading-relaxed">
            {item.customer.context}
          </p>
        </article>

        <article className="rounded-3xl border border-line bg-card p-6 shadow-xs">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">
            Değerlendirme Ölçütleri ({item.rubric_dimensions.length} Boyut)
          </p>
          <ul className="mt-3 space-y-2.5 text-xs">
            {item.rubric_dimensions.map((dimension) => (
              <li key={dimension.id} className="border-b border-line/60 pb-2 last:border-0 last:pb-0">
                <span className="font-semibold text-ink">{dimension.name}:</span>{" "}
                <span className="text-muted">{dimension.description}</span>
              </li>
            ))}
          </ul>
        </article>
      </div>

      {start.isError && (
        <div className="rounded-2xl border border-accent/20 bg-accent-soft/50 p-4 text-xs text-accent">
          {isApiError(start.error) ? start.error.message : "Prova başlatılamadı."}
        </div>
      )}

      <div className="pt-2">
        <div className="flex flex-wrap gap-3">
          {assignedChannel !== "phone" && (
            <button
              type="button"
              disabled={start.isPending}
              onClick={() => start.mutate("message")}
              className="rounded-full bg-primary px-8 py-3 text-sm font-semibold text-white shadow-md hover:opacity-95 disabled:opacity-50"
            >
              {start.isPending ? "Hazırlanıyor…" : "Mesaj provası"}
            </button>
          )}
          {assignedChannel !== "message" && (
            <button
              type="button"
              disabled={start.isPending || !audioOk}
              title={audioOk ? undefined : "Bu kurulumda sesli cevap desteklenmiyor"}
              onClick={() => start.mutate("phone")}
              className="rounded-full border border-ink px-8 py-3 text-sm font-semibold disabled:opacity-50"
            >
              Telefon provası
            </button>
          )}
        </div>
        <p className="mt-2.5 text-xs text-muted">
          Mesaj provası yazılıdır. Telefon provası karşılıklı aramadır; sustuğunda söz müşteriye geçer.
          {!audioOk && " Bu kurulum sesli cevabı desteklemediği için telefon provası kapalı."}
        </p>
      </div>

      {/* Modal */}
      <AssignModal
        open={assignOpen}
        onClose={() => setAssignOpen(false)}
        defaultTrainingId={trainingId}
      />
    </div>
  );
}

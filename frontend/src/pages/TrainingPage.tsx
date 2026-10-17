import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, isApiError } from "../api/client";
import type { CreateSessionResponse, TrainingDetail } from "../api/types";
import { difficultyLabel, sectorLabel } from "../lib/labels";

export function TrainingPage() {
  const { trainingId = "" } = useParams();
  const [params] = useSearchParams();
  const assignmentId = params.get("assignment");
  const navigate = useNavigate();
  const training = useQuery({
    queryKey: ["training", trainingId],
    queryFn: () => api<TrainingDetail>(`/trainings/${trainingId}`),
  });
  const start = useMutation({
    mutationFn: () =>
      api<CreateSessionResponse>("/sessions", {
        method: "POST",
        body: JSON.stringify({
          training_id: trainingId,
          ...(assignmentId ? { assignment_id: assignmentId } : {}),
          client_request_id: crypto.randomUUID(),
        }),
      }),
    onSuccess: (created) => navigate(`/sessions/${created.session.id}`),
  });

  if (training.isLoading) return <p className="text-muted">Yükleniyor…</p>;
  if (training.isError || !training.data) {
    return (
      <p className="text-accent">
        Eğitim bulunamadı. <Link to="/">Geri dön</Link>
      </p>
    );
  }

  const item = training.data;
  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/" className="text-sm text-muted hover:text-ink">
        ← Eğitimler
      </Link>
      <p className="mt-6 text-sm text-muted">
        {sectorLabel(item.sector)} · {difficultyLabel[item.difficulty]} · {item.estimated_minutes} dk · en fazla{" "}
        {item.max_turns} cevap
      </p>
      <h1 className="mt-2 font-serif text-4xl tracking-tight">{item.title}</h1>
      <p className="mt-4 text-lg text-muted">{item.summary}</p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <article className="rounded-2xl border border-line bg-card p-5">
          <p className="text-sm text-muted">Karşındaki</p>
          <h2 className="mt-1 font-serif text-2xl">{item.customer.name}</h2>
          <p className="mt-2">{item.customer.context}</p>
        </article>
        <article className="rounded-2xl border border-line bg-card p-5">
          <p className="text-sm text-muted">Nelere bakılacak</p>
          <ul className="mt-2 space-y-2">
            {item.rubric_dimensions.map((dimension) => (
              <li key={dimension.id}>
                <span className="font-medium">{dimension.name}.</span>{" "}
                <span className="text-muted">{dimension.description}</span>
              </li>
            ))}
          </ul>
        </article>
      </div>

      {start.isError && (
        <p className="mt-6 text-sm text-accent">
          {isApiError(start.error) ? start.error.message : "Prova başlatılamadı."}
        </p>
      )}

      <button
        type="button"
        disabled={start.isPending}
        onClick={() => start.mutate()}
        className="mt-8 rounded-full bg-ink px-5 py-2.5 text-paper disabled:opacity-60"
      >
        {start.isPending ? "Hazırlanıyor…" : "Provayı başlat"}
      </button>
      <p className="mt-3 text-sm text-muted">Müşteri konuşarak başlar. Sen konuşarak ya da yazarak cevap verirsin.</p>
    </div>
  );
}

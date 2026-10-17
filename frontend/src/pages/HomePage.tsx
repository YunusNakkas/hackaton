import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { AssignmentPage, Me, TrainingPage } from "../api/types";
import { assignmentLabel, difficultyLabel, formatDue, sectorLabel } from "../lib/labels";

export function HomePage() {
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });
  const trainings = useQuery({
    queryKey: ["trainings"],
    queryFn: () => api<TrainingPage>("/trainings?limit=50"),
  });
  const assignments = useQuery({
    queryKey: ["assignments"],
    queryFn: () => api<AssignmentPage>("/assignments?limit=50"),
  });

  const first = me.data?.user.display_name.split(" ")[0];

  return (
    <div className="space-y-12">
      <header>
        <h1 className="font-serif text-4xl tracking-tight">Merhaba{first ? `, ${first}` : ""}</h1>
        <p className="mt-2 max-w-xl text-muted">
          Atanan provayı bitir ya da listeden bir senaryo seç. Müşteri önce yazar, sen yazarak cevap verirsin.
        </p>
      </header>

      <section>
        <h2 className="text-sm tracking-wide text-muted uppercase">Sana atanan</h2>
        {assignments.isLoading && <p className="mt-3 text-muted">Yükleniyor…</p>}
        {assignments.data && assignments.data.items.length === 0 && (
          <p className="mt-3 text-muted">Açık atama yok. Aşağıdan serbest prova başlatabilirsin.</p>
        )}
        <div className="mt-4 grid gap-3">
          {assignments.data?.items.map((item) => {
            const due = formatDue(item.due_at);
            const href =
              item.status === "completed" && item.completed_session_id
                ? `/sessions/${item.completed_session_id}`
                : `/trainings/${item.training.id}?assignment=${item.id}`;
            return (
              <Link
                key={item.id}
                to={href}
                className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-card px-5 py-4 hover:border-ink/25"
              >
                <div>
                  <p className="text-sm text-muted">
                    {sectorLabel(item.training.sector)} · {assignmentLabel[item.status]}
                    {due ? ` · ${due}` : ""}
                  </p>
                  <p className="mt-0.5 text-lg">{item.training.title}</p>
                </div>
                <span className="text-sm">{item.status === "completed" ? "Rapor" : "Başla"}</span>
              </Link>
            );
          })}
        </div>
      </section>

      <section>
        <h2 className="text-sm tracking-wide text-muted uppercase">Eğitimler</h2>
        {trainings.isError && <p className="mt-3 text-accent">Liste alınamadı.</p>}
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {trainings.data?.items.map((training) => (
            <Link
              key={training.id}
              to={`/trainings/${training.id}`}
              className="rounded-2xl border border-line bg-card p-5 hover:border-ink/25"
            >
              <p className="text-sm text-muted">
                {sectorLabel(training.sector)} · {difficultyLabel[training.difficulty]} · {training.estimated_minutes} dk
              </p>
              <h3 className="mt-1 font-serif text-2xl leading-tight">{training.title}</h3>
              <p className="mt-2 text-muted">{training.summary}</p>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}

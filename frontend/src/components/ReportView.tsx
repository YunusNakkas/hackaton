import type { EvaluationReport } from "../api/types";
import { flagLabel } from "../lib/labels";

function ScoreMarks({ score }: { score: number | null }) {
  return (
    <div className="flex gap-1" aria-hidden>
      {[0, 1, 2, 3].map((index) => (
        <span
          key={index}
          className={`h-1.5 w-6 rounded-full ${score != null && index < score ? "bg-pine" : "bg-line"}`}
        />
      ))}
    </div>
  );
}

export function ReportView({ report }: { report: EvaluationReport }) {
  const total = report.effective_total;
  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-5">
        <div>
          <p className="text-sm text-muted">Sonuç</p>
          <p className="font-serif text-4xl tracking-tight">
            {total.complete && total.score != null ? (
              <>
                {total.score}
                <span className="text-2xl text-muted"> / {total.max_score}</span>
              </>
            ) : (
              <span className="text-3xl">
                {total.scored_dimensions}
                <span className="text-xl text-muted"> / {total.total_dimensions} boyut</span>
              </span>
            )}
          </p>
        </div>
        {report.model_run.runtime === "stub" && (
          <p className="text-sm text-warn">Puanlar sahte modelden. Gerçek değerlendirme değil.</p>
        )}
      </div>

      {report.flags.length > 0 && (
        <ul className="space-y-1 text-sm text-warn">
          {report.flags.map((flag) => (
            <li key={flag}>{flagLabel(flag)}</li>
          ))}
        </ul>
      )}

      <div className="space-y-4">
        {report.dimensions.map((dimension) => (
          <article key={dimension.dimension_id} className="rounded-2xl border border-line bg-card p-4">
            <div className="flex items-center justify-between gap-4">
              <h3 className="font-medium">{dimension.name}</h3>
              <div className="flex items-center gap-3">
                <ScoreMarks score={dimension.score} />
                <span className="w-10 text-right text-sm tabular-nums text-muted">
                  {dimension.insufficient_evidence || dimension.score == null ? "—" : `${dimension.score}/4`}
                </span>
              </div>
            </div>
            <p className="mt-2 text-muted">{dimension.rationale}</p>
            {dimension.evidence.length > 0 && (
              <ul className="mt-3 space-y-2">
                {dimension.evidence.map((item) => (
                  <li key={`${item.turn_id}-${item.quote}`} className="border-l-2 border-line pl-3 text-sm">
                    <span className="text-ink">“{item.quote}”</span>
                    {!item.verified && (
                      <span className="mt-0.5 block text-warn">Bu alıntı transkriptte doğrulanamadı.</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </article>
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <List title="İyi giden" items={report.strengths} />
        <List title="Sonraki provada" items={report.improvements} />
      </div>

      {report.practice_drill && (
        <article className="rounded-2xl bg-pine-soft p-5">
          <p className="text-sm text-pine">Kısa alıştırma</p>
          <h3 className="mt-1 font-serif text-2xl">{report.practice_drill.title}</h3>
          <p className="mt-2">{report.practice_drill.instructions}</p>
          {report.practice_drill.example_phrases && report.practice_drill.example_phrases.length > 0 && (
            <ul className="mt-3 space-y-1 text-sm">
              {report.practice_drill.example_phrases.map((phrase) => (
                <li key={phrase}>“{phrase}”</li>
              ))}
            </ul>
          )}
        </article>
      )}
    </section>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h3 className="text-sm text-muted">{title}</h3>
      <ul className="mt-2 space-y-1.5">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

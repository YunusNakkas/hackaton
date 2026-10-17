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

export function ReportView({
  report,
  onPracticeAgain,
}: {
  report: EvaluationReport;
  onPracticeAgain?: () => void;
}) {
  const total = report.effective_total;
  const adjustments = new Map(report.manager_review?.adjustments.map(a => [a.dimension_id, a]) ?? []);
  const dimensions = report.dimensions.map(d => {
    const adjustment = adjustments.get(d.dimension_id);
    return adjustment ? { ...d, score: adjustment.score, insufficient_evidence: adjustment.score === null } : d;
  });
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

      {report.manager_review && <div className="rounded-2xl border border-line bg-pine-soft p-4 text-sm"><p className="font-semibold text-pine">Yönetici incelemesi: {report.manager_review.decision === "approved" ? "Onaylandı" : "Puanlar düzeltildi"}</p><p className="mt-1 text-muted">{report.manager_review.reviewer.display_name} · {new Date(report.manager_review.created_at).toLocaleString("tr-TR")}</p>{report.manager_review.comment && <p className="mt-2 whitespace-pre-wrap">{report.manager_review.comment}</p>}</div>}

      {report.flags.length > 0 && (
        <ul className="space-y-1 text-sm text-warn">
          {report.flags.map((flag) => (
            <li key={flag}>{flagLabel(flag)}</li>
          ))}
        </ul>
      )}

      <div className="space-y-4">
        {dimensions.map((dimension) => (
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
            {(dimension.insufficient_evidence || dimension.score == null) && (
              <p className="mt-2 text-sm text-warn">Bu boyut için yeterli kanıt yok.</p>
            )}
            <p className="mt-2 text-muted">{dimension.rationale}</p>
            {adjustments.has(dimension.dimension_id) && <p className="mt-2 rounded-xl bg-primary/10 p-3 text-sm"><strong>Yönetici düzeltmesi:</strong> Model puanı {adjustments.get(dimension.dimension_id)?.original_score ?? "—"} → {dimension.score ?? "Puan yok"}. {adjustments.get(dimension.dimension_id)?.reason}</p>}
            {dimension.evidence.length > 0 && (
              <ul className="mt-3 space-y-2">
                {dimension.evidence.map((item) => (
                  <li key={`${item.turn_id}-${item.quote}`} className="border-l-2 border-line pl-3 text-sm">
                    <span className="text-ink">“{item.quote}”</span>
                    <span className={`ml-2 rounded-full px-2 py-0.5 text-xs ${item.verified ? "bg-pine-soft text-pine" : "bg-warn-soft text-warn"}`}>{item.verified ? "Doğrulandı" : "Doğrulanamadı"}</span>
                    {!item.verified && (
                      <span className="mt-0.5 block text-warn">Bu alıntı transkriptte doğrulanamadı.</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {dimension.policy_refs.length > 0 && <div className="mt-4 space-y-2 border-t border-line pt-3"><p className="text-xs font-semibold text-muted">İşletme kuralları</p>{dimension.policy_refs.map((policy, index) => <div key={`${policy.policy_id}-${index}`} className="text-sm"><p className="font-medium">{policy.title} <span className={`ml-2 text-xs ${policy.verified ? "text-pine" : "text-warn"}`}>{policy.verified ? "Doğrulandı" : "Doğrulanamadı"}</span></p>{policy.quote && <p className="mt-1 text-muted">“{policy.quote}”</p>}</div>)}</div>}
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
          {onPracticeAgain && (
            <button
              type="button"
              onClick={onPracticeAgain}
              className="mt-4 rounded-full bg-ink px-4 py-2 text-sm text-paper"
            >
              Tekrar dene
            </button>
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

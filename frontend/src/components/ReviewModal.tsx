import { ModalFrame } from "./ModalFrame";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, isApiError } from "../api/client";
import type { CreateReviewRequest, DimensionAdjustment, EvaluationReport, Review } from "../api/types";

interface ReviewModalProps {
  open: boolean;
  onClose: () => void;
  sessionId: string;
  report: EvaluationReport;
}

export function ReviewModal({ open, onClose, sessionId, report }: ReviewModalProps) {
  const queryClient = useQueryClient();
  const [decision, setDecision] = useState<"approved" | "adjusted">(report.manager_review?.decision ?? "approved");
  const [comment, setComment] = useState(report.manager_review?.comment ?? "");
  const [adjustments, setAdjustments] = useState<Record<string, { score: number | null; reason: string }>>(
    Object.fromEntries((report.manager_review?.adjustments ?? []).map(a => [a.dimension_id, { score: a.score, reason: a.reason }])),
  );
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const reviewMutation = useMutation({
    mutationFn: (body: CreateReviewRequest) =>
      api<Review>(`/admin/sessions/${sessionId}/reviews`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
      void queryClient.invalidateQueries({ queryKey: ["evaluation", sessionId] });
      void queryClient.invalidateQueries({ queryKey: ["admin-employee"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-sessions"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
      onClose();
    },
    onError: (err) => {
      setErrorMsg(isApiError(err) ? err.message : "İnceleme kaydedilemedi.");
    },
  });

  if (!open) return null;

  const handleAdjustToggle = (dimId: string, currentScore: number | null) => {
    setAdjustments((prev) => {
      const next = { ...prev };
      if (next[dimId]) {
        delete next[dimId];
      } else {
        next[dimId] = {
          score: currentScore ?? 2,
          reason: "",
        };
      }
      return next;
    });
  };

  const handleScoreChange = (dimId: string, score: number | null) => {
    setAdjustments((prev) => ({
      ...prev,
      [dimId]: { ...prev[dimId], score },
    }));
  };

  const handleReasonChange = (dimId: string, reason: string) => {
    setAdjustments((prev) => ({
      ...prev,
      [dimId]: { ...prev[dimId], reason },
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    const adjList: DimensionAdjustment[] = [];
    if (decision === "adjusted") {
      const keys = Object.keys(adjustments);
      if (keys.length === 0) {
        setErrorMsg("Puanı düzeltmek için en az bir boyut seçmelisiniz.");
        return;
      }
      for (const k of keys) {
        const item = adjustments[k];
        if (!item.reason || item.reason.trim().length < 10) {
          setErrorMsg("Düzeltilen her boyut için en az 10 karakterlik bir gerekçe girmelisiniz.");
          return;
        }
        adjList.push({
          dimension_id: k,
          score: item.score,
          reason: item.reason.trim(),
        });
      }
    }

    reviewMutation.mutate({
      decision,
      adjustments: decision === "adjusted" ? adjList : [],
      comment: comment.trim(),
    });
  };

  return (
    <ModalFrame>
      <div className="w-full max-w-2xl max-h-[90vh] flex flex-col rounded-3xl border border-line bg-card shadow-2xl overflow-hidden animate-in fade-in duration-200">
        <div className="flex items-center justify-between border-b border-line px-6 py-4">
          <div>
            <h2 className="font-serif text-2xl tracking-tight text-ink">Yönetici İncelemesi</h2>
            <p className="text-sm text-muted">
              Modelin değerlendirmesini onaylayın veya boyut puanlarını gerekçesiyle güncelleyin.
            </p>
          </div>
          <button
            type="button"
            aria-label="Kapat"
            onClick={onClose}
            className="rounded-full p-2 text-muted hover:bg-card-subtle hover:text-ink transition-colors"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-6">
          {errorMsg && (
            <div className="rounded-2xl border border-accent/20 bg-accent-soft/50 p-4 text-sm text-accent">
              {errorMsg}
            </div>
          )}

          {/* Karar Seçimi */}
          <div>
            <label className="block text-sm font-medium text-ink mb-2">İnceleme Kararı</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => {
                  setDecision("approved");
                  setAdjustments({});
                }}
                className={`p-4 rounded-2xl border text-left transition-all ${
                  decision === "approved"
                    ? "border-primary bg-primary/10 text-ink shadow-xs"
                    : "border-line bg-card-subtle text-muted hover:text-ink hover:border-ink/20"
                }`}
              >
                <p className="font-semibold text-ink">✓ Onayla</p>
                <p className="mt-1 text-xs text-muted">Modelin puan ve tespitleri geçerli kabul edilir.</p>
              </button>

              <button
                type="button"
                onClick={() => setDecision("adjusted")}
                className={`p-4 rounded-2xl border text-left transition-all ${
                  decision === "adjusted"
                    ? "border-primary bg-primary/10 text-ink shadow-xs"
                    : "border-line bg-card-subtle text-muted hover:text-ink hover:border-ink/20"
                }`}
              >
                <p className="font-semibold text-ink">✎ Puanları Düzelt</p>
                <p className="mt-1 text-xs text-muted">Boyut puanlarını manuel olarak düzenleyin.</p>
              </button>
            </div>
          </div>

          {/* Düzeltme Alanı */}
          {decision === "adjusted" && (
            <div className="space-y-4 rounded-2xl border border-line bg-card-subtle p-4">
              <h3 className="text-sm font-semibold text-ink">Boyut Puanlarını Güncelleyin</h3>
              <p className="text-xs text-muted">
                Düzeltmek istediğiniz boyutun yanındaki onay kutusunu işaretleyin, yeni puanı ve gerekçeyi yazın.
              </p>

              <div className="space-y-3">
                {report.dimensions.map((dim) => {
                  const isAdjusted = Boolean(adjustments[dim.dimension_id]);
                  const adj = adjustments[dim.dimension_id];
                  return (
                    <div
                      key={dim.dimension_id}
                      className={`p-4 rounded-2xl border transition-colors ${
                        isAdjusted ? "border-primary/40 bg-card" : "border-line bg-card/60"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={isAdjusted}
                            onChange={() => handleAdjustToggle(dim.dimension_id, dim.score)}
                            className="h-4 w-4 rounded accent-primary"
                          />
                          <span className="font-medium text-sm text-ink">{dim.name}</span>
                        </label>
                        <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-card-subtle border border-line text-muted">
                          Orijinal: {dim.score ?? "-"} / {dim.max_score}
                        </span>
                      </div>

                      {isAdjusted && (
                        <div className="mt-4 pt-3 border-t border-line space-y-3">
                          <div>
                            <label className="block text-xs font-medium text-muted mb-1">
                              Yeni Puan: <strong className="text-ink">{adj.score} / {dim.max_score}</strong>
                            </label>
                            <input
                              type="range"
                              min={0}
                              max={dim.max_score}
                              value={adj.score ?? 0}
                              disabled={adj.score === null}
                              onChange={(e) => handleScoreChange(dim.dimension_id, Number(e.target.value))}
                              className="w-full accent-primary"
                            />
                            <label className="mt-2 flex items-center gap-2 text-xs text-muted"><input type="checkbox" checked={adj.score === null} onChange={e => handleScoreChange(dim.dimension_id, e.target.checked ? null : (dim.score ?? 2))} />Yetersiz kanıt / puan yok</label>
                            <div className="flex justify-between text-[11px] text-muted">
                              <span>0 (Yetersiz)</span>
                              <span>2 (Orta)</span>
                              <span>4 (Mükemmel)</span>
                            </div>
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-muted mb-1">
                              Düzeltme Gerekçesi (En az 10 karakter)
                            </label>
                            <input aria-label="Düzeltme Gerekçesi (En az 10 karakter)"
                              type="text"
                              required
                              maxLength={1000}
                              placeholder="Örn: Çalışan iade politikasını tam olarak doğru aktardı..."
                              value={adj.reason}
                              onChange={(e) => handleReasonChange(dim.dimension_id, e.target.value)}
                              className="w-full rounded-xl border border-line bg-card-subtle px-3 py-2 text-xs text-ink outline-none focus:border-primary transition-colors"
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Yönetici Yorumu */}
          <div>
            <label className="block text-sm font-medium text-ink mb-1">
              Yönetici Geri Bildirimi / Notu (Opsiyonel)
            </label>
            <textarea aria-label="Yönetici Geri Bildirimi / Notu (Opsiyonel)"
              rows={3}
              maxLength={2000}
              placeholder="Çalışanın performansına dair inceleme notu ekleyin…"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              className="w-full rounded-2xl border border-line bg-card-subtle p-3 text-sm text-ink outline-none focus:border-primary transition-colors resize-none"
            />
          </div>

          <div className="pt-2 flex items-center justify-end gap-3 border-t border-line">
            <button
              type="button"
              onClick={onClose}
              disabled={reviewMutation.isPending}
              className="rounded-full border border-line px-5 py-2.5 text-sm text-muted hover:text-ink transition-colors"
            >
              Vazgeç
            </button>
            <button
              type="submit"
              disabled={reviewMutation.isPending}
              className="rounded-full bg-primary px-6 py-2.5 text-sm font-medium text-white shadow-sm hover:opacity-95 disabled:opacity-50 transition-opacity"
            >
              {reviewMutation.isPending ? "Kaydediliyor…" : "İncelemeyi Kaydet"}
            </button>
          </div>
        </form>
      </div>
    </ModalFrame>
  );
}

import { ModalFrame } from "./ModalFrame";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { EmployeeDetail } from "../api/types";
import { assignmentLabel, formatDue, sectorLabel } from "../lib/labels";

interface EmployeeDetailModalProps {
  employeeId: string | null;
  onClose: () => void;
  onOpenAssign: (employeeId: string) => void;
}

export function EmployeeDetailModal({
  employeeId,
  onClose,
  onOpenAssign,
}: EmployeeDetailModalProps) {
  const queryClient = useQueryClient();

  const employee = useQuery({
    queryKey: ["admin-employee", employeeId],
    queryFn: () => api<EmployeeDetail>(`/admin/employees/${employeeId}`),
    enabled: Boolean(employeeId),
  });

  const deactivateMutation = useMutation({
    mutationFn: (id: string) =>
      api(`/admin/employees/${id}/deactivate`, { method: "POST" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-employees"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-employees-active"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-employee", employeeId] });
      void queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
    },
  });

  if (!employeeId) return null;

  const data = employee.data;

  return (
    <ModalFrame>
      <div className="w-full max-w-2xl max-h-[90vh] flex flex-col rounded-3xl border border-line bg-card shadow-2xl overflow-hidden animate-in fade-in duration-200">
        <div className="flex items-center justify-between border-b border-line px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-lg">
              {data?.display_name.charAt(0) || "?"}
            </div>
            <div>
              <h2 className="font-serif text-2xl tracking-tight text-ink flex items-center gap-2">
                {data?.display_name}
                {data && (
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-sans font-medium ${
                      data.active
                        ? "bg-pine-soft text-pine"
                        : "bg-accent-soft text-accent"
                    }`}
                  >
                    {data.active ? "Aktif" : "Pasif"}
                  </span>
                )}
              </h2>
              <p className="text-sm text-muted">{data?.email}</p>
            </div>
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

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {deactivateMutation.error && <p role="alert" className="text-accent">{deactivateMutation.error.message}</p>}
          {employee.isLoading ? (
            <p className="text-muted">Yükleniyor…</p>
          ) : !data ? (
            <p className="text-accent">Çalışan bilgisi alınamadı.</p>
          ) : (
            <>
              {/* İstatistikler */}
              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-2xl border border-line bg-card-subtle p-4 text-center">
                  <p className="text-xs text-muted uppercase tracking-wider">Açık Atama</p>
                  <p className="mt-1 font-serif text-2xl text-ink">{data.open_assignments}</p>
                </div>
                <div className="rounded-2xl border border-line bg-card-subtle p-4 text-center">
                  <p className="text-xs text-muted uppercase tracking-wider">Tamamlanan Prova</p>
                  <p className="mt-1 font-serif text-2xl text-pine">{data.completed_sessions}</p>
                </div>
                <div className="rounded-2xl border border-line bg-card-subtle p-4 text-center">
                  <p className="text-xs text-muted uppercase tracking-wider">Kayıt Tarihi</p>
                  <p className="mt-1 text-sm font-medium text-ink">
                    {new Date(data.created_at).toLocaleDateString("tr-TR")}
                  </p>
                </div>
              </div>

              {/* Hızlı İşlem Düğmeleri */}
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  disabled={!data.active}
                  onClick={() => {
                    onClose();
                    onOpenAssign(data.id);
                  }}
                  className="rounded-full bg-primary px-4 py-2 text-sm font-medium text-white hover:opacity-95 transition-opacity"
                >
                  + Yeni Eğitim Ata
                </button>
                {data.active && (
                  <button
                    type="button"
                    disabled={deactivateMutation.isPending}
                    onClick={() => {
                      if (confirm(`${data.display_name} adlı çalışanın hesabını askıya almak istediğinize emin misiniz?`)) {
                        deactivateMutation.mutate(data.id);
                      }
                    }}
                    className="rounded-full border border-line px-4 py-2 text-sm text-accent hover:bg-accent-soft/30 transition-colors"
                  >
                    {deactivateMutation.isPending ? "İşleniyor…" : "Hesabı Askıya Al"}
                  </button>
                )}
              </div>

              {/* Atanan Eğitimler */}
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted mb-3">
                  Atanan Eğitimler ({data.assignments.length})
                </h3>
                {data.assignments.length === 0 ? (
                  <p className="text-sm text-muted">Henüz atanmış bir eğitim yok.</p>
                ) : (
                  <div className="space-y-2">
                    {data.assignments.map((a) => {
                      const due = formatDue(a.due_at);
                      return (
                        <div
                          key={a.id}
                          className="flex items-center justify-between p-3.5 rounded-2xl border border-line bg-card-subtle text-sm"
                        >
                          <div>
                            <p className="font-medium text-ink">{a.training.title}</p>
                            <p className="text-xs text-muted">
                              {sectorLabel(a.training.sector)} · Durum:{" "}
                              <span className="font-medium text-ink">
                                {assignmentLabel[a.status]}
                              </span>
                              {due ? ` · ${due}` : ""}
                            </p>
                          </div>
                          {a.completed_session_id && (
                            <Link
                              to={`/sessions/${a.completed_session_id}`}
                              className="text-xs font-medium text-primary hover:underline"
                            >
                              Rapora Git →
                            </Link>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Son Oturumlar */}
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted mb-3">
                  Son Provalar ({data.recent_sessions.length})
                </h3>
                {data.recent_sessions.length === 0 ? (
                  <p className="text-sm text-muted">Henüz yapılmış bir prova bulunmuyor.</p>
                ) : (
                  <div className="space-y-2">
                    {data.recent_sessions.map((s) => (
                      <Link
                        key={s.id}
                        to={`/sessions/${s.id}`}
                        className="flex items-center justify-between p-3.5 rounded-2xl border border-line bg-card-subtle hover:border-primary/40 transition-colors text-sm"
                      >
                        <div>
                          <p className="font-medium text-ink">{s.training.title}</p>
                          <p className="text-xs text-muted">
                            {new Date(s.started_at).toLocaleDateString("tr-TR")} · {s.employee_turn_count} tur
                          </p>
                        </div>
                        <div className="text-right">
                          {s.total ? (
                            <p className="font-serif text-base font-semibold text-primary">
                              {s.total.score ?? "-"} / {s.total.max_score}
                            </p>
                          ) : (
                            <span className="text-xs text-muted">Devam ediyor</span>
                          )}
                          <span className="text-xs text-muted">İncele →</span>
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </ModalFrame>
  );
}

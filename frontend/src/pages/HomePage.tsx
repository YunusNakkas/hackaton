import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, allPages, isApiError } from "../api/client";
import type { AdminOverview, Assignment, Me, SessionSummary, TrainingSummary } from "../api/types";
import { assignmentLabel, channelLabel, difficultyLabel, formatDue, sectorLabel, summaryOutcome } from "../lib/labels";

export function HomePage() {
  const queryClient = useQueryClient();
  const [dropping, setDropping] = useState<string | null>(null);
  const [dropError, setDropError] = useState<string | null>(null);
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });
  const isManager = me.data?.user.role === "manager";

  const trainings = useQuery({
    queryKey: ["trainings"],
    queryFn: () => allPages<TrainingSummary>("/trainings?limit=100"),
  });

  const assignments = useQuery({
    queryKey: ["assignments"],
    queryFn: () => allPages<Assignment>("/assignments?limit=100"),
  });

  const history = useQuery({
    queryKey: ["my-sessions"],
    queryFn: () => api<{ items: SessionSummary[] }>("/sessions?limit=20"),
  });

  const adminOverview = useQuery({
    queryKey: ["admin-overview"],
    enabled: isManager,
    queryFn: () => api<AdminOverview>("/admin/overview"),
  });

  async function dropSession(id: string) {
    setDropping(id);
    setDropError(null);
    try {
      await api(`/sessions/${id}/abandon`, { method: "POST" });
      await queryClient.invalidateQueries({ queryKey: ["my-sessions"] });
      await queryClient.invalidateQueries({ queryKey: ["assignments"] });
    } catch (error) {
      setDropError(isApiError(error) ? error.message : "Prova bırakılamadı.");
    } finally {
      setDropping(null);
    }
  }

  const first = me.data?.user.display_name.split(" ")[0];

  return (
    <div className="space-y-10 animate-in fade-in duration-300">
      {/* Karşılama Başlığı */}
      <header className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl sm:text-4xl tracking-tight text-ink font-semibold">
            Merhaba{first ? `, ${first}` : ""}
          </h1>
          <p className="mt-1.5 max-w-xl text-sm sm:text-base text-muted">
            {isManager
              ? "Yönetici olarak çalışanlarınıza eğitim atayabilir, provaları denetleyebilir veya katalogdaki senaryoları test edebilirsiniz."
              : "Mesaj görevinde yazarsın. Telefon görevinde müşteri arar, sen konuşursun; sustuğunda söz ona geçer."}
          </p>
        </div>

        {isManager && (
          <Link
            to="/admin"
            className="flex items-center gap-2 self-start sm:self-auto rounded-full bg-primary/10 border border-primary/20 px-4 py-2 text-xs font-semibold text-primary hover:bg-primary hover:text-white transition-all shadow-xs"
          >
            <span>Yönetici Paneline Git</span>
            <span>→</span>
          </Link>
        )}
      </header>

      {/* Yönetici için Hızlı Bakış Kartı */}
      {isManager && adminOverview.data && (
        <section className="rounded-3xl border border-primary/25 bg-gradient-to-r from-card to-card-subtle p-6 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-primary">
                Yönetici Durum Özeti
              </p>
              <div className="mt-3 flex flex-wrap gap-4 text-sm text-ink">
                <div>
                  <span className="font-serif text-2xl font-bold text-ink mr-1.5">
                    {adminOverview.data.active_employees}
                  </span>
                  <span className="text-xs text-muted">Çalışan</span>
                </div>
                <div className="border-l border-line pl-4">
                  <span className="font-serif text-2xl font-bold text-primary mr-1.5">
                    {adminOverview.data.open_assignments}
                  </span>
                  <span className="text-xs text-muted">Açık Atama</span>
                </div>
                <div className="border-l border-line pl-4">
                  <span className="font-serif text-2xl font-bold text-ink mr-1.5">
                    {adminOverview.data.active_sessions}
                  </span>
                  <span className="text-xs text-muted">Süren prova</span>
                </div>
                <div className="border-l border-line pl-4">
                  <span className="font-serif text-2xl font-bold text-warn mr-1.5">
                    {adminOverview.data.sessions_pending_review}
                  </span>
                  <span className="text-xs text-muted">İnceleme Bekleyen</span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Link
                to="/admin"
                className="rounded-full bg-primary px-4 py-2 text-xs font-semibold text-white hover:opacity-95 transition-opacity"
              >
                Yönetici Paneli & Atama Yap →
              </Link>
            </div>
          </div>
        </section>
      )}

      {/* Çalışana Atanan Eğitimler */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">
            {isManager ? "Senin İçin Atananlar" : "Sana Atanan Eğitimler"}
          </h2>
          {assignments.data && (
            <span className="text-xs text-muted">
              {assignments.data.items.length} atama
            </span>
          )}
        </div>

        {assignments.isLoading && <p className="text-sm text-muted">Atamalar yükleniyor…</p>}
        {assignments.data && assignments.data.items.length === 0 && (
          <div className="rounded-2xl border border-line bg-card p-5 text-sm text-muted">
            Açık bir zorunlu atamanız bulunmuyor. Aşağıdaki katalogdan serbest prova başlatabilirsiniz.
          </div>
        )}

        <div className="grid gap-3">
          {assignments.data?.items.map((item) => {
            const due = formatDue(item.due_at);
            const isCompleted = item.status === "completed";
            const href =
              isCompleted && item.completed_session_id
                ? `/sessions/${item.completed_session_id}`
                : `/trainings/${item.training.id}?assignment=${item.id}`;
            return (
              <Link
                key={item.id}
                to={href}
                className="group flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-line bg-card p-5 hover:border-primary/40 hover:shadow-sm transition-all"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-xs text-muted">
                    <span className="font-medium text-primary">
                      {sectorLabel(item.training.sector)} · {item.channel === "phone" ? "Telefon" : "Mesaj"}
                    </span>
                    <span>·</span>
                    <span
                      className={`font-medium ${
                        isCompleted
                          ? "text-pine"
                          : item.status === "in_progress"
                            ? "text-primary"
                            : "text-warn"
                      }`}
                    >
                      {assignmentLabel[item.status]}
                    </span>
                    {due && (
                      <>
                        <span>·</span>
                        <span className="text-muted">{due}</span>
                      </>
                    )}
                  </div>
                  <h3 className="text-lg font-semibold text-ink group-hover:text-primary transition-colors">
                    {item.training.title}
                  </h3>
                  <p className="text-xs text-muted">{item.training.summary}</p>
                </div>

                <div className="flex items-center gap-3">
                  <span
                    className={`rounded-full px-4 py-2 text-xs font-semibold transition-all ${
                      isCompleted
                        ? "border border-pine/30 bg-pine-soft text-pine"
                        : "bg-primary text-white shadow-xs group-hover:scale-105"
                    }`}
                  >
                    {isCompleted ? "Sonuç Raporunu Gör" : item.channel === "phone" ? "Aramayı aç" : "Mesaja gir"}
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">Geçmiş provalar</h2>
        {history.isLoading && <p className="text-sm text-muted">Yükleniyor…</p>}
        {history.data && history.data.items.length === 0 && (
          <p className="text-sm text-muted">Henüz prova yok.</p>
        )}
        {dropError && <p className="text-sm text-accent">{dropError}</p>}
        <div className="grid gap-3">
          {history.data?.items.map((item) => {
            const canDrop = item.status === "active" && item.employee_turn_count === 0;
            return (
              <div
                key={item.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-line bg-card px-5 py-4"
              >
                <Link to={`/sessions/${item.id}`} className="min-w-0 flex-1 hover:text-primary">
                  <p className="text-xs text-muted">
                    {sectorLabel(item.training.sector)} · {channelLabel(item.channel)} · {new Date(item.started_at).toLocaleString("tr-TR")}
                  </p>
                  <p className="mt-0.5 text-lg">{item.training.title}</p>
                </Link>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-semibold text-primary">{summaryOutcome(item)}</span>
                  {canDrop && (
                    <button
                      type="button"
                      disabled={dropping === item.id}
                      onClick={() => void dropSession(item.id)}
                      className="rounded-full border border-line px-3 py-1 text-xs text-muted hover:text-ink disabled:opacity-40"
                    >
                      {dropping === item.id ? "Bırakılıyor" : "Bırak"}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Tüm Eğitimler Kataloğu */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">
            Tüm Eğitim Senaryoları Kataloğu
          </h2>
          {trainings.data && (
            <span className="text-xs text-muted">{trainings.data.items.length} senaryo</span>
          )}
        </div>

        {trainings.isError && <p className="text-sm text-accent">Katalog alınamadı.</p>}

        <div className="grid gap-4 sm:grid-cols-2">
          {trainings.data?.items.map((training) => (
            <Link
              key={training.id}
              to={`/trainings/${training.id}`}
              className="group rounded-3xl border border-line bg-card p-6 hover:border-primary/40 hover:shadow-sm transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between text-xs text-muted mb-2">
                  <span className="font-medium text-primary">
                    {sectorLabel(training.sector)}
                  </span>
                  <span className="rounded-full bg-card-subtle px-2 py-0.5 border border-line text-muted">
                    {difficultyLabel[training.difficulty]} · {training.estimated_minutes} dk
                  </span>
                </div>

                <h3 className="font-serif text-xl font-semibold leading-tight text-ink group-hover:text-primary transition-colors">
                  {training.title}
                </h3>
                <p className="mt-2 text-xs sm:text-sm text-muted line-clamp-3">
                  {training.summary}
                </p>
              </div>

              <div className="mt-5 pt-3 border-t border-line flex items-center justify-between text-xs">
                <span className="text-muted">En fazla {training.max_turns} tur konuşma</span>
                <span className="font-semibold text-primary group-hover:translate-x-0.5 transition-transform">
                  İncele & Başla →
                </span>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}

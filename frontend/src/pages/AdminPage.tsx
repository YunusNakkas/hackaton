import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, allPages, isApiError } from "../api/client";
import type {
  AdminOverview,
  EvaluationEnvelope,
  Employee, SessionSummary, TrainingSummary, TrainingDraft,
} from "../api/types";
import { DraftEditor } from "../components/DraftEditor";
import { DraftJobStatus } from "../components/DraftJobStatus";
import { AssignModal } from "../components/AssignModal";
import { CreateDraftModal } from "../components/CreateDraftModal";
import { CreateEmployeeModal } from "../components/CreateEmployeeModal";
import { EmployeeDetailModal } from "../components/EmployeeDetailModal";
import { ReviewModal } from "../components/ReviewModal";
import { channelLabel, evaluationLabel, sectorLabel, summaryOutcome } from "../lib/labels";

type AdminTab = "overview" | "employees" | "reviews" | "drafts";

export function AdminPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<AdminTab>("overview");

  // Modals state
  const [editingDraftId, setEditingDraftId] = useState<string | null>(null);
  const [assignTrainingId, setAssignTrainingId] = useState<string | undefined>();
  const [employeeFilter, setEmployeeFilter] = useState("");
  const [sessionEmployee, setSessionEmployee] = useState("");
  const [sessionTraining, setSessionTraining] = useState("");
  const [evalFilter, setEvalFilter] = useState("");
  const [sessionFrom, setSessionFrom] = useState("");
  const [sessionTo, setSessionTo] = useState("");
  const [draftFilter, setDraftFilter] = useState("");
  const [feedback, setFeedback] = useState("");
  const [assignOpen, setAssignOpen] = useState(false);
  const [createEmployeeOpen, setCreateEmployeeOpen] = useState(false);
  const [createDraftOpen, setCreateDraftOpen] = useState(false);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string | null>(null);
  const [preselectedEmpIdForAssign, setPreselectedEmpIdForAssign] = useState<string | undefined>();
  const [reviewingSessionId, setReviewingSessionId] = useState<string | null>(null);

  // Queries
  const overview = useQuery({
    queryKey: ["admin-overview"],
    queryFn: () => api<AdminOverview>("/admin/overview"),
    refetchInterval: 15000,
  });

  const [employeeSearch, setEmployeeSearch] = useState("");
  const employees = useQuery({
    queryKey: ["admin-employees", employeeSearch, employeeFilter],
    queryFn: () => {
      const q = employeeSearch.trim() ? `&q=${encodeURIComponent(employeeSearch.trim())}` : "";
      return allPages<Employee>(`/admin/employees?limit=100${q}${employeeFilter ? `&active=${employeeFilter}` : ""}`);
    },
  });

  const [reviewFilter, setReviewFilter] = useState<"pending" | "reviewed" | "not_required" | "all">("pending");
  const sessions = useQuery({
    queryKey: ["admin-sessions", reviewFilter, sessionEmployee, sessionTraining, evalFilter, sessionFrom, sessionTo],
    queryFn: () => {
      const filterParam =
        reviewFilter === "all" ? "" : `&review_status=${reviewFilter}`;
      const params = new URLSearchParams();
      if (sessionEmployee) params.set("employee_id", sessionEmployee);
      if (sessionTraining) params.set("training_id", sessionTraining);
      if (evalFilter) params.set("evaluation_status", evalFilter);
      if (sessionFrom) params.set("from", new Date(`${sessionFrom}T00:00:00`).toISOString());
      if (sessionTo) params.set("to", new Date(`${sessionTo}T23:59:59.999`).toISOString());
      return allPages<SessionSummary>(`/admin/sessions?limit=100${filterParam}&${params}`);
    },
    refetchInterval: query => query.state.data?.items.some(s => s.status === "active" || s.evaluation_status === "pending") ? 3000 : false,
  });

  const drafts = useQuery({
    queryKey: ["admin-drafts", draftFilter],
    queryFn: () => allPages<TrainingDraft>(`/admin/training-drafts?limit=100${draftFilter ? `&status=${draftFilter}` : ""}`),
    refetchInterval: query => query.state.data?.items.some(d => d.status === "generating") ? 1500 : false,
  });

  const trainings = useQuery({
    queryKey: ["trainings"],
    queryFn: () => allPages<TrainingSummary>("/trainings?limit=100"),
  });

  const evalForReview = useQuery({
    queryKey: ["evaluation", reviewingSessionId],
    enabled: Boolean(reviewingSessionId),
    queryFn: () => api<EvaluationEnvelope>(`/sessions/${reviewingSessionId}/evaluation`),
  });

  // Publish draft mutation
  const publishDraftMutation = useMutation({
    mutationFn: ({ draftId, version }: { draftId: string; version: number }) =>
      api(`/admin/training-drafts/${draftId}/publish`, {
        method: "POST",
        body: JSON.stringify({ version }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-drafts"] });
      void queryClient.invalidateQueries({ queryKey: ["trainings"] });
      setFeedback("Eğitim yayımlandı ve kataloğa eklendi.");
    },
  });

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {feedback && <p role="status" className="rounded-2xl bg-pine-soft p-4 text-pine">{feedback}</p>}
      {[overview, employees, sessions, drafts, trainings, evalForReview].filter(q => q.isError).map((q, i) => <p key={i} role="alert" className="rounded-2xl bg-accent-soft p-4 text-accent">{q.error?.message} <button className="underline" onClick={() => void q.refetch()}>Tekrar dene</button></p>)}
      {publishDraftMutation.error && <p role="alert" className="text-accent">{publishDraftMutation.error.message} {isApiError(publishDraftMutation.error) && publishDraftMutation.error.status === 409 && <button className="underline" onClick={() => { const id = publishDraftMutation.variables?.draftId; publishDraftMutation.reset(); void queryClient.invalidateQueries({ queryKey: ["admin-drafts"] }); if (id) { void queryClient.invalidateQueries({ queryKey: ["admin-draft", id] }); setEditingDraftId(id); } }}>Güncel sürümü incele</button>}</p>}
      {reviewingSessionId && evalForReview.isFetching && <p role="status">Değerlendirme yükleniyor…</p>}
      {/* Başlık ve Hızlı Eylem Alanı */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="font-serif text-3xl sm:text-4xl tracking-tight text-ink">
              Yönetici Paneli
            </h1>
            <span className="rounded-full bg-primary/10 border border-primary/20 px-3 py-0.5 text-xs font-semibold text-primary">
              Yönetici
            </span>
          </div>
          <p className="mt-1 text-sm text-muted">
            Çalışanların eğitim atamalarını yönetin, müşteri provası oturumlarını inceleyin ve yapay zeka ile senaryolar üretin.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => {
              setPreselectedEmpIdForAssign(undefined);
              setAssignOpen(true);
            }}
            className="flex items-center gap-2 rounded-full bg-primary px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:opacity-95 transition-opacity"
          >
            <span>+</span>
            <span>Eğitim Ata</span>
          </button>
          <button
            type="button"
            onClick={() => setCreateEmployeeOpen(true)}
            className="flex items-center gap-1.5 rounded-full border border-line bg-card px-4 py-2.5 text-sm font-medium text-ink hover:border-primary/40 transition-colors"
          >
            <span>+</span>
            <span>Çalışan Ekle</span>
          </button>
        </div>
      </div>

      {/* Navigasyon Sekmeleri */}
      <div className="flex border-b border-line gap-2 overflow-x-auto pb-px">
        <button
          type="button"
          onClick={() => setActiveTab("overview")}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-all whitespace-nowrap ${
            activeTab === "overview"
              ? "border-primary text-primary"
              : "border-transparent text-muted hover:text-ink"
          }`}
        >
          Genel Bakış
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("employees")}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-all whitespace-nowrap ${
            activeTab === "employees"
              ? "border-primary text-primary"
              : "border-transparent text-muted hover:text-ink"
          }`}
        >
          Çalışanlar & Atamalar ({overview.data?.active_employees ?? 0})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("reviews")}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-all whitespace-nowrap flex items-center gap-2 ${
            activeTab === "reviews"
              ? "border-primary text-primary"
              : "border-transparent text-muted hover:text-ink"
          }`}
        >
          <span>Oturum İnceleme</span>
          {(overview.data?.sessions_pending_review ?? 0) > 0 && (
            <span className="rounded-full bg-warn-soft px-2 py-0.5 text-xs text-warn font-semibold">
              {overview.data?.sessions_pending_review}
            </span>
          )}
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("drafts")}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-all whitespace-nowrap flex items-center gap-1.5 ${
            activeTab === "drafts"
              ? "border-primary text-primary"
              : "border-transparent text-muted hover:text-ink"
          }`}
        >
          <span>✨</span>
          <span>Yapay Zeka Taslakları</span>
        </button>
      </div>

      {/* ----------------- TAB: OVERVIEW ----------------- */}
      {activeTab === "overview" && (
        <div className="space-y-8 animate-in fade-in duration-200">
          {/* Metrik Kartları */}
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-3.5">
            <div className="rounded-2xl border border-line bg-card p-5 shadow-xs">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted">
                Aktif Çalışan
              </p>
              <p className="mt-2 font-serif text-3xl font-bold text-ink">
                {overview.data?.active_employees ?? "-"}
              </p>
              <p className="mt-1 text-xs text-muted">İşletme bünyesinde</p>
            </div>

            <div className="rounded-2xl border border-line bg-card p-5 shadow-xs">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted">
                Açık Atamalar
              </p>
              <p className="mt-2 font-serif text-3xl font-bold text-primary">
                {overview.data?.open_assignments ?? "-"}
              </p>
              <p className="mt-1 text-xs text-muted">Yönetici ataması, henüz kapanmamış</p>
            </div>

            <div className="rounded-2xl border border-line bg-card p-5 shadow-xs">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted">
                Süren prova
              </p>
              <p className="mt-2 font-serif text-3xl font-bold text-ink">
                {overview.data?.active_sessions ?? "-"}
              </p>
              <p className="mt-1 text-xs text-muted">Katalog ve atama, cevap sürüyor</p>
            </div>

            <div className="rounded-2xl border border-line bg-card p-5 shadow-xs">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted">
                Tamamlanan
              </p>
              <p className="mt-2 font-serif text-3xl font-bold text-pine">
                {overview.data?.completed_assignments ?? "-"}
              </p>
              <p className="mt-1 text-xs text-muted">Bitirilmiş atama</p>
            </div>

            <div className="rounded-2xl border border-line bg-card p-5 shadow-xs">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted">
                İnceleme Bekleyen
              </p>
              <p className="mt-2 font-serif text-3xl font-bold text-warn">
                {overview.data?.sessions_pending_review ?? "-"}
              </p>
              <p className="mt-1 text-xs text-muted">Gözden geçirme gerekli</p>
            </div>

            <div className="col-span-2 sm:col-span-1 rounded-2xl border border-line bg-card p-5 shadow-xs">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted">
                Son 7 Gün
              </p>
              <p className="mt-2 font-serif text-3xl font-bold text-ink">
                {overview.data?.sessions_last_7_days ?? "-"}
              </p>
              <p className="mt-1 text-xs text-muted">Gerçekleşen prova</p>
            </div>
          </div>

          {/* İnceleme Bekleyen Oturumlar Uyarısı */}
          {(overview.data?.sessions_pending_review ?? 0) > 0 && (
            <div className="rounded-3xl border border-warn/30 bg-warn-soft/40 p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-start gap-3">
                <span className="text-2xl">⚠️</span>
                <div>
                  <h3 className="font-semibold text-ink text-base">
                    {overview.data?.sessions_pending_review} prova oturumu yönetici incelemesi bekliyor
                  </h3>
                  <p className="text-xs text-muted mt-0.5">
                    Model değerlendirmesinde belirsizlik olan oturumlar çalışan puanına nihai olarak yansımadan önce incelemenizi bekliyor.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setReviewFilter("pending");
                  setActiveTab("reviews");
                }}
                className="rounded-full bg-warn text-white px-4 py-2 text-xs font-semibold hover:opacity-90 whitespace-nowrap self-start sm:self-center transition-opacity"
              >
                Oturumları İncele →
              </button>
            </div>
          )}

          {/* Hızlı Atama ve Çalışan Özeti */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Mevcut Eğitimler ve Hızlı Ata */}
            <div className="rounded-3xl border border-line bg-card p-6 shadow-xs space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-serif text-xl text-ink">Katalogdaki Eğitimler</h3>
                  <p className="text-xs text-muted">Çalışanlara doğrudan bu listeden atama yapabilirsiniz.</p>
                </div>
                <button
                  type="button"
                  onClick={() => setAssignOpen(true)}
                  className="text-xs text-primary font-medium hover:underline"
                >
                  + Atama Yap
                </button>
              </div>

              <div className="space-y-2.5 max-h-80 overflow-y-auto">
                {trainings.data?.items.map((t) => (
                  <div
                    key={t.id}
                    className="flex items-center justify-between p-3.5 rounded-2xl border border-line bg-card-subtle hover:border-primary/30 transition-colors"
                  >
                    <div>
                      <p className="text-xs text-muted">
                        {sectorLabel(t.sector)} · {t.estimated_minutes} dk
                      </p>
                      <p className="text-sm font-medium text-ink">{t.title}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setAssignTrainingId(t.id);
                        setPreselectedEmpIdForAssign(undefined);
                        setAssignOpen(true);
                      }}
                      className="rounded-full border border-line px-3 py-1 text-xs text-primary font-medium hover:bg-card transition-colors"
                    >
                      Ata
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Çalışan Listesi Önizleme */}
            <div className="rounded-3xl border border-line bg-card p-6 shadow-xs space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-serif text-xl text-ink">Çalışanlar</h3>
                  <p className="text-xs text-muted">Performans ve açık atama durumları.</p>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveTab("employees")}
                  className="text-xs text-primary font-medium hover:underline"
                >
                  Tümünü Gör →
                </button>
              </div>

              <div className="space-y-2.5 max-h-80 overflow-y-auto">
                {employees.data?.items.slice(0, 5).map((emp) => (
                  <div
                    key={emp.id}
                    className="flex items-center justify-between p-3.5 rounded-2xl border border-line bg-card-subtle"
                  >
                    <div className="flex items-center gap-3">
                      <div className="h-9 w-9 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-sm">
                        {emp.display_name.charAt(0)}
                      </div>
                      <div>
                        <p className="text-sm font-medium text-ink">{emp.display_name}</p>
                        <p className="text-xs text-muted">{emp.email}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs px-2.5 py-1 rounded-full bg-card border border-line text-muted">
                        {emp.open_assignments} atama{emp.active_sessions > 0 ? ` · ${emp.active_sessions} süren` : ""}
                      </span>
                      <button
                        type="button"
                        onClick={() => {
                          setPreselectedEmpIdForAssign(emp.id);
                          setAssignOpen(true);
                        }}
                        className="text-xs text-primary font-medium hover:underline p-1"
                      >
                        Ata
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === "employees" && <label className="block text-sm text-muted">Hesap durumu <select className="ml-3 rounded-xl border border-line bg-card px-3 py-2 text-ink" value={employeeFilter} onChange={e => setEmployeeFilter(e.target.value)}><option value="">Tümü</option><option value="true">Aktif</option><option value="false">Pasif</option></select></label>}
      {activeTab === "reviews" && <label className="text-sm text-muted">İnceleme durumu <select className="ml-3 rounded-xl border border-line bg-card p-2 text-ink" value={reviewFilter} onChange={e => setReviewFilter(e.target.value as typeof reviewFilter)}><option value="all">Tümü</option><option value="pending">Bekleyen</option><option value="reviewed">İncelenen</option><option value="not_required">İnceleme gerekmeyen</option></select></label>}
      {activeTab === "reviews" && <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-sm text-muted">Çalışan<select className="mt-1 w-full rounded-xl border border-line bg-card p-2 text-ink" value={sessionEmployee} onChange={e => setSessionEmployee(e.target.value)}><option value="">Tümü</option>{employees.data?.items.map(e => <option key={e.id} value={e.id}>{e.display_name}</option>)}</select></label>
        <label className="text-sm text-muted">Eğitim<select className="mt-1 w-full rounded-xl border border-line bg-card p-2 text-ink" value={sessionTraining} onChange={e => setSessionTraining(e.target.value)}><option value="">Tümü</option>{trainings.data?.items.map(t => <option key={t.id} value={t.id}>{t.title}</option>)}</select></label>
        <label className="text-sm text-muted">Değerlendirme<select className="mt-1 w-full rounded-xl border border-line bg-card p-2 text-ink" value={evalFilter} onChange={e => setEvalFilter(e.target.value)}><option value="">Tümü</option><option value="pending">Hazırlanıyor</option><option value="ready">Hazır</option><option value="needs_review">İnceleme gerekli</option><option value="error">Hata</option></select></label>
        <label className="text-sm text-muted">Başlangıç tarihi<input type="date" className="mt-1 w-full rounded-xl border border-line bg-card p-2 text-ink" value={sessionFrom} onChange={e => setSessionFrom(e.target.value)} /></label>
        <label className="text-sm text-muted">Bitiş tarihi<input type="date" className="mt-1 w-full rounded-xl border border-line bg-card p-2 text-ink" value={sessionTo} onChange={e => setSessionTo(e.target.value)} /></label>
      </div>}
      {activeTab === "drafts" && <label className="block text-sm text-muted">Taslak durumu <select className="ml-3 rounded-xl border border-line bg-card px-3 py-2 text-ink" value={draftFilter} onChange={e => setDraftFilter(e.target.value)}><option value="">Tümü</option><option value="generating">Üretiliyor</option><option value="ready">Hazır</option><option value="error">Hata</option><option value="published">Yayımlandı</option></select></label>}
      {/* ----------------- TAB: EMPLOYEES ----------------- */}
      {activeTab === "employees" && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex-1 max-w-md">
              <input
                type="text"
                placeholder="İsim veya e-posta ile ara…"
                value={employeeSearch}
                onChange={(e) => setEmployeeSearch(e.target.value)}
                className="w-full rounded-2xl border border-line bg-card px-4 py-2.5 text-sm text-ink outline-none focus:border-primary transition-colors"
              />
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setCreateEmployeeOpen(true)}
                className="rounded-full bg-primary px-4 py-2.5 text-sm font-medium text-white hover:opacity-95 transition-opacity"
              >
                + Yeni Çalışan Ekle
              </button>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {employees.isLoading ? (
              <p className="col-span-full text-muted py-8 text-center">Çalışanlar yükleniyor…</p>
            ) : employees.data?.items.length === 0 ? (
              <p className="col-span-full text-muted py-8 text-center">Çalışan bulunamadı.</p>
            ) : (
              employees.data?.items.map((emp) => (
                <div
                  key={emp.id}
                  className="rounded-3xl border border-line bg-card p-5 shadow-xs flex flex-col justify-between hover:border-primary/40 transition-all"
                >
                  <div>
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div className="h-11 w-11 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-base">
                          {emp.display_name.charAt(0)}
                        </div>
                        <div>
                          <h3 className="font-semibold text-ink text-base">{emp.display_name}</h3>
                          <p className="text-xs text-muted">{emp.email}</p>
                        </div>
                      </div>
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          emp.active ? "bg-pine-soft text-pine" : "bg-accent-soft text-accent"
                        }`}
                      >
                        {emp.active ? "Aktif" : "Pasif"}
                      </span>
                    </div>

                    <div className="mt-5 grid grid-cols-3 gap-2 text-center">
                      <div className="rounded-xl border border-line bg-card-subtle p-2">
                        <p className="text-[11px] text-muted uppercase">Açık Atama</p>
                        <p className="mt-0.5 font-semibold text-ink text-sm">{emp.open_assignments}</p>
                      </div>
                      <div className="rounded-xl border border-line bg-card-subtle p-2">
                        <p className="text-[11px] text-muted uppercase">Süren</p>
                        <p className="mt-0.5 font-semibold text-ink text-sm">{emp.active_sessions}</p>
                      </div>
                      <div className="rounded-xl border border-line bg-card-subtle p-2">
                        <p className="text-[11px] text-muted uppercase">Tamamlanan</p>
                        <p className="mt-0.5 font-semibold text-pine text-sm">{emp.completed_sessions}</p>
                      </div>
                    </div>
                  </div>

                  <div className="mt-5 pt-4 border-t border-line flex items-center justify-between">
                    <button
                      type="button"
                      onClick={() => setSelectedEmployeeId(emp.id)}
                      className="text-xs font-medium text-muted hover:text-ink transition-colors"
                    >
                      Geçmiş & Detay →
                    </button>
                    <button
                      type="button"
                      disabled={!emp.active}
                      onClick={() => {
                        setPreselectedEmpIdForAssign(emp.id);
                        setAssignOpen(true);
                      }}
                      className="rounded-full bg-primary/10 text-primary px-3 py-1 text-xs font-semibold hover:bg-primary hover:text-white transition-colors"
                    >
                      + Eğitim Ata
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* ----------------- TAB: REVIEWS ----------------- */}
      {activeTab === "reviews" && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="font-serif text-2xl text-ink">Prova Oturumları & İnceleme</h2>
              <p className="text-xs text-muted">
                Çalışanların tamamladığı provaların transkriptlerini ve AI değerlendirmelerini denetleyin.
              </p>
            </div>

            <div className="flex items-center gap-2 bg-card-subtle p-1 rounded-2xl border border-line">
              <button
                type="button"
                onClick={() => setReviewFilter("pending")}
                className={`rounded-xl px-3 py-1.5 text-xs font-medium transition-colors ${
                  reviewFilter === "pending"
                    ? "bg-card text-ink shadow-xs"
                    : "text-muted hover:text-ink"
                }`}
              >
                İnceleme Bekleyenler
              </button>
              <button
                type="button"
                onClick={() => setReviewFilter("reviewed")}
                className={`rounded-xl px-3 py-1.5 text-xs font-medium transition-colors ${
                  reviewFilter === "reviewed"
                    ? "bg-card text-ink shadow-xs"
                    : "text-muted hover:text-ink"
                }`}
              >
                İncelenenler
              </button>
              <button
                type="button"
                onClick={() => setReviewFilter("all")}
                className={`rounded-xl px-3 py-1.5 text-xs font-medium transition-colors ${
                  reviewFilter === "all"
                    ? "bg-card text-ink shadow-xs"
                    : "text-muted hover:text-ink"
                }`}
              >
                Tümü
              </button>
            </div>
          </div>

          <div className="space-y-3">
            {sessions.isLoading ? (
              <p className="text-muted py-8 text-center">Oturumlar yükleniyor…</p>
            ) : sessions.data?.items.length === 0 ? (
              <div className="rounded-3xl border border-line bg-card p-10 text-center space-y-2">
                <p className="font-serif text-lg text-ink">İnceleme gerektiren oturum bulunmuyor.</p>
                <p className="text-xs text-muted">Tüm provalar güncel veya onaylanmış durumda.</p>
              </div>
            ) : (
              sessions.data?.items.map((item) => (
                <div
                  key={item.id}
                  className="rounded-3xl border border-line bg-card p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:border-primary/30 transition-colors"
                >
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-ink text-base">
                        {item.employee.display_name}
                      </span>
                      <span className="text-line">·</span>
                      <span className="text-sm text-muted">{item.training.title}</span>
                      <span className="text-line">·</span>
                      <span className="text-xs text-muted">
                        {channelLabel(item.channel)} · {new Date(item.started_at).toLocaleDateString("tr-TR")}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-muted">
                      <span>{item.employee_turn_count} cevap · {summaryOutcome(item)}</span>
                      <span>·</span>
                      {(item.evaluation_status === "ready" || item.evaluation_status === "needs_review") && (
                        <span>AI Durumu: {evaluationLabel[item.evaluation_status]}</span>
                      )}
                      <span>·</span>
                      <span
                        className={`font-medium ${
                          item.review_status === "pending"
                            ? "text-warn"
                            : item.review_status === "reviewed"
                              ? "text-pine"
                              : "text-muted"
                        }`}
                      >
                        İnceleme: {item.review_status === "pending" ? "Bekliyor" : item.review_status === "reviewed" ? "İncelendi" : "Gerekmiyor"}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    {item.total ? (
                      <div className="text-right mr-2">
                        <span className="block font-serif text-lg font-bold text-primary">
                          {item.total.score ?? "-"} / {item.total.max_score}
                        </span>
                        <span className="text-[11px] text-muted">Toplam Puan</span>
                      </div>
                    ) : null}

                    <Link
                      to={`/sessions/${item.id}`}
                      className="rounded-full border border-line px-4 py-2 text-xs font-medium text-ink hover:bg-card-subtle transition-colors"
                    >
                      Transkript & Rapor
                    </Link>

                    {(item.evaluation_status === "ready" || item.evaluation_status === "needs_review") && (
                      <button
                        type="button"
                        onClick={() => setReviewingSessionId(item.id)}
                        className="rounded-full bg-primary px-4 py-2 text-xs font-semibold text-white hover:opacity-95 transition-opacity"
                      >
                        {item.review_status === "reviewed" ? "İncelemeyi Düzenle" : "İncele & Onayla"}
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* ----------------- TAB: DRAFTS (AI GENERATOR) ----------------- */}
      {activeTab === "drafts" && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="font-serif text-2xl text-ink flex items-center gap-2">
                <span>✨</span>
                <span>Gemma Yapay Zeka ile Eğitim Taslakları</span>
              </h2>
              <p className="text-xs text-muted">
                İşletme politikalarınızı ve kurallarınızı verin, Gemma sizin için senaryolar ve 5 seviyeli değerlendirme ölçütleri üretsin.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setCreateDraftOpen(true)}
              className="rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:opacity-95 transition-opacity flex items-center gap-2"
            >
              <span>+</span>
              <span>Yeni Taslak Üret</span>
            </button>
          </div>

          <div className="grid gap-4">
            {drafts.isLoading ? (
              <p className="text-muted py-8 text-center">Taslaklar yükleniyor…</p>
            ) : drafts.data?.items.length === 0 ? (
              <div className="rounded-3xl border border-line bg-card p-10 text-center space-y-3">
                <p className="font-serif text-lg text-ink">Henüz üretilmiş bir eğitim taslağı yok.</p>
                <p className="text-xs text-muted max-w-md mx-auto">
                  İşletmenize özel mağaza veya otel müşteri provası oluşturmak için "Yeni Taslak Üret" düğmesine tıklayın.
                </p>
                <button
                  type="button"
                  onClick={() => setCreateDraftOpen(true)}
                  className="mt-2 rounded-full bg-primary px-4 py-2 text-xs font-semibold text-white hover:opacity-95"
                >
                  İlk Taslağı Üret ✨
                </button>
              </div>
            ) : (
              drafts.data?.items.map((draft) => (
                <div
                  key={draft.id}
                  className="rounded-3xl border border-line bg-card p-6 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                >
                  <div className="space-y-2">
                    <div className="flex items-center gap-3">
                      <span className="font-semibold text-ink text-lg">
                        {draft.form.business_name}
                      </span>
                      <span className="rounded-full bg-card-subtle border border-line px-2.5 py-0.5 text-xs text-muted">
                        {sectorLabel(draft.form.sector)}
                      </span>
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          draft.status === "published"
                            ? "bg-pine-soft text-pine"
                            : draft.status === "ready"
                              ? "bg-primary/10 text-primary"
                              : draft.status === "generating"
                                ? "bg-warn-soft text-warn"
                                : "bg-accent-soft text-accent"
                        }`}
                      >
                        {draft.status === "published"
                          ? "✓ Yayımlandı"
                          : draft.status === "ready"
                            ? "Hazır (Yayımlanabilir)"
                            : draft.status === "generating"
                              ? "Gemma Üretiyor…"
                              : "Hata"}
                      </span>
                    </div>

                    <p className="text-xs text-muted">
                      {draft.form.policies.length} Politika Kuralı · {draft.form.scenario_count} Senaryo Hedefi · v{draft.version}
                    </p>
                    {draft.generation_job_id && (draft.status === "generating" || draft.status === "error") && <DraftJobStatus jobId={draft.generation_job_id} />}

                    {draft.warnings && draft.warnings.length > 0 && (
                      <p className="text-xs text-warn">
                        ⚠️ {draft.warnings.join(", ")}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-3">
                    {draft.content && <button type="button" onClick={() => setEditingDraftId(draft.id)} className="rounded-full border border-line px-4 py-2 text-xs text-primary">İncele / Düzenle</button>}
                    {draft.status === "error" && draft.generation_job_id && <button type="button" className="text-sm text-primary underline" onClick={async () => { try { await api(`/jobs/${draft.generation_job_id}/retry`, { method: "POST" }); await queryClient.invalidateQueries({ queryKey: ["admin-drafts"] }); setFeedback("Taslak üretimi yeniden başlatıldı."); } catch (error) { setFeedback(error instanceof Error ? error.message : "Tekrar denenemedi."); } }}>Üretimi tekrar dene</button>}
                    {draft.status === "ready" && (
                      <button
                        type="button"
                        disabled={publishDraftMutation.isPending}
                        onClick={() =>
                          publishDraftMutation.mutate({
                            draftId: draft.id,
                            version: draft.version,
                          })
                        }
                        className="rounded-full bg-pine px-4 py-2 text-xs font-semibold text-white hover:opacity-90 transition-opacity"
                      >
                        {publishDraftMutation.isPending ? "Yayımlanıyor…" : "Kataloğa Yayımla"}
                      </button>
                    )}
                    {draft.status === "published" && (
                      <div className="space-y-2 text-xs font-medium text-pine"><p>Yayında ({draft.published_training_ids.length} eğitim)</p>{draft.published_training_ids.map((id, index) => <button key={id} type="button" className="rounded-full border border-line px-4 py-2 text-primary" onClick={() => { setAssignTrainingId(id); setAssignOpen(true); }}>{draft.published_training_ids.length > 1 ? `${index + 1}. eğitimi ata` : "Çalışanlara ata"}</button>)}</div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* MODALLER */}
      {editingDraftId && <DraftEditor key={editingDraftId} draftId={editingDraftId} onClose={() => setEditingDraftId(null)} />}
      <AssignModal
        defaultTrainingId={assignTrainingId}
        open={assignOpen}
        onClose={() => { setAssignOpen(false); setAssignTrainingId(undefined); setPreselectedEmpIdForAssign(undefined); }}
        defaultEmployeeId={preselectedEmpIdForAssign}
      />

      <CreateEmployeeModal
        open={createEmployeeOpen}
        onClose={() => setCreateEmployeeOpen(false)}
      />

      <CreateDraftModal
        open={createDraftOpen}
        onClose={() => setCreateDraftOpen(false)}
      />

      <EmployeeDetailModal
        employeeId={selectedEmployeeId}
        onClose={() => setSelectedEmployeeId(null)}
        onOpenAssign={(empId) => {
          setPreselectedEmpIdForAssign(empId);
          setAssignOpen(true);
        }}
      />

      {reviewingSessionId && evalForReview.data?.report && (
        <ReviewModal
          open={Boolean(reviewingSessionId)}
          onClose={() => setReviewingSessionId(null)}
          sessionId={reviewingSessionId}
          report={evalForReview.data.report}
        />
      )}
    </div>
  );
}

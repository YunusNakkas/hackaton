import { ModalFrame } from "./ModalFrame";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, allPages, isApiError } from "../api/client";
import type {
  CreateAssignmentsRequest,
  CreateAssignmentsResponse,
  Employee,
  TrainingSummary,
} from "../api/types";
import { difficultyLabel, sectorLabel } from "../lib/labels";

interface AssignModalProps {
  open: boolean;
  onClose: () => void;
  defaultTrainingId?: string;
  defaultEmployeeId?: string;
}

export function AssignModal({
  open,
  onClose,
  defaultTrainingId,
  defaultEmployeeId,
}: AssignModalProps) {
  const queryClient = useQueryClient();
  const [selectedTrainingId, setSelectedTrainingId] = useState<string>(
    defaultTrainingId ?? ""
  );
  const [selectedEmployees, setSelectedEmployees] = useState<Set<string>>(
    new Set(defaultEmployeeId ? [defaultEmployeeId] : [])
  );
  const [dueDate, setDueDate] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successInfo, setSuccessInfo] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setSelectedTrainingId(defaultTrainingId ?? "");
    setSelectedEmployees(new Set(defaultEmployeeId ? [defaultEmployeeId] : []));
    setDueDate("");
    setErrorMsg(null);
    setSuccessInfo(null);
  }, [open, defaultTrainingId, defaultEmployeeId]);

  const trainings = useQuery({
    queryKey: ["trainings"],
    queryFn: () => allPages<TrainingSummary>("/trainings?limit=100"),
    enabled: open,
  });

  const employees = useQuery({
    queryKey: ["admin-employees-active"],
    queryFn: () => allPages<Employee>("/admin/employees?active=true&limit=100"),
    enabled: open,
  });

  const assignMutation = useMutation({
    mutationFn: (body: CreateAssignmentsRequest) =>
      api<CreateAssignmentsResponse>("/admin/assignments", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-employees"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-employees-active"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-employee"] });
      void queryClient.invalidateQueries({ queryKey: ["assignments"] });
      const createdCount = res.created.length;
      const skippedCount = res.skipped_employee_ids.length;
      let msg = `${createdCount} çalışana eğitim başarıyla atandı.`;
      if (skippedCount > 0) {
        msg += ` (${skippedCount} çalışan zaten bu eğitime atanmış olduğu için atlandı)`;
      }
      setSuccessInfo(msg);
    },
    onError: (err) => {
      setErrorMsg(isApiError(err) ? err.message : "Atama yapılamadı.");
    },
  });

  if (!open) return null;

  const toggleEmployee = (id: string) => {
    setSelectedEmployees((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    if (!employees.data) return;
    setSelectedEmployees(new Set(employees.data.items.map((e) => e.id)));
  };

  const clearAll = () => {
    setSelectedEmployees(new Set());
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    if (!selectedTrainingId) {
      setErrorMsg("Lütfen atanacak bir eğitim seçin.");
      return;
    }
    if (selectedEmployees.size === 0) {
      setErrorMsg("Lütfen en az bir çalışan seçin.");
      return;
    }

    assignMutation.mutate({
      training_id: selectedTrainingId,
      employee_ids: Array.from(selectedEmployees),
      due_at: dueDate ? new Date(dueDate).toISOString() : null,
    });
  };

  return (
    <ModalFrame>
      <div className="w-full max-w-xl max-h-[90vh] flex flex-col rounded-3xl border border-line bg-card shadow-2xl overflow-hidden animate-in fade-in duration-200">
        <div className="flex items-center justify-between border-b border-line px-6 py-4">
          <div>
            <h2 className="font-serif text-2xl tracking-tight text-ink">
              Eğitim Ata
            </h2>
            <p className="text-sm text-muted">
              Çalışanlara tamamlamaları gereken yazılı provayı atayın.
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
          {successInfo && (
            <div className="rounded-2xl border border-pine/20 bg-pine-soft/50 p-4 text-sm text-pine">
              {successInfo}
              <button type="button" onClick={onClose} className="ml-2 underline">Tamam</button>
            </div>
          )}

          {/* Eğitim Seçimi */}
          <div>
            <label className="block text-sm font-medium text-ink mb-2">
              Eğitim Seçin
            </label>
            <select aria-label="Eğitim Seçin"
              value={selectedTrainingId}
              onChange={(e) => setSelectedTrainingId(e.target.value)}
              className="w-full rounded-2xl border border-line bg-card-subtle px-4 py-3 text-sm text-ink outline-none focus:border-primary transition-colors"
            >
              <option value="">-- Bir eğitim seçin --</option>
              {trainings.data?.items.map((t) => (
                <option key={t.id} value={t.id}>
                  [{sectorLabel(t.sector)}] {t.title} ({difficultyLabel[t.difficulty]} · {t.estimated_minutes} dk)
                </option>
              ))}
            </select>
          </div>

          {/* Çalışanlar Seçimi */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-ink">
                Çalışanlar ({selectedEmployees.size} seçildi)
              </label>
              <div className="space-x-2 text-xs">
                <button
                  type="button"
                  onClick={selectAll}
                  className="text-primary hover:underline"
                >
                  Tümünü Seç
                </button>
                <span className="text-line">|</span>
                <button
                  type="button"
                  onClick={clearAll}
                  className="text-muted hover:underline"
                >
                  Temizle
                </button>
              </div>
            </div>

            <div className="max-h-52 overflow-y-auto rounded-2xl border border-line bg-card-subtle p-3 space-y-2">
              {employees.isLoading ? (
                <p className="text-sm text-muted p-2">Çalışanlar yükleniyor…</p>
              ) : employees.data?.items.length === 0 ? (
                <p className="text-sm text-muted p-2">Aktif çalışan bulunamadı.</p>
              ) : (
                employees.data?.items.map((emp) => {
                  const checked = selectedEmployees.has(emp.id);
                  return (
                    <label
                      key={emp.id}
                      className={`flex items-center justify-between gap-3 p-2.5 rounded-xl border transition-colors cursor-pointer text-sm ${
                        checked
                          ? "border-primary/50 bg-primary/10 text-ink font-medium"
                          : "border-transparent hover:bg-card text-muted hover:text-ink"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleEmployee(emp.id)}
                          className="h-4 w-4 rounded accent-primary"
                        />
                        <div>
                          <p>{emp.display_name}</p>
                          <p className="text-xs text-muted">{emp.email}</p>
                        </div>
                      </div>
                      <span className="text-xs text-muted">
                        {emp.open_assignments} açık atama
                      </span>
                    </label>
                  );
                })
              )}
            </div>
          </div>

          {/* Bitiş Tarihi */}
          <div>
            <label className="block text-sm font-medium text-ink mb-2">
              Son Teslim Tarihi (Opsiyonel)
            </label>
            <input aria-label="Son Teslim Tarihi (Opsiyonel)"
              type="datetime-local"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className="w-full rounded-2xl border border-line bg-card-subtle px-4 py-2.5 text-sm text-ink outline-none focus:border-primary transition-colors"
            />
            <p className="mt-1 text-xs text-muted">
              Çalışanın arayüzünde son tarih uyarısı olarak gösterilir.
            </p>
          </div>

          <div className="pt-2 flex items-center justify-end gap-3 border-t border-line">
            <button
              type="button"
              onClick={onClose}
              disabled={assignMutation.isPending}
              className="rounded-full border border-line px-5 py-2.5 text-sm text-muted hover:text-ink hover:border-ink/30 transition-colors"
            >
              Vazgeç
            </button>
            <button
              type="submit"
              disabled={assignMutation.isPending || selectedEmployees.size === 0 || Boolean(successInfo)}
              className="rounded-full bg-primary px-6 py-2.5 text-sm font-medium text-white shadow-sm hover:opacity-95 disabled:opacity-50 transition-opacity"
            >
              {assignMutation.isPending ? "Atanıyor…" : "Atamayı Tamamla"}
            </button>
          </div>
        </form>
      </div>
    </ModalFrame>
  );
}

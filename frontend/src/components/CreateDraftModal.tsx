import { ModalFrame } from "./ModalFrame";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, isApiError } from "../api/client";
import type { BusinessRulesForm, TrainingDraft } from "../api/types";

interface CreateDraftModalProps {
  open: boolean;
  onClose: () => void;
}

export function CreateDraftModal({ open, onClose }: CreateDraftModalProps) {
  const queryClient = useQueryClient();
  const [businessName, setBusinessName] = useState("");
  const [sector, setSector] = useState<string>("retail");
  const [scenarioCount, setScenarioCount] = useState<number>(2);
  const [policies, setPolicies] = useState<{ title: string; body: string }[]>([
    { title: "İade ve Değişim Kuralı", body: "Fiş veya fatura ibrazında 14 gün içinde değişim veya iade yapılır. Ambalajı açık ürünlerde hijyen şartı aranır." },
  ]);
  const [customerSituations, setCustomerSituations] = useState<string>(
    "Müşteri indirimli ürünü iade etmek istiyor.\nMüşteri kasada fiyat uyuşmazlığı yaşıyor."
  );
  const [mustDo, setMustDo] = useState<string>(
    "Müşteriyi güler yüzle selamla.\nFişi nazikçe talep et.\nAlternatif ürün öner."
  );
  const [mustNotDo, setMustNotDo] = useState<string>(
    "Müşteriyle tartışmaya girme.\nKuralı açıklarken 'bizim suçumuz değil' deme."
  );
  const [escalationRule, setEscalationRule] = useState<string>(
    "Müşteri ısrar ederse mağaza müdürünü çağıracağını belirt."
  );
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const draftMutation = useMutation({
    mutationFn: (form: BusinessRulesForm) =>
      api<TrainingDraft>("/admin/training-drafts", {
        method: "POST",
        body: JSON.stringify({ form }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-drafts"] });
      onClose();
    },
    onError: (err) => {
      setErrorMsg(isApiError(err) ? err.message : "Taslak oluşturulamadı.");
    },
  });

  if (!open) return null;

  const addPolicy = () => {
    setPolicies((prev) => [...prev, { title: "", body: "" }]);
  };

  const removePolicy = (idx: number) => {
    setPolicies((prev) => prev.filter((_, i) => i !== idx));
  };

  const updatePolicy = (idx: number, field: "title" | "body", value: string) => {
    setPolicies((prev) =>
      prev.map((p, i) => (i === idx ? { ...p, [field]: value } : p))
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!businessName.trim()) {
      setErrorMsg("İşletme adı zorunludur.");
      return;
    }

    const validPolicies = policies.filter((p) => p.title.trim() && p.body.trim());
    if (validPolicies.length === 0) {
      setErrorMsg("En az bir geçerli işletme politikası tanımlamalısınız.");
      return;
    }

    const form: BusinessRulesForm = {
      business_name: businessName.trim(),
      sector,
      language: "tr",
      policies: validPolicies,
      customer_situations: customerSituations
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean),
      must_do: mustDo
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean),
      must_not_do: mustNotDo
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean),
      escalation_rule: escalationRule.trim() || null,
      scenario_count: Number(scenarioCount),
    };

    draftMutation.mutate(form);
  };

  return (
    <ModalFrame>
      <div className="w-full max-w-2xl max-h-[90vh] flex flex-col rounded-3xl border border-line bg-card shadow-2xl overflow-hidden animate-in fade-in duration-200">
        <div className="flex items-center justify-between border-b border-line px-6 py-4">
          <div>
            <h2 className="font-serif text-2xl tracking-tight text-ink flex items-center gap-2">
              <span>✨</span> Gemma ile Eğitim Taslağı Oluştur
            </h2>
            <p className="text-sm text-muted">
              İşletmenizin kurallarını girin, Gemma AI özel senaryolar ve ölçütler üretsin.
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

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-ink mb-1">İşletme Adı</label>
              <input aria-label="İşletme Adı"
                type="text"
                required
                placeholder="Örn: Moda Butik A.Ş."
                value={businessName}
                onChange={(e) => setBusinessName(e.target.value)}
                className="w-full rounded-2xl border border-line bg-card-subtle px-4 py-2.5 text-sm text-ink outline-none focus:border-primary transition-colors"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-ink mb-1">Sektör</label>
              <select aria-label="Sektör"
                value={sector}
                onChange={(e) => setSector(e.target.value)}
                className="w-full rounded-2xl border border-line bg-card-subtle px-4 py-2.5 text-sm text-ink outline-none focus:border-primary transition-colors"
              >
                <option value="retail">Perakende / Mağazacılık </option>
                <option value="hotel">Otelcilik / Konaklama </option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-ink mb-1">
              Üretilecek Senaryo Sayısı (1 - 5)
            </label>
            <input aria-label="Üretilecek Senaryo Sayısı (1 - 5)"
              type="number"
              min={1}
              max={5}
              value={scenarioCount}
              onChange={(e) => setScenarioCount(Number(e.target.value))}
              className="w-24 rounded-2xl border border-line bg-card-subtle px-4 py-2 text-sm text-ink outline-none focus:border-primary transition-colors"
            />
          </div>

          {/* Politikalar */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-ink">
                İşletme Politikaları ({policies.length})
              </label>
              <button
                type="button"
                onClick={addPolicy}
                className="text-xs text-primary font-medium hover:underline"
              >
                + Politika Ekle
              </button>
            </div>
            {policies.map((p, idx) => (
              <div key={idx} className="rounded-2xl border border-line bg-card-subtle p-3.5 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <input
                    type="text"
                    required
                    placeholder="Politika Başlığı (örn: İade Kuralı)"
                    value={p.title}
                    onChange={(e) => updatePolicy(idx, "title", e.target.value)}
                    className="flex-1 rounded-xl border border-line bg-card px-3 py-1.5 text-sm text-ink outline-none focus:border-primary"
                  />
                  {policies.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removePolicy(idx)}
                      className="text-xs text-accent hover:underline p-1"
                    >
                      Sil
                    </button>
                  )}
                </div>
                <textarea
                  rows={2}
                  required
                  placeholder="Politika Açıklaması ve Kuralı..."
                  value={p.body}
                  onChange={(e) => updatePolicy(idx, "body", e.target.value)}
                  className="w-full rounded-xl border border-line bg-card p-2.5 text-xs text-ink outline-none focus:border-primary resize-none"
                />
              </div>
            ))}
          </div>

          {/* Müşteri Durumları */}
          <div>
            <label className="block text-sm font-medium text-ink mb-1">
              Karşılaşılan Müşteri Senaryoları / Durumları (Her satıra bir durum)
            </label>
            <textarea aria-label="Karşılaşılan Müşteri Senaryoları / Durumları (Her satıra bir durum)"
              rows={3}
              value={customerSituations}
              onChange={(e) => setCustomerSituations(e.target.value)}
              className="w-full rounded-2xl border border-line bg-card-subtle p-3 text-sm text-ink outline-none focus:border-primary transition-colors resize-none"
            />
          </div>

          {/* Yapılması ve Yapılmaması Gerekenler */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-pine mb-1">
                Yapılması Gerekenler (Her satıra bir kural)
              </label>
              <textarea aria-label="Yapılması Gerekenler (Her satıra bir kural)"
                rows={3}
                value={mustDo}
                onChange={(e) => setMustDo(e.target.value)}
                className="w-full rounded-2xl border border-line bg-card-subtle p-3 text-xs text-ink outline-none focus:border-primary resize-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-accent mb-1">
                Yapılmaması Gerekenler (Her satıra bir kural)
              </label>
              <textarea aria-label="Yapılmaması Gerekenler (Her satıra bir kural)"
                rows={3}
                value={mustNotDo}
                onChange={(e) => setMustNotDo(e.target.value)}
                className="w-full rounded-2xl border border-line bg-card-subtle p-3 text-xs text-ink outline-none focus:border-primary resize-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-ink mb-1">
              Yetkiliye Aktarma Kuralı (Opsiyonel)
            </label>
            <input aria-label="Yetkiliye Aktarma Kuralı (Opsiyonel)"
              type="text"
              value={escalationRule}
              onChange={(e) => setEscalationRule(e.target.value)}
              className="w-full rounded-2xl border border-line bg-card-subtle px-4 py-2.5 text-sm text-ink outline-none focus:border-primary transition-colors"
            />
          </div>

          <div className="pt-2 flex items-center justify-end gap-3 border-t border-line">
            <button
              type="button"
              onClick={onClose}
              disabled={draftMutation.isPending}
              className="rounded-full border border-line px-5 py-2.5 text-sm text-muted hover:text-ink transition-colors"
            >
              Vazgeç
            </button>
            <button
              type="submit"
              disabled={draftMutation.isPending}
              className="rounded-full bg-primary px-6 py-2.5 text-sm font-medium text-white shadow-sm hover:opacity-95 disabled:opacity-50 transition-opacity"
            >
              {draftMutation.isPending ? "Üretim Başlatılıyor…" : "✨ Taslağı Oluştur"}
            </button>
          </div>
        </form>
      </div>
    </ModalFrame>
  );
}

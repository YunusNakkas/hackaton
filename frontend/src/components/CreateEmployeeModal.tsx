import { ModalFrame } from "./ModalFrame";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, isApiError } from "../api/client";
import type { CreateEmployeeRequest, Employee } from "../api/types";

interface CreateEmployeeModalProps {
  open: boolean;
  onClose: () => void;
}

export function CreateEmployeeModal({ open, onClose }: CreateEmployeeModalProps) {
  const queryClient = useQueryClient();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [tempPassword, setTempPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: (body: CreateEmployeeRequest) =>
      api<Employee>("/admin/employees", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-employees"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-employees-active"] });
      void queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
      setDisplayName(""); setEmail(""); setTempPassword(""); setErrorMsg(null);
      onClose();
    },
    onError: (err) => {
      setErrorMsg(isApiError(err) ? err.message : "Çalışan oluşturulamadı.");
    },
  });

  if (!open) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    if (!displayName.trim() || !email.trim() || !tempPassword) {
      setErrorMsg("Lütfen tüm alanları doldurun.");
      return;
    }
    // Tarayıcının kendi e-posta kontrolü yerine açık mesaj (form noValidate); backend de aynı kuralı uygular.
    if (/[^\x00-\x7F]/.test(email)) {
      setErrorMsg("E-posta adresinde Türkçe karakter (ç, ğ, ı, ö, ş, ü) kullanılamaz.");
      return;
    }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) {
      setErrorMsg("Geçerli bir e-posta adresi girin (ör. ayse@isletme.com).");
      return;
    }
    createMutation.mutate({
      display_name: displayName.trim(),
      email: email.trim().toLowerCase(),
      temporary_password: tempPassword,
    });
  };

  return (
    <ModalFrame>
      <div className="w-full max-w-md rounded-3xl border border-line bg-card shadow-2xl overflow-hidden animate-in fade-in duration-200">
        <div className="flex items-center justify-between border-b border-line px-6 py-4">
          <div>
            <h2 className="font-serif text-2xl tracking-tight text-ink">Yeni Çalışan Ekle</h2>
            <p className="text-sm text-muted">İşletmenize yeni bir çalışan hesabı tanımlayın.</p>
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

        <form onSubmit={handleSubmit} noValidate className="p-6 space-y-4">
          {errorMsg && (
            <div className="rounded-2xl border border-accent/20 bg-accent-soft/50 p-4 text-sm text-accent">
              {errorMsg}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-ink mb-1">Ad Soyad</label>
            <input aria-label="Ad Soyad"
              type="text"
              required
              placeholder="Örn: Ayşe Kaya"
              maxLength={100}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full rounded-2xl border border-line bg-card-subtle px-4 py-2.5 text-sm text-ink outline-none focus:border-primary transition-colors"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-ink mb-1">E-posta Adresi</label>
            <input aria-label="E-posta Adresi"
              type="email"
              required
              placeholder="Örn: ayse@isletme.com"
              maxLength={254}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-2xl border border-line bg-card-subtle px-4 py-2.5 text-sm text-ink outline-none focus:border-primary transition-colors"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-ink mb-1">Geçici Şifre</label>
            <input aria-label="Geçici Şifre"
              type="text"
              required
              minLength={8}
              maxLength={200}
              autoComplete="new-password"
              value={tempPassword}
              onChange={(e) => setTempPassword(e.target.value)}
              className="w-full rounded-2xl border border-line bg-card-subtle px-4 py-2.5 text-sm text-ink outline-none focus:border-primary transition-colors"
            />
            <p className="mt-1 text-xs text-muted">Çalışan ilk girişte bu şifreyi kullanabilir.</p>
          </div>

          <div className="pt-4 flex items-center justify-end gap-3 border-t border-line">
            <button
              type="button"
              onClick={onClose}
              disabled={createMutation.isPending}
              className="rounded-full border border-line px-5 py-2.5 text-sm text-muted hover:text-ink transition-colors"
            >
              Vazgeç
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="rounded-full bg-primary px-6 py-2.5 text-sm font-medium text-white shadow-sm hover:opacity-95 disabled:opacity-50 transition-opacity"
            >
              {createMutation.isPending ? "Ekleniyor…" : "Çalışanı Kaydet"}
            </button>
          </div>
        </form>
      </div>
    </ModalFrame>
  );
}

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, isApiError } from "../api/client";
import type { Me } from "../api/types";
import { BrandLogo } from "../components/BrandLogo";
import { ThemePicker } from "../components/ThemePicker";

export function ChangePasswordPage() {
  const client = useQueryClient();
  const navigate = useNavigate();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });
  const required = me.data?.user.must_change_password;
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [visible, setVisible] = useState(false);

  async function save(event: React.FormEvent) {
    event.preventDefault(); setError("");
    if (newPassword !== confirmation) { setError("Yeni şifreler eşleşmiyor."); return; }
    if (newPassword === currentPassword || !newPassword.trim()) { setError("Önceki şifrenizden farklı bir şifre seçin."); return; }
    setSaving(true);
    try {
      const updated = await api<Me>("/auth/change-password", { method: "POST", body: JSON.stringify({
        current_password: currentPassword, new_password: newPassword, confirm_password: confirmation,
      }) });
      setCurrentPassword(""); setNewPassword(""); setConfirmation("");
      client.clear(); client.setQueryData(["me"], updated);
      navigate(updated.user.role === "manager" ? "/admin" : "/", { replace: true });
    } catch (failure) {
      setError(isApiError(failure) ? failure.message : "Şifre yenilenemedi. Tekrar deneyin.");
    } finally { setSaving(false); }
  }

  const input = "mt-1.5 w-full rounded-2xl border border-line bg-card-subtle px-4 py-3 text-ink";
  return <main className="min-h-screen bg-paper px-5 py-8 text-ink">
    <header className="mx-auto flex w-full max-w-md items-center justify-between gap-4"><div className="flex items-center gap-2"><BrandLogo /><span className="font-serif text-xl font-semibold">ProvaMüşteri</span></div><ThemePicker /></header>
    <section className="mx-auto mt-10 w-full max-w-md rounded-3xl border border-line bg-card p-6 sm:p-8">
      <h1 className="font-serif text-3xl">{required ? "Kendi şifreni belirle" : "Şifreni yenile"}</h1>
      <p className="mt-3 text-sm text-muted">{required ? "Eğitimlerine devam etmek için geçici şifreni doğrula ve yeni şifreni belirle." : "Mevcut şifreni doğrulayarak yeni şifreni belirle."}</p>
      <p className="mt-2 break-words text-sm text-muted">{me.data?.user.email}</p>
      <form onSubmit={event => void save(event)} className="mt-6 space-y-4">
        <fieldset disabled={saving} className="space-y-4 disabled:opacity-60">
          <label className="block text-sm">{required ? "Geçici şifre" : "Mevcut şifre"}<input aria-label={required ? "Geçici şifre" : "Mevcut şifre"} required autoComplete="current-password" type={visible ? "text" : "password"} maxLength={200} value={currentPassword} onChange={event => setCurrentPassword(event.target.value)} className={input} /></label>
          <label className="block text-sm">Yeni şifre<input aria-label="Yeni şifre" required autoComplete="new-password" type={visible ? "text" : "password"} minLength={8} maxLength={200} value={newPassword} onChange={event => setNewPassword(event.target.value)} className={input} /></label>
          <label className="block text-sm">Yeni şifre (tekrar)<input aria-label="Yeni şifre (tekrar)" required autoComplete="new-password" type={visible ? "text" : "password"} minLength={8} maxLength={200} value={confirmation} onChange={event => setConfirmation(event.target.value)} className={input} /></label>
          <label className="flex items-center gap-2 text-sm text-muted"><input type="checkbox" checked={visible} onChange={event => setVisible(event.target.checked)} />Şifreleri göster</label>
          <p className="text-xs text-muted">En az 8 karakter kullan. Şifren değişince diğer açık oturumların kapanır.</p>
        </fieldset>
        {error && <p role="alert" className="rounded-xl bg-accent-soft p-3 text-sm text-accent">{error}</p>}
        <button type="submit" disabled={saving} className="w-full rounded-full bg-primary px-5 py-3 font-semibold text-white disabled:opacity-50">{saving ? "Yenileniyor…" : "Şifreyi yenile ve devam et"}</button>
      </form>
      <div className="mt-5 flex items-center justify-between text-sm text-muted">
        {!required && <Link to={me.data?.user.role === "manager" ? "/admin" : "/"} className="underline">Geri dön</Link>}
        <button type="button" disabled={saving} className="ml-auto underline" onClick={async () => {
          try { await api("/auth/logout", { method: "POST" }); client.clear(); navigate("/login", { replace: true }); }
          catch { setError("Oturum kapatılamadı. Tekrar deneyin."); }
        }}>Çıkış yap</button>
      </div>
    </section>
  </main>;
}

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { api, isApiError } from "../api/client";
import type { Me } from "../api/types";
import { ThemePicker } from "../components/ThemePicker";
import { BrandLogo } from "../components/BrandLogo";

const schema = z.object({
  email: z.email("Geçerli bir e-posta girin"),
  password: z.string().min(1, "Şifre gerekli"),
});

type FormValues = z.infer<typeof schema>;

export function LoginPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { email: "", password: "" } });

  async function onSubmit(values: FormValues) {
    setFormError(null);
    try {
      const me = await api<Me>("/auth/login", { method: "POST", body: JSON.stringify(values) });
      queryClient.setQueryData(["me"], me);
      if (me.user.role === "manager") {
        navigate("/admin", { replace: true });
      } else {
        navigate("/", { replace: true });
      }
    } catch (error) {
      setFormError(isApiError(error) ? error.message : "Giriş yapılamadı.");
    }
  }

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-2 bg-paper text-ink transition-colors duration-200">
      {/* Sol Panel: Hero Tanıtım */}
      <section className="relative hidden flex-col justify-between p-12 lg:flex border-r border-line bg-gradient-to-b from-card-subtle/50 to-transparent">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <BrandLogo />
            <span className="font-serif text-2xl font-semibold tracking-tight text-ink">
              ProvaMüşteri
            </span>
          </div>

          <ThemePicker />
        </div>

        <div className="max-w-lg py-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-xs font-semibold text-primary mb-6">
            <span>✨</span>
            <span>Yapay Zeka Destekli Müşteri Deneyimi</span>
          </div>
          <h1 className="font-serif text-5xl leading-[1.1] tracking-tight text-ink">
            Müşteriyle konuş. Gerçek kurallarla provayı tamamla.
          </h1>
          <p className="mt-6 text-base text-muted leading-relaxed">
            İşletmenizin iade, değişim, karşılama ve problem çözme standartlarıyla mesajda veya telefonda prova yapın. Model görüşmenizi puanlar ve yönetici denetler.
          </p>

          <div className="mt-8 grid grid-cols-2 gap-4">
            <div className="rounded-2xl border border-line bg-card/60 p-4">
              <p className="font-serif text-2xl font-bold text-primary">6 Farklı</p>
              <p className="text-xs text-muted mt-1">Mağaza ve Otel Senaryosu</p>
            </div>
            <div className="rounded-2xl border border-line bg-card/60 p-4">
              <p className="font-serif text-2xl font-bold text-pine">İki kanal</p>
              <p className="text-xs text-muted mt-1">Mesaj ya da telefon</p>
            </div>
          </div>
        </div>

        <p className="text-xs text-muted">
          Türkçe dil desteği · Gemma 4 Yapay Zeka Ölçüm Motoru
        </p>
      </section>

      {/* Sağ Panel: Giriş Formu */}
      <section className="flex min-h-screen items-center justify-center bg-card p-8 sm:p-14">
        <div className="w-full max-w-sm">
          <div className="flex items-center justify-between lg:hidden mb-8">
            <div className="flex items-center gap-2">
              <BrandLogo />
              <span className="font-serif text-xl font-semibold text-ink">ProvaMüşteri</span>
            </div>
            <ThemePicker />
          </div>

          <h2 className="font-serif text-3xl font-semibold text-ink">Giriş Yap</h2>
          <p className="mt-1 text-sm text-muted">Platforma erişmek için bilgilerinizi girin.</p>

          <form onSubmit={handleSubmit(onSubmit)} className="mt-8 space-y-4" noValidate>
            <div>
              <label className="block text-xs font-semibold text-muted uppercase tracking-wider" htmlFor="email">
                E-posta Adresi
              </label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                className="mt-1.5 w-full rounded-2xl border border-line bg-card-subtle px-4 py-3 text-sm text-ink outline-none focus:border-primary transition-colors"
                placeholder="ad@isletme.com"
                {...register("email")}
              />
              {errors.email && <p className="mt-1 text-xs text-accent">{errors.email.message}</p>}
            </div>

            <div>
              <label className="block text-xs font-semibold text-muted uppercase tracking-wider" htmlFor="password">
                Şifre
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                className="mt-1.5 w-full rounded-2xl border border-line bg-card-subtle px-4 py-3 text-sm text-ink outline-none focus:border-primary transition-colors"
                placeholder="••••••••"
                {...register("password")}
              />
              {errors.password && <p className="mt-1 text-xs text-accent">{errors.password.message}</p>}
            </div>

            {formError && (
              <div className="rounded-2xl border border-accent/20 bg-accent-soft/50 p-3 text-xs text-accent">
                {formError}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="mt-4 w-full rounded-full bg-primary px-5 py-3 text-sm font-semibold text-white shadow-sm hover:opacity-95 disabled:opacity-50 transition-opacity"
            >
              {isSubmitting ? "Giriş yapılıyor…" : "Giriş Yap"}
            </button>

          </form>
        </div>
      </section>
    </div>
  );
}

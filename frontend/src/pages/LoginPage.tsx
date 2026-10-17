import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { api, isApiError } from "../api/client";
import type { Me } from "../api/types";

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
      navigate("/", { replace: true });
    } catch (error) {
      setFormError(isApiError(error) ? error.message : "Giriş yapılamadı.");
    }
  }

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-2">
      <section className="hidden flex-col justify-between px-8 py-10 sm:px-14 lg:flex">
        <p className="font-serif text-2xl">ProvaMüşteri</p>
        <div className="max-w-md py-16">
          <h1 className="font-serif text-5xl leading-[1.05] tracking-tight">
            Müşteriyle konuş. Sonra neyin tuttuğunu gör.
          </h1>
          <p className="mt-5 max-w-sm text-lg text-muted">
            İşletmenin kendi kurallarıyla sesli ya da yazılı prova. Kayıt sende kalır, puan görüşmeden çıkar.
          </p>
        </div>
        <p className="text-sm text-muted">Türkçe · ses en fazla 30 saniye</p>
      </section>

      <section className="flex min-h-screen items-center bg-card px-8 py-12 sm:px-14">
        <form onSubmit={handleSubmit(onSubmit)} className="w-full max-w-sm" noValidate>
          <p className="font-serif text-2xl lg:hidden">ProvaMüşteri</p>
          <h2 className="mt-8 font-serif text-3xl lg:mt-0">Giriş</h2>
          <label className="mt-8 block text-sm text-muted" htmlFor="email">
            E-posta
          </label>
          <input
            id="email"
            type="email"
            autoComplete="username"
            className="mt-1 w-full border-b border-line bg-transparent py-2 outline-none focus:border-ink"
            {...register("email")}
          />
          {errors.email && <p className="mt-1 text-sm text-accent">{errors.email.message}</p>}

          <label className="mt-6 block text-sm text-muted" htmlFor="password">
            Şifre
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            className="mt-1 w-full border-b border-line bg-transparent py-2 outline-none focus:border-ink"
            {...register("password")}
          />
          {errors.password && <p className="mt-1 text-sm text-accent">{errors.password.message}</p>}

          {formError && <p className="mt-4 text-sm text-accent">{formError}</p>}

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-8 rounded-full bg-ink px-5 py-2.5 text-paper disabled:opacity-60"
          >
            {isSubmitting ? "Giriliyor…" : "Giriş yap"}
          </button>
        </form>
      </section>
    </div>
  );
}

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { api } from "../api/client";
import type { Health, Me } from "../api/types";
import { AssignModal } from "./AssignModal";
import { ThemePicker } from "./ThemePicker";
import { BrandLogo } from "./BrandLogo";

export function Shell() {
  const [quickAssignOpen, setQuickAssignOpen] = useState(false);

  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<Health>("/health"),
    staleTime: 30_000,
  });

  if (!me.data) return null;
  const { user, organization } = me.data;
  const model = health.data?.model_service;
  const isManager = user.role === "manager";

  return (
    <div className="min-h-screen bg-paper text-ink transition-colors duration-200">
      <header className="sticky top-0 z-40 border-b border-line bg-card/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-3 sm:gap-4 sm:px-5">
          {/* Logo & Brand */}
          <Link to="/" className="flex items-center gap-2 group">
            <BrandLogo />
            <span className="font-serif text-lg tracking-tight text-ink font-semibold sm:text-xl">
              ProvaMüşteri
            </span>
          </Link>

          {/* Navigasyon Linkleri */}
          <nav className="hidden items-center gap-1 sm:flex ml-4">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted hover:text-ink hover:bg-card-subtle"
                }`
              }
            >
              {isManager ? "Eğitim Kataloğu" : "Eğitimlerim"}
            </NavLink>

            {isManager && (
              <NavLink
                to="/admin"
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-muted hover:text-ink hover:bg-card-subtle"
                  }`
                }
              >
                Yönetici Paneli
              </NavLink>
            )}
          </nav>

          {/* Sağ Alan: Hızlı Butonlar, Tema Değiştirici ve Profil */}
          <div className="ml-auto flex items-center gap-2 text-sm sm:gap-3">
            {/* Model & Demo Rozetleri */}
            {model === "stub" && (
              <span className="hidden sm:inline-flex rounded-full bg-warn-soft/80 border border-warn/30 px-2.5 py-0.5 text-xs font-medium text-warn">
                Sahte model
              </span>
            )}
            {model === "down" && (
              <span className="rounded-full bg-accent-soft px-2.5 py-0.5 text-xs text-accent">
                Model Kapalı
              </span>
            )}

            {/* Yönetici için Hızlı Atama Butonu */}
            {isManager && (
              <button
                type="button"
                onClick={() => setQuickAssignOpen(true)}
                className="hidden md:flex items-center gap-1.5 rounded-full bg-primary/10 border border-primary/30 px-3 py-1.5 text-xs font-semibold text-primary hover:bg-primary hover:text-white transition-all"
              >
                <span>+</span>
                <span>Atama Yap</span>
              </button>
            )}

            <ThemePicker />
            <Link to="/change-password" aria-label="Şifremi değiştir" title="Şifremi değiştir" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-line bg-card-subtle text-muted hover:text-primary">
              <svg aria-hidden="true" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3" /></svg>
            </Link>

            {/* Kullanıcı Profili ve Rol */}
            <div className="flex items-center gap-2 pl-1 sm:border-l sm:border-line">
              <div className="flex flex-col text-right">
                <span className="hidden sm:inline font-medium text-xs text-ink leading-tight">
                  {user.display_name}
                </span>
                <span className="hidden sm:inline text-[11px] text-muted">
                  {isManager ? "Yönetici" : "Çalışan"} · {organization.name}
                </span>
              </div>
            </div>

            {/* Çıkış */}
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void api("/auth/logout", { method: "POST" }).finally(() => {
                  window.location.assign("/login");
                });
              }}
            >
              <button
                type="submit"
                className="rounded-full border border-line px-3 py-1 text-xs text-muted hover:text-accent hover:border-accent/40 transition-colors"
              >
                Çıkış
              </button>
            </form>
          </div>
        </div>
      </header>

      {/* Alt Mobil Menü */}
      {isManager && (
        <div className="sm:hidden flex border-b border-line bg-card px-5 py-2 gap-3 text-xs">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              isActive ? "font-semibold text-primary" : "text-muted"
            }
          >
            Eğitimler
          </NavLink>
          <NavLink
            to="/admin"
            className={({ isActive }) =>
              isActive ? "font-semibold text-primary" : "text-muted"
            }
          >
            Yönetici Paneli
          </NavLink>
          <button
            type="button"
            onClick={() => setQuickAssignOpen(true)}
            className="ml-auto font-medium text-primary"
          >
            + Atama Yap
          </button>
        </div>
      )}

      <main className="mx-auto max-w-6xl px-5 py-8">
        <Outlet />
      </main>

      {/* Hızlı Atama Modalı */}
      <AssignModal
        open={quickAssignOpen}
        onClose={() => setQuickAssignOpen(false)}
      />
    </div>
  );
}

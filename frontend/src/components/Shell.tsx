import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { api } from "../api/client";
import type { Health, Me } from "../api/types";
import { AssignModal } from "./AssignModal";
import { useTheme } from "../lib/theme";

export function Shell() {
  const { theme, toggleTheme } = useTheme();
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
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-5 py-3">
          {/* Logo & Brand */}
          <Link to="/" className="flex items-center gap-2 group">
            <div className="h-8 w-8 rounded-xl bg-gradient-to-tr from-primary to-sky-400 text-white flex items-center justify-center font-bold text-sm shadow-xs group-hover:scale-105 transition-transform">
              P
            </div>
            <span className="font-serif text-xl tracking-tight text-ink font-semibold">
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
          <div className="ml-auto flex items-center gap-3 text-sm">
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

            {/* Tema Değiştirme Butonu */}
            <button
              type="button"
              onClick={toggleTheme}
              aria-label="Temayı değiştir"
              title={theme === "dark" ? "Açık Temaya Geç (Çok Açık Mavi)" : "Karanlık Temaya Geç (Lacivert)"}
              className="flex items-center justify-center h-8 w-8 rounded-full border border-line bg-card-subtle text-ink hover:border-primary/40 transition-colors cursor-pointer"
            >
              {theme === "dark" ? (
                // Güneş ikonu (açık temaya geçiş)
                <svg
                  className="w-4 h-4 text-amber-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
                  />
                </svg>
              ) : (
                // Ay ikonu (lacivert temaya geçiş)
                <svg
                  className="w-4 h-4 text-sky-700"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
                  />
                </svg>
              )}
            </button>

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

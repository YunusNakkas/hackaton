import { useQuery } from "@tanstack/react-query";
import { Link, NavLink, Outlet } from "react-router-dom";
import { api } from "../api/client";
import type { Health, Me } from "../api/types";

export function Shell() {
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<Health>("/health"),
    staleTime: 30_000,
  });

  if (!me.data) return null;
  const { user, organization } = me.data;
  const model = health.data?.model_service;

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-card/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center gap-4 px-5 py-3.5">
          <Link to="/" className="font-serif text-xl tracking-tight text-ink">
            ProvaMüşteri
          </Link>
          <nav className="hidden items-center gap-4 text-sm text-muted sm:flex">
            <NavLink to="/" end className={({ isActive }) => (isActive ? "text-ink" : "hover:text-ink")}>
              Eğitimler
            </NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            {model === "stub" && (
              <span className="rounded-full bg-warn-soft px-2.5 py-0.5 whitespace-nowrap text-warn">Sahte model</span>
            )}
            {model === "down" && (
              <span className="rounded-full bg-accent-soft px-2.5 py-0.5 whitespace-nowrap text-accent">
                Model kapalı
              </span>
            )}
            <span className="hidden text-muted md:inline">{organization.name}</span>
            <span className="hidden text-ink sm:inline">{user.display_name}</span>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void api("/auth/logout", { method: "POST" }).finally(() => {
                  window.location.assign("/login");
                });
              }}
            >
              <button type="submit" className="text-muted hover:text-ink">
                Çıkış
              </button>
            </form>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-5 py-8">
        <Outlet />
      </main>
    </div>
  );
}

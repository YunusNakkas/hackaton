import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { api, isApiError } from "./api/client";
import type { Me } from "./api/types";
import { Shell } from "./components/Shell";
import { ThemeProvider } from "./lib/theme";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { SessionPage } from "./pages/SessionPage";
import { TrainingPage } from "./pages/TrainingPage";

const AdminPage = lazy(() => import("./pages/AdminPage").then(module => ({ default: module.AdminPage })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (count, error) => !(isApiError(error) && (error.status === 401 || error.status === 404)) && count < 1,
      refetchOnWindowFocus: false,
    },
  },
});

function Splash() {
  return (
    <div className="grid min-h-screen place-items-center font-serif text-2xl text-muted bg-paper">
      ProvaMüşteri
    </div>
  );
}

function Gate() {
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me"), retry: false });
  if (me.isLoading) return <Splash />;
  if (!me.data) return <Navigate to="/login" replace />;
  return <Shell />;
}

function ManagerRoute() {
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me"), retry: false });
  if (me.isLoading) return <Splash />;
  if (me.data?.user.role !== "manager") return <Navigate to="/" replace />;
  return <Suspense fallback={<Splash />}><AdminPage /></Suspense>;
}

function Guest() {
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me"), retry: false });
  if (me.isLoading) return <Splash />;
  if (me.data) return <Navigate to={me.data.user.role === "manager" ? "/admin" : "/"} replace />;
  return <LoginPage />;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Guest />} />
            <Route element={<Gate />}>
              <Route path="/" element={<HomePage />} />
              <Route path="/admin" element={<ManagerRoute />} />
              <Route path="/trainings/:trainingId" element={<TrainingPage />} />
              <Route path="/sessions/:sessionId" element={<SessionPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

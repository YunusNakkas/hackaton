import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { api, isApiError } from "./api/client";
import type { Me } from "./api/types";
import { Shell } from "./components/Shell";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { SessionPage } from "./pages/SessionPage";
import { TrainingPage } from "./pages/TrainingPage";

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
    <div className="grid min-h-screen place-items-center font-serif text-2xl text-muted">ProvaMüşteri</div>
  );
}

function Gate() {
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me"), retry: false });
  if (me.isLoading) return <Splash />;
  if (!me.data) return <Navigate to="/login" replace />;
  return <Shell />;
}

function Guest() {
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me"), retry: false });
  if (me.isLoading) return <Splash />;
  if (me.data) return <Navigate to="/" replace />;
  return <LoginPage />;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Guest />} />
          <Route element={<Gate />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/trainings/:trainingId" element={<TrainingPage />} />
            <Route path="/sessions/:sessionId" element={<SessionPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

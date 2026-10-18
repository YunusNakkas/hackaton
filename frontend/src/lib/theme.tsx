import React, { createContext, useContext, useEffect, useLayoutEffect, useState } from "react";

export type Theme = "light" | "dark" | "quartz" | "charcoal";

export const themeLogo = (theme: Theme) =>
  theme === "quartz" || theme === "charcoal" ? "/logo-orange.png"
    : theme === "dark" ? "/logo-light-blue.png" : "/logo-blue.png";

export const themes: { id: Theme; name: string; background: string; accent: string }[] = [
  { id: "light", name: "Açık mavi", background: "#F0F7FF", accent: "#0284C7" },
  { id: "dark", name: "Lacivert", background: "#080F24", accent: "#38BDF8" },
  { id: "quartz", name: "Kuvars · Turuncu", background: "#F5F1ED", accent: "#C2410C" },
  { id: "charcoal", name: "Koyu gri · Turuncu", background: "#141414", accent: "#FB923C" },
];

interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

function readTheme(): Theme {
  try {
    const saved = localStorage.getItem("pm_theme");
    if (themes.some(option => option.id === saved)) return saved as Theme;
  } catch { /* Depolama kapalıysa tema bellekte çalışmaya devam eder. */ }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readTheme);

  useEffect(() => {
    function sync(event: StorageEvent) {
      if (event.key === "pm_theme" || event.key === null) setThemeState(readTheme());
    }
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);

  useLayoutEffect(() => {
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);
    root.style.colorScheme = theme === "dark" || theme === "charcoal" ? "dark" : "light";
    document.querySelector('link[rel="icon"]')?.setAttribute("href", themeLogo(theme));
    document.querySelector('link[rel="apple-touch-icon"]')?.setAttribute("href", themeLogo(theme));
    if (theme === "dark" || theme === "charcoal") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
    try { localStorage.setItem("pm_theme", theme); } catch { /* Tercihi saklayamamak sayfayı engellemez. */ }
  }, [theme]);

  const setTheme = (t: Theme) => {
    setThemeState(t);
  };

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}

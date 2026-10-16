/** Theme (dark default + light) + Persian formatting helpers. */
import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

export type Theme = "dark" | "light";
const THEME_KEY = "gi_theme";

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* ignore */
  }
  return "dark";
}

const ThemeCtx = createContext<{ theme: Theme; setTheme: (t: Theme) => void }>({
  theme: "dark",
  setTheme: () => {},
});

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(initialTheme);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* ignore */
    }
  }, [theme]);
  return (
    <ThemeCtx.Provider value={{ theme, setTheme: setThemeState }}>
      {children}
    </ThemeCtx.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeCtx);
}

// --- fa formatting (numbers, percent, dates) ---
const faNum = new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 4 });

export function fa(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("fa-IR", {
    maximumFractionDigits: digits,
  }).format(n);
}

export function faInt(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return faNum.format(Math.round(n));
}

export function faPct(x: number | null | undefined, digits = 1): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  return `${new Intl.NumberFormat("fa-IR", { maximumFractionDigits: digits }).format(x * 100)}٪`;
}

const faDate = new Intl.DateTimeFormat("fa-IR", {
  dateStyle: "medium",
  timeStyle: "short",
});

const faDateOnly = new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium" });

export function faDateTime(iso: string | null | undefined, withTime = true): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  try {
    return (withTime ? faDate : faDateOnly).format(d);
  } catch {
    return "—";
  }
}

/** قرارداد واقعی importance: ۱ = بالاترین، ۱۰ = کمترین (Backend معکوس است). */
export function importanceLabel(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${faInt(v)} از ۱۰ (۱=بالاترین)`;
}

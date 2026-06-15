"use client";

import {Moon, Sun} from "lucide-react";
import {useEffect, useState} from "react";
import {Button} from "@/components/ui/button";
import {useTranslation} from "@/lib/i18n";

type Theme = "light" | "dark";

function resolveInitialTheme(): Theme {
  if (typeof window === "undefined") return "light";
  const saved = localStorage.getItem("smsbridge-theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
}

export function ThemeToggle() {
  const {t} = useTranslation();
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    const initial = resolveInitialTheme();
    setTheme(initial);
    applyTheme(initial);
  }, []);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("smsbridge-theme", next);
    applyTheme(next);
  }

  return (
    <Button
      aria-label={theme === "dark" ? t("common.switchToLight") : t("common.switchToDark")}
      className="h-9 w-9 shrink-0 px-0"
      onClick={toggleTheme}
      title={theme === "dark" ? t("common.switchToLight") : t("common.switchToDark")}
      type="button"
      variant="secondary"
    >
      {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
    </Button>
  );
}

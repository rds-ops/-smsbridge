"use client";

import Link from "next/link";
import {Check, Copy, Globe2, Loader2} from "lucide-react";
import {useState} from "react";
import {useTranslation} from "@/lib/i18n";
import {money} from "@/lib/shared/format";

export function PageShell({children, wide = false}: {children: React.ReactNode; wide?: boolean}) {
  return <main className={`mx-auto w-full ${wide ? "max-w-7xl" : "max-w-6xl"} px-4 py-8 lg:px-6`}>{children}</main>;
}

export function PageHeader({
  title,
  description,
  actions
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4 border-b border-line pb-5 md:flex-row md:items-end md:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-normal md:text-3xl">{title}</h1>
        {description && <p className="mt-2 max-w-3xl text-sm leading-6 text-neutral-600">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Card({
  title,
  description,
  children,
  className = ""
}: {
  title?: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`min-w-0 rounded-lg border border-line bg-white p-5 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-slate-200/70 ${className}`}>
      {(title || description) && (
        <div className="mb-4">
          {title && <h2 className="text-base font-semibold">{title}</h2>}
          {description && <p className="mt-1 text-sm leading-6 text-neutral-600">{description}</p>}
        </div>
      )}
      {children}
    </section>
  );
}

export function MetricCard({label, value, helper}: {label: string; value: React.ReactNode; helper?: string}) {
  return (
    <Card className="p-4">
      <p className="text-sm text-neutral-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-normal">{value}</p>
      {helper && <p className="mt-2 text-xs leading-5 text-neutral-500">{helper}</p>}
    </Card>
  );
}

export function Alert({type = "info", children}: {type?: "info" | "success" | "error"; children: React.ReactNode}) {
  const classes = {
    info: "border-blue-200 bg-blue-50 text-blue-900",
    success: "border-green-200 bg-green-50 text-green-900",
    error: "border-red-200 bg-red-50 text-red-800"
  }[type];
  return <div className={`rounded-md border p-3 text-sm leading-6 ${classes}`}>{children}</div>;
}

export function Toast({type = "success", message}: {type?: "success" | "error"; message: string}) {
  if (!message) return null;
  return (
    <div className={`fixed right-4 top-20 z-50 max-w-sm rounded-md border p-3 text-sm shadow-lg ${type === "success" ? "border-green-200 bg-green-50 text-green-900" : "border-red-200 bg-red-50 text-red-800"}`}>
      {message}
    </div>
  );
}

export function StatusBadge({status}: {status: string}) {
  const {t} = useTranslation();
  const pending = ["created", "reserved", "waiting_sms"].includes(status);
  const map: Record<string, string> = {
    active: "bg-green-50 text-green-700 ring-green-200",
    completed: "bg-green-50 text-green-700 ring-green-200",
    sms_received: "bg-cyan-50 text-cyan-700 ring-cyan-200",
    waiting_sms: "bg-amber-50 text-amber-800 ring-amber-200",
    created: "bg-slate-50 text-slate-700 ring-slate-200",
    reserved: "bg-slate-50 text-slate-700 ring-slate-200",
    cancelled: "bg-neutral-100 text-neutral-700 ring-neutral-200",
    expired: "bg-orange-50 text-orange-800 ring-orange-200",
    refunded: "bg-blue-50 text-blue-700 ring-blue-200",
    failed: "bg-red-50 text-red-700 ring-red-200",
    blocked: "bg-red-50 text-red-700 ring-red-200",
    limited: "bg-amber-50 text-amber-800 ring-amber-200",
    inactive: "bg-neutral-100 text-neutral-700 ring-neutral-200"
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ring-1 ring-inset transition-all duration-200 ${pending ? "pending-glow" : ""} ${map[status] || "bg-slate-50 text-slate-700 ring-slate-200"}`}>
      {t(`status.${status}`)}
    </span>
  );
}

export function EmptyState({title, description, action}: {title: string; description?: string; action?: React.ReactNode}) {
  return (
    <div className="rounded-md border border-dashed border-line bg-panel p-8 text-center">
      <h3 className="font-medium">{title}</h3>
      {description && <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-neutral-600">{description}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function CopyButton({value, label = "Copy"}: {value?: string | null; label?: string}) {
  const [copied, setCopied] = useState(false);
  const {t} = useTranslation();
  if (!value) return null;
  async function copy() {
    await navigator.clipboard.writeText(value || "");
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }
  return (
    <button className="btn btn-secondary px-2 py-1 text-xs" onClick={copy} title={label}>
      {copied ? <Check size={14} /> : <Copy size={14} />}
      {copied ? t("common.copied") : label === "Copy" ? t("common.copy") : label}
    </button>
  );
}

export function ActionLink({href, children}: {href: string; children: React.ReactNode}) {
  return <Link className="btn btn-secondary" href={href}>{children}</Link>;
}

export function LanguageSwitcher({compact = false}: {compact?: boolean}) {
  const {locale, setLocale, t} = useTranslation();
  const next = locale === "en" ? "ru" : "en";
  return (
    <button
      className={`btn btn-secondary ${compact ? "px-2" : "px-3"}`}
      onClick={() => setLocale(next)}
      title={locale === "en" ? t("common.switchToRussian") : t("common.switchToEnglish")}
    >
      <Globe2 size={16} />
      {locale.toUpperCase()}
    </button>
  );
}

export function MoneyValue({value, currency}: {value?: unknown; currency?: string}) {
  return <>{money(value, currency)}</>;
}

export function HelpText({children}: {children: React.ReactNode}) {
  return <p className="text-sm leading-6 text-neutral-600">{children}</p>;
}

export function LoadingState({message}: {message?: string}) {
  const {t} = useTranslation();
  return (
    <div className="flex items-center gap-2 rounded-md border border-line bg-white p-4 text-sm text-neutral-600">
      <Loader2 size={16} className="animate-spin text-accent" />
      {message || t("common.loading")}
    </div>
  );
}

export function ErrorState({message}: {message: string}) {
  return <Alert type="error">{message}</Alert>;
}

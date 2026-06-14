"use client";

import {useState} from "react";
import {useRouter} from "next/navigation";
import {auth} from "@/lib/shared/api";
import {useTranslation} from "@/lib/i18n";
import type {Locale} from "@/lib/i18n";

export default function RegisterPage() {
  const router = useRouter();
  const {t, locale: currentLocale, setLocale: setAppLocale} = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [locale, setLocale] = useState<Locale>(currentLocale);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      setAppLocale(locale);
      await auth("/auth/register", {email, password, locale});
      const next = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("next") : null;
      router.push(next || "/");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("auth.registrationFailed"));
    }
  }

  return (
    <main className="mx-auto max-w-md px-4 py-12">
      <div className="rounded-xl border border-line bg-white p-6 shadow-sm">
      <h1 className="text-2xl font-semibold">{t("auth.createAccount")}</h1>
      <form onSubmit={submit} className="mt-6 grid gap-4">
        <input className="field" value={email} onChange={(e) => setEmail(e.target.value)} placeholder={t("common.email")} />
        <input className="field" value={password} onChange={(e) => setPassword(e.target.value)} placeholder={t("auth.passwordHint")} type="password" />
        <label className="grid gap-2 text-sm font-medium">
          {t("auth.locale")}
        <select className="field" value={locale} onChange={(e) => setLocale(e.target.value as Locale)}>
          <option value="en">{t("common.english")}</option>
          <option value="ru">{t("common.russian")}</option>
        </select>
        </label>
        {error && <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        <button className="btn btn-primary" type="submit">{t("auth.signUp")}</button>
      </form>
      </div>
    </main>
  );
}

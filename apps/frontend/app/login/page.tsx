"use client";

import {useState} from "react";
import {useRouter} from "next/navigation";
import Link from "next/link";
import {auth} from "@/lib/shared/api";
import {useTranslation} from "@/lib/i18n";

export default function LoginPage() {
  const router = useRouter();
  const {t} = useTranslation();
  const [email, setEmail] = useState("user@smsbridge.local");
  const [password, setPassword] = useState("change-me");
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const session = await auth("/auth/login", {email, password});
      const role = session.user && typeof session.user === "object" && "role" in session.user
        ? String((session.user as {role: unknown}).role)
        : "user";
      const next = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("next") : null;
      router.push(role === "admin" ? "/admin" : next || "/");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("auth.loginFailed"));
    }
  }

  return (
    <main className="mx-auto max-w-md px-4 py-12">
      <div className="rounded-xl border border-line bg-white p-6 shadow-sm">
      <h1 className="text-2xl font-semibold">{t("auth.signIn")}</h1>
      <form onSubmit={submit} className="mt-6 grid gap-4">
        <input className="field" value={email} onChange={(e) => setEmail(e.target.value)} placeholder={t("common.email")} />
        <input className="field" value={password} onChange={(e) => setPassword(e.target.value)} placeholder={t("auth.password")} type="password" />
        {error && <p className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        <button className="btn btn-primary" type="submit">{t("auth.signIn")}</button>
      </form>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <button className="btn btn-secondary" onClick={() => setEmail("admin@smsbridge.local")}>{t("auth.useAdmin")}</button>
        <button className="btn btn-secondary" onClick={() => setEmail("user@smsbridge.local")}>{t("auth.useTestUser")}</button>
      </div>
      <p className="mt-4 text-sm text-neutral-600">{t("auth.noAccount")} <Link className="text-accent" href="/register">{t("auth.createOne")}</Link></p>
      </div>
    </main>
  );
}

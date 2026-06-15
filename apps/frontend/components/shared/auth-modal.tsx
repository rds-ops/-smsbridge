"use client";

import {useEffect, useState} from "react";
import {Loader2} from "lucide-react";
import {Alert} from "@/components/shared/ui";
import {Button} from "@/components/ui/button";
import {Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle} from "@/components/ui/dialog";
import {Input} from "@/components/ui/input";
import {Tabs, TabsList, TabsTrigger} from "@/components/ui/tabs";
import {auth, currentUser} from "@/lib/shared/api";
import type {User} from "@/lib/shared/types";
import {useTranslation} from "@/lib/i18n";
import type {Locale} from "@/lib/i18n";

export type AuthMode = "login" | "register";

export function AuthModal({
  initialMode = "login",
  onClose,
  onSuccess,
  open
}: {
  initialMode?: AuthMode;
  onClose: () => void;
  onSuccess: (user: User) => void;
  open: boolean;
}) {
  const {t, locale, setLocale} = useTranslation();
  const [mode, setMode] = useState<AuthMode>(initialMode);
  const [email, setEmail] = useState("user@smsbridge.local");
  const [password, setPassword] = useState("change-me");
  const [selectedLocale, setSelectedLocale] = useState<Locale>(locale);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setMode(initialMode);
    setSelectedLocale(locale);
    setError("");
  }, [initialMode, locale, open]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (mode === "register") setLocale(selectedLocale);
      const session = await auth(mode === "login" ? "/auth/login" : "/auth/register", mode === "login" ? {email, password} : {email, password, locale: selectedLocale});
      const user = session.user ? session.user as User : (await currentUser()) as User;
      onSuccess(user);
    } catch (err) {
      setError(err instanceof Error ? err.message : mode === "login" ? t("auth.loginFailed") : t("auth.registrationFailed"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("buy.authGateTitle")}</DialogTitle>
          <DialogDescription>{t("buy.authGateDesc")}</DialogDescription>
        </DialogHeader>
        <Tabs className="mt-5" value={mode} onValueChange={(value) => setMode(value as AuthMode)}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="login">{t("nav.login")}</TabsTrigger>
            <TabsTrigger value="register">{t("nav.register")}</TabsTrigger>
          </TabsList>
        </Tabs>
        <form className="mt-5 grid gap-3" onSubmit={submit}>
          <Input value={email} onChange={(event) => setEmail(event.target.value)} placeholder={t("common.email")} />
          <Input value={password} onChange={(event) => setPassword(event.target.value)} placeholder={mode === "login" ? t("auth.password") : t("auth.passwordHint")} type="password" />
          {mode === "register" && (
            <select className="field" value={selectedLocale} onChange={(event) => setSelectedLocale(event.target.value as Locale)}>
              <option value="en">{t("common.english")}</option>
              <option value="ru">{t("common.russian")}</option>
            </select>
          )}
          {error && <Alert type="error">{error}</Alert>}
          <Button disabled={loading} type="submit">
            {loading ? <Loader2 size={16} className="animate-spin" /> : null}
            {mode === "login" ? t("auth.signIn") : t("auth.signUp")}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

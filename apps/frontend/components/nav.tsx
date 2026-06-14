"use client";

import Link from "next/link";
import {usePathname, useRouter} from "next/navigation";
import {BookOpen, ClipboardList, LogOut, ShieldCheck, Truck, Wallet} from "lucide-react";
import {useEffect, useState} from "react";
import {LanguageSwitcher} from "@/components/shared/ui";
import {Button} from "@/components/ui/button";
import {getBalance} from "@/lib/client/api";
import {currentUser, getToken, logout} from "@/lib/shared/api";
import {money} from "@/lib/shared/format";
import type {User, Wallet as WalletType} from "@/lib/shared/types";
import {useTranslation} from "@/lib/i18n";

const publicRoutes = new Set([
  "/",
  "/buy",
  "/login",
  "/register",
  "/acceptable-use",
  "/terms",
  "/privacy",
  "/abuse",
  "/developer-commands",
  "/supplier"
]);

export function Nav({children}: {children?: React.ReactNode}) {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [balance, setBalance] = useState<WalletType | null>(null);
  const isPublic = publicRoutes.has(pathname);

  useEffect(() => {
    let active = true;
    const syncAuth = async () => {
      if (!getToken()) {
        if (active) {
          setUser(null);
          setBalance(null);
        }
        if (!isPublic) router.replace("/login");
        return;
      }
      try {
        const [me, wallet] = await Promise.all([currentUser(), getBalance()]);
        if (active) {
          setUser(me as User);
          setBalance(wallet);
        }
      } catch {
        if (active) {
          setUser(null);
          setBalance(null);
        }
        if (!isPublic) router.replace("/login");
      }
    };
    syncAuth();
    window.addEventListener("smsbridge-auth-changed", syncAuth);
    window.addEventListener("smsbridge-data-changed", syncAuth);
    window.addEventListener("storage", syncAuth);
    return () => {
      active = false;
      window.removeEventListener("smsbridge-auth-changed", syncAuth);
      window.removeEventListener("smsbridge-data-changed", syncAuth);
      window.removeEventListener("storage", syncAuth);
    };
  }, [isPublic, router]);

  return (
    <div className="min-h-screen bg-[#f6f8fb]">
      <TopNavigation balance={balance} pathname={pathname} user={user} />
      {children}
    </div>
  );
}

function TopNavigation({balance, pathname, user}: {balance: WalletType | null; pathname: string; user: User | null}) {
  const {t} = useTranslation();
  const signedIn = Boolean(user);
  const linkClass = (href: string) => {
    const active = pathname === href || (href !== "/" && pathname.startsWith(href));
    return `inline-flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium transition ${
      active ? "bg-blue-50 text-accent" : "text-neutral-600 hover:bg-slate-50 hover:text-slate-950"
    }`;
  };

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-white/90 backdrop-blur">
      <div className="mx-auto grid w-full max-w-7xl grid-cols-1 gap-3 px-4 py-2.5 lg:grid-cols-[auto_minmax(0,1fr)_auto] lg:items-center lg:gap-4 lg:px-6">
        <div className="flex min-w-0 items-center justify-between gap-3">
          <Link href="/" className="flex shrink-0 items-center gap-2 text-lg font-semibold tracking-normal">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent text-sm font-bold text-white">sb</span>
            smsbridge
          </Link>
          <div className="lg:hidden"><LanguageSwitcher compact /></div>
        </div>

        <nav className="flex min-w-0 items-center gap-1 overflow-x-auto pb-1 lg:justify-center lg:pb-0">
          <Link className={linkClass("/")} href="/">{t("common.publicHome")}</Link>
          <Link className={linkClass("/orders")} href="/orders"><ClipboardList size={16} />{t("nav.orders")}</Link>
          <Link className={linkClass("/deposit")} href="/deposit"><Wallet size={16} />{t("nav.deposit")}</Link>
          <Link className={linkClass("/api-docs")} href="/api-docs"><BookOpen size={16} />{t("nav.api")}</Link>
          <Link className={linkClass("/abuse")} href="/abuse">{t("nav.support")}</Link>
        </nav>

        <div className="flex min-w-0 shrink-0 items-center justify-end gap-2 overflow-x-auto lg:overflow-visible">
          {signedIn ? (
            <>
              <div className="flex shrink-0 items-center gap-1.5 rounded-lg border border-line bg-slate-50 px-2.5 py-1.5 text-xs sm:text-sm">
                <Wallet size={15} className="text-accent" />
                <span className="hidden text-neutral-500 xl:inline">{t("common.availableBalance")}</span>
                <strong>{money(balance?.balance, balance?.currency)}</strong>
              </div>
              <Link className={`${linkClass("/settings")} max-w-[150px] truncate`} href="/settings" title={user?.email || undefined}>{user?.email}</Link>
              <div className="hidden lg:block"><LanguageSwitcher compact /></div>
              {user?.role === "admin" && <Link className="btn btn-secondary shrink-0 px-2.5 py-1.5 text-sm" href="/admin"><ShieldCheck size={15} />{t("nav.admin")}</Link>}
              <Link className="btn btn-secondary shrink-0 px-2.5 py-1.5 text-sm" href="/supplier"><Truck size={15} />{t("nav.supplier")}</Link>
              <Button className="shrink-0 px-2.5 py-1.5 text-sm" onClick={logout} variant="secondary">
                <LogOut size={15} />
                {t("nav.logout")}
              </Button>
            </>
          ) : (
            <>
              <Link className="btn btn-secondary" href="/login">{t("nav.login")}</Link>
              <Link className="btn btn-primary" href="/register">{t("nav.register")}</Link>
              <Link className="hidden shrink-0 items-center gap-1.5 rounded-xl border border-border bg-white px-2.5 py-1.5 text-sm font-medium text-foreground hover:bg-muted sm:inline-flex" href="/supplier">
                <Truck size={15} />
                {t("nav.supplier")}
              </Link>
              <div className="hidden lg:block"><LanguageSwitcher compact /></div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

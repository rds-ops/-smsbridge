"use client";

import Link from "next/link";
import {usePathname, useRouter} from "next/navigation";
import {
  BarChart3,
  BookOpen,
  ClipboardList,
  LayoutDashboard,
  LogOut,
  PlusCircle,
  Settings,
  ShieldCheck,
  Truck,
  Wallet
} from "lucide-react";
import type {LucideIcon} from "lucide-react";
import {useEffect, useMemo, useState} from "react";
import {LanguageSwitcher} from "@/components/shared/ui";
import {useTranslation} from "@/lib/i18n";
import {currentUser, getToken, logout} from "@/lib/shared/api";
import {getBalance} from "@/lib/client/api";
import type {User, Wallet as WalletType} from "@/lib/shared/types";
import {money} from "@/lib/shared/format";

const publicRoutes = new Set(["/", "/login", "/register", "/acceptable-use", "/terms", "/privacy", "/abuse", "/developer-commands", "/supplier"]);

type NavLink = {href: string; label: string; icon: LucideIcon};

export function Nav({children}: {children?: React.ReactNode}) {
  const pathname = usePathname();
  const router = useRouter();
  const {t} = useTranslation();
  const [user, setUser] = useState<User | null>(null);
  const [balance, setBalance] = useState<WalletType | null>(null);
  const [loadingUser, setLoadingUser] = useState(true);

  const isPublic = publicRoutes.has(pathname || "/");
  const signedIn = Boolean(user);

  useEffect(() => {
    let active = true;
    const syncAuth = async () => {
      const hasToken = Boolean(getToken());
      if (!hasToken) {
        if (active) {
          setUser(null);
          setBalance(null);
          setLoadingUser(false);
        }
        if (!isPublic) router.replace("/login");
        return;
      }
      try {
        const [me, wallet] = await Promise.all([currentUser(), getBalance()]);
        if (active) {
          setUser(me);
          setBalance(wallet);
          setLoadingUser(false);
        }
      } catch {
        if (active) {
          setUser(null);
          setBalance(null);
          setLoadingUser(false);
        }
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
  }, [pathname, isPublic, router]);

  const links = useMemo(() => {
    const base = [
      {href: "/dashboard", label: t("nav.dashboard"), icon: LayoutDashboard},
      {href: "/deposit", label: t("nav.deposit"), icon: Wallet},
      {href: "/buy", label: t("nav.buy"), icon: PlusCircle},
      {href: "/orders", label: t("nav.orders"), icon: ClipboardList},
      {href: "/api-docs", label: t("nav.api"), icon: BookOpen},
      {href: "/settings", label: t("nav.settings"), icon: Settings}
    ];
    if (user?.role === "admin") base.push({href: "/admin", label: t("nav.admin"), icon: ShieldCheck});
    return base;
  }, [t, user?.role]);

  if (!signedIn || isPublic) {
    return (
      <>
        <PublicHeader signedIn={signedIn} user={user} />
        {children}
      </>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <AppSidebar links={links} pathname={pathname || "/"} user={user} balance={balance} />
      <div className="lg:pl-72">
        <TopBar user={user} balance={balance} loadingUser={loadingUser} links={links} pathname={pathname || "/"} />
        {children}
      </div>
    </div>
  );
}

function PublicHeader({signedIn, user}: {signedIn: boolean; user: User | null}) {
  const {t} = useTranslation();
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3">
        <Link href="/" className="flex items-center gap-2 text-lg font-semibold tracking-normal">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent text-sm font-bold text-white">sb</span>
          smsbridge
        </Link>
        <nav className="flex items-center gap-2">
          {signedIn && user ? (
            <Link className="btn btn-secondary" href={user.role === "admin" ? "/admin" : "/dashboard"}>{t("common.openDashboard")}</Link>
          ) : (
            <>
              <Link className="hidden rounded-md px-3 py-2 text-sm text-neutral-600 hover:bg-panel sm:inline-flex" href="/login">{t("nav.login")}</Link>
              <Link className="hidden rounded-md px-3 py-2 text-sm text-neutral-600 hover:bg-panel sm:inline-flex" href="/supplier">{t("nav.supplier")}</Link>
              <Link className="btn btn-primary" href="/register">{t("nav.register")}</Link>
            </>
          )}
          <LanguageSwitcher compact />
        </nav>
      </div>
    </header>
  );
}

export function AppSidebar({
  links,
  pathname,
  user,
  balance
}: {
  links: NavLink[];
  pathname: string;
  user: User | null;
  balance: WalletType | null;
}) {
  const {t} = useTranslation();
  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-72 border-r border-slate-200 bg-white lg:flex lg:flex-col">
      <div className="flex h-16 items-center gap-3 border-b border-line px-5">
        <Link href="/dashboard" className="flex items-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-accent text-sm font-bold text-white shadow-sm shadow-blue-200">sb</span>
          <span>
            <span className="block text-base font-semibold tracking-normal">smsbridge</span>
            <span className="block text-xs text-neutral-500">{t("landing.compliance")}</span>
          </span>
        </Link>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4">
        {links.map((link) => <SidebarLink key={link.href} link={link} pathname={pathname} />)}
        <SidebarLink link={{href: "/supplier", label: t("nav.supplier"), icon: Truck}} pathname={pathname} />
      </nav>
      <div className="border-t border-line p-4">
        <div className="rounded-lg border border-line bg-slate-50 p-3">
          <div className="flex items-center gap-2 text-xs text-neutral-500">
            <Wallet size={14} className="text-accent" />
            {t("common.availableBalance")}
          </div>
          <p className="mt-1 text-lg font-semibold">{money(balance?.balance, balance?.currency)}</p>
          <p className="mt-2 truncate text-xs text-neutral-500">{user?.email}</p>
        </div>
      </div>
    </aside>
  );
}

function SidebarLink({
  link,
  pathname
}: {
  link: NavLink;
  pathname: string;
}) {
  const Icon = link.icon;
  const active = pathname === link.href || (link.href !== "/dashboard" && pathname.startsWith(link.href));
  return (
    <Link
      href={link.href}
      className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
        active ? "bg-blue-50 text-accent ring-1 ring-blue-100" : "text-neutral-600 hover:bg-slate-50 hover:text-ink"
      }`}
    >
      <Icon size={18} />
      {link.label}
    </Link>
  );
}

export function TopBar({
  user,
  balance,
  loadingUser,
  links,
  pathname
}: {
  user: User | null;
  balance: WalletType | null;
  loadingUser: boolean;
  links: NavLink[];
  pathname: string;
}) {
  const {t} = useTranslation();
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-white/90 backdrop-blur">
      <div className="flex min-h-16 flex-col gap-3 px-4 py-3 lg:flex-row lg:items-center lg:justify-between lg:px-6">
        <div className="flex items-center justify-between gap-3 lg:hidden">
          <Link href="/dashboard" className="flex items-center gap-2 text-lg font-semibold">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent text-sm font-bold text-white">sb</span>
            smsbridge
          </Link>
          <LanguageSwitcher compact />
        </div>
        <nav className="flex gap-2 overflow-x-auto pb-1 lg:hidden">
          {links.map((link) => <MobileLink key={link.href} link={link} pathname={pathname} />)}
        </nav>
        <div className="hidden text-sm text-neutral-500 lg:block">
          {loadingUser ? t("common.loading") : `${t("common.signedInAs")} ${user?.email || "-"}`}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2 rounded-lg border border-line bg-slate-50 px-3 py-2 text-sm">
            <Wallet size={16} className="text-accent" />
            <span className="text-neutral-500">{t("common.availableBalance")}</span>
            <strong>{money(balance?.balance, balance?.currency)}</strong>
          </div>
          <span className="rounded-full bg-violet-50 px-3 py-1 text-xs font-medium text-violet-700 ring-1 ring-violet-100">
            {user?.role || "user"} · {user?.tier || "default"}
          </span>
          <div className="hidden lg:block"><LanguageSwitcher compact /></div>
          <button className="btn btn-secondary px-3" onClick={logout}>
            <LogOut size={16} />
            {t("nav.logout")}
          </button>
        </div>
      </div>
    </header>
  );
}

function MobileLink({
  link,
  pathname
}: {
  link: NavLink;
  pathname: string;
}) {
  const Icon = link.icon;
  const active = pathname === link.href || (link.href !== "/dashboard" && pathname.startsWith(link.href));
  return (
    <Link
      href={link.href}
      className={`inline-flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${
        active ? "bg-blue-50 text-accent ring-1 ring-blue-100" : "bg-white text-neutral-600 ring-1 ring-line"
      }`}
    >
      <Icon size={16} />
      {link.label}
    </Link>
  );
}

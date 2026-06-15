"use client";

import Link from "next/link";
import {usePathname, useRouter} from "next/navigation";
import {BookOpen, ChevronDown, ClipboardList, HelpCircle, LogOut, Settings, ShieldCheck, Truck, UserCircle, Wallet} from "lucide-react";
import {useEffect, useState} from "react";
import {AuthModal, type AuthMode} from "@/components/shared/auth-modal";
import {ThemeToggle} from "@/components/shared/theme-toggle";
import {LanguageSwitcher} from "@/components/shared/ui";
import {Button} from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import {getBalance} from "@/lib/client/api";
import {currentUser, getToken, logout} from "@/lib/shared/api";
import {money} from "@/lib/shared/format";
import type {User, Wallet as WalletType} from "@/lib/shared/types";
import {useTranslation} from "@/lib/i18n";

const publicRoutes = new Set([
  "/",
  "/buy",
  "/api-docs",
  "/login",
  "/register",
  "/acceptable-use",
  "/terms",
  "/privacy",
  "/abuse",
  "/developer-commands",
  "/faq",
  "/suppliers",
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
    <div className="min-h-screen bg-background">
      <TopNavigation balance={balance} pathname={pathname} user={user} />
      {children}
    </div>
  );
}

function TopNavigation({balance, pathname, user}: {balance: WalletType | null; pathname: string; user: User | null}) {
  const {t} = useTranslation();
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [navUser, setNavUser] = useState<User | null>(user);
  const [navBalance, setNavBalance] = useState<WalletType | null>(balance);

  useEffect(() => {
    setNavUser(user);
    setNavBalance(balance);
  }, [balance, user]);

  const currentUser = navUser || user;
  const currentBalance = navBalance || balance;
  const isSignedIn = Boolean(currentUser);

  const linkClass = (href: string) => {
    const active = pathname === href || (href !== "/" && pathname.startsWith(href));
    return `inline-flex min-w-[5.75rem] items-center justify-center gap-1.5 whitespace-nowrap rounded-lg px-2.5 py-1.5 text-sm font-medium transition-all duration-200 ${
      active ? "bg-cyan-50 text-accent shadow-sm ring-1 ring-cyan-100" : "text-neutral-600 hover:-translate-y-px hover:bg-slate-50 hover:text-slate-950 hover:shadow-sm"
    }`;
  };
  const openAuth = (mode: AuthMode) => {
    setAuthMode(mode);
    setAuthOpen(true);
  };
  const handleAuthSuccess = async (nextUser: User) => {
    setNavUser(nextUser);
    setAuthOpen(false);
    await getBalance().then(setNavBalance).catch(() => null);
  };

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-white/90 backdrop-blur dark:bg-slate-950/85">
      <div className="mx-auto flex h-16 w-full max-w-7xl items-center gap-3 px-4 lg:gap-4 lg:px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2 text-lg font-semibold tracking-normal">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent text-sm font-bold text-white">sb</span>
            smsbridge
        </Link>

        <nav className="hidden min-w-0 flex-1 items-center justify-center gap-1 md:flex">
          <Link className={linkClass("/")} href="/">{t("common.publicHome")}</Link>
          <Link className={linkClass("/api-docs")} href="/api-docs"><BookOpen size={16} />{t("nav.api")}</Link>
          <Link className={linkClass("/suppliers")} href="/suppliers"><Truck size={16} />{t("nav.suppliers")}</Link>
          <Link className={linkClass("/faq")} href="/faq"><HelpCircle size={16} />{t("nav.faq")}</Link>
        </nav>

        <div className="ml-auto flex min-w-0 shrink-0 items-center justify-end gap-2">
          {isSignedIn ? (
            <>
              <div className="hidden min-w-[8.75rem] shrink-0 items-center justify-center gap-1.5 rounded-lg border border-line bg-slate-50 px-2.5 py-1.5 text-xs shadow-sm transition-all duration-200 hover:-translate-y-px hover:border-cyan-200 hover:bg-white hover:shadow-md sm:flex sm:text-sm">
                <Wallet size={15} className="text-accent" />
                <strong>{money(currentBalance?.balance, currentBalance?.currency)}</strong>
              </div>
              <div className="hidden sm:block"><LanguageSwitcher compact /></div>
              <ThemeToggle />
              <AccountMenu user={currentUser} />
            </>
          ) : (
            <>
              <div className="hidden sm:block"><LanguageSwitcher compact /></div>
              <ThemeToggle />
              <Button className="min-w-[5.75rem]" onClick={() => openAuth("login")} size="sm" type="button" variant="secondary">
                {t("nav.login")}
              </Button>
              <Button className="min-w-[7.5rem]" onClick={() => openAuth("register")} size="sm" type="button">
                {t("nav.register")}
              </Button>
            </>
          )}
        </div>
      </div>
      <AuthModal
        initialMode={authMode}
        onClose={() => setAuthOpen(false)}
        onSuccess={handleAuthSuccess}
        open={authOpen}
      />
    </header>
  );
}

function AccountMenu({user}: {user: User | null}) {
  const {t} = useTranslation();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button className="min-w-[2.5rem] shrink-0 px-2.5 lg:min-w-[11rem]" size="sm" variant="secondary">
          <UserCircle size={16} />
          <span className="hidden max-w-28 truncate lg:inline" title={user?.email || undefined}>{user?.email}</span>
          <ChevronDown size={14} />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <div className="px-2 py-1.5">
          <p className="text-xs text-muted-foreground">{t("settings.account")}</p>
          <p className="truncate text-sm font-medium" title={user?.email || undefined}>{user?.email}</p>
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/orders"><ClipboardList size={15} />{t("nav.orders")}</Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/deposit"><Wallet size={15} />{t("nav.addFunds")}</Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/settings"><Settings size={15} />{t("nav.settings")}</Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/supplier"><Truck size={15} />{t("nav.supplierCabinet")}</Link>
        </DropdownMenuItem>
        {user?.role === "admin" && (
          <DropdownMenuItem asChild>
            <Link href="/admin"><ShieldCheck size={15} />{t("nav.admin")}</Link>
          </DropdownMenuItem>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={logout}>
          <LogOut size={15} />{t("nav.logout")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

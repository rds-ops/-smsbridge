"use client";

import {useEffect, useState} from "react";
import {SmsMarketplace} from "@/components/buyer/SmsMarketplace";
import {Alert, Card, PageHeader, PageShell, StatusBadge} from "@/components/shared/ui";
import {getLimits} from "@/lib/client/api";
import {currentUser, logout, logoutAll} from "@/lib/shared/api";
import type {User, UserLimit} from "@/lib/shared/types";
import {money} from "@/lib/shared/format";
import {useTranslation} from "@/lib/i18n";
import type {Locale} from "@/lib/i18n";

export default function SettingsPage() {
  const {t, locale, setLocale} = useTranslation();
  const [user, setUser] = useState<User | null>(null);
  const [limits, setLimits] = useState<UserLimit | null>(null);
  const [error, setError] = useState("");
  const [logoutAllBusy, setLogoutAllBusy] = useState(false);

  useEffect(() => {
    Promise.all([currentUser(), getLimits()])
      .then(([userData, limitData]) => {
        setUser(userData);
        setLimits(limitData);
      })
      .catch((err) => setError(err instanceof Error ? err.message : t("buy.loadFailed")));
  }, []);

  function updateLocale(value: string) {
    setLocale(value as Locale);
  }

  async function endAllSessions() {
    setLogoutAllBusy(true);
    try {
      await logoutAll();
    } finally {
      setLogoutAllBusy(false);
    }
  }

  return (
    <SmsMarketplace>
    <PageShell>
      <PageHeader title={t("settings.title")} description={t("settings.description")} />
      {error && <div className="mt-4"><Alert type="error">{error}</Alert></div>}
      <section className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card title={t("settings.account")}>
          <div className="grid gap-3 text-sm">
            <p><span className="text-neutral-500">{t("common.email")}:</span> <strong>{user?.email ?? "-"}</strong></p>
            <p><span className="text-neutral-500">{t("common.role")}:</span> <strong>{user?.role ?? "-"}</strong></p>
            <p><span className="text-neutral-500">{t("common.status")}:</span> {user?.status ? <StatusBadge status={user.status} /> : "-"}</p>
            <p><span className="text-neutral-500">{t("common.tier")}:</span> <strong>{user?.tier ?? "-"}</strong></p>
            <label className="grid gap-2 text-sm">
              {t("common.locale")}
              <select className="field" value={locale} onChange={(e) => updateLocale(e.target.value)}>
                <option value="en">{t("common.english")}</option>
                <option value="ru">{t("common.russian")}</option>
              </select>
            </label>
            <div className="flex flex-wrap gap-2">
              <button className="btn btn-secondary w-fit" onClick={logout}>{t("nav.logout")}</button>
              <button className="btn btn-secondary w-fit" disabled={logoutAllBusy} onClick={endAllSessions}>
                {logoutAllBusy ? t("common.saving") : t("settings.logoutAll")}
              </button>
            </div>
          </div>
        </Card>
        <Card title={t("settings.limits")} description={t("settings.limitsDesc")}>
          <div className="grid gap-3 text-sm">
            <p><span className="text-neutral-500">{t("settings.ordersPerMinute")}:</span> <strong>{limits?.max_orders_per_minute ?? "-"}</strong></p>
            <p><span className="text-neutral-500">{t("settings.ordersPerDay")}:</span> <strong>{limits?.max_orders_per_day ?? "-"}</strong></p>
            <p><span className="text-neutral-500">{t("settings.activeOrders")}:</span> <strong>{limits?.max_active_orders ?? "-"}</strong></p>
            <p><span className="text-neutral-500">{t("settings.dailySpend")}:</span> <strong>{money(limits?.max_daily_spend)}</strong></p>
          </div>
        </Card>
        <Card title={t("settings.apiKeyStatus")} description={t("settings.apiKeyDesc")}>
          <p className="text-sm leading-6 text-neutral-700">{t("settings.apiKeyText")}</p>
        </Card>
      </section>
    </PageShell>
    </SmsMarketplace>
  );
}

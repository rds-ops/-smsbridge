"use client";

import Link from "next/link";
import {useEffect, useState} from "react";
import {DataTable} from "@/components/shared/data-table";
import {ActionLink, Alert, Card, MetricCard, PageHeader, PageShell, StatusBadge} from "@/components/shared/ui";
import {OnboardingChecklist} from "@/components/client/onboarding-checklist";
import {getBalance, getLimits, getWalletTransactions, listOrders} from "@/lib/client/api";
import {currentUser} from "@/lib/shared/api";
import {dateTime, money, truncate} from "@/lib/shared/format";
import type {Order, User, UserLimit, Wallet, WalletTransaction} from "@/lib/shared/types";
import {useTranslation} from "@/lib/i18n";

export default function DashboardPage() {
  const {t} = useTranslation();
  const [user, setUser] = useState<User | null>(null);
  const [balance, setBalance] = useState<Wallet | null>(null);
  const [limits, setLimits] = useState<UserLimit | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [transactions, setTransactions] = useState<WalletTransaction[]>([]);
  const [transactionOffset, setTransactionOffset] = useState(0);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    Promise.all([
      currentUser(),
      getBalance(),
      getLimits(),
      listOrders(),
      getWalletTransactions(10, 0)
    ])
      .then(([userData, balanceData, limitsData, orderData, transactionData]) => {
        setUser(userData);
        setBalance(balanceData);
        setLimits(limitsData);
        setOrders(orderData);
        setTransactions(transactionData);
        setTransactionOffset(transactionData.length);
      })
      .catch((err) => setError(err instanceof Error ? err.message : t("buy.loadFailed")));
  }

  async function loadMoreTransactions() {
    try {
      const rows = await getWalletTransactions(10, transactionOffset);
      setTransactions((current) => [...current, ...rows]);
      setTransactionOffset((current) => current + rows.length);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("buy.loadFailed"));
    }
  }

  useEffect(() => {
    load();
    window.addEventListener("smsbridge-data-changed", load);
    return () => window.removeEventListener("smsbridge-data-changed", load);
  }, []);

  const activeOrders = orders.filter((order) => ["created", "reserved", "waiting_sms", "sms_received"].includes(order.status)).length;
  const completedOrders = orders.filter((order) => order.status === "completed").length;

  return (
    <PageShell>
      <PageHeader
        title={t("dashboard.title")}
        description={t("dashboard.description")}
        actions={<><Link className="btn btn-primary" href="/buy">{t("dashboard.buyNumber")}</Link><ActionLink href="/deposit">{t("deposit.title")}</ActionLink><ActionLink href="/orders">{t("dashboard.viewOrders")}</ActionLink></>}
      />
      {error && <div className="mt-4"><Alert type="error">{error}</Alert></div>}
      <section className="mt-6 grid gap-4 md:grid-cols-3 xl:grid-cols-6">
        <MetricCard label={t("common.availableBalance")} value={money(balance?.balance, balance?.currency)} helper={t("dashboard.availableHelper")} />
        <MetricCard label={t("common.heldBalance")} value={money(balance?.held_balance, balance?.currency)} helper={t("dashboard.heldHelper")} />
        <MetricCard label={t("dashboard.accountTier")} value={user?.tier || "-"} helper={t("settings.limitsDesc")} />
        <MetricCard label={t("dashboard.dailyLimit")} value={limits?.max_orders_per_day ?? "-"} helper={t("dashboard.maxOrdersDay")} />
        <MetricCard label={t("dashboard.activeOrders")} value={activeOrders} helper={t("status.waiting_sms")} />
        <MetricCard label={t("dashboard.completed")} value={completedOrders} helper={t("dashboard.recentHistory")} />
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
        <Card title={t("dashboard.checklist")} description={user?.role === "admin" ? t("dashboard.adminChecklistDesc") : t("dashboard.userChecklistDesc")}>
          <OnboardingChecklist role={user?.role} />
        </Card>
        <Card title={t("dashboard.quickActions")} description={t("dashboard.quickActionsDesc")}>
          <div className="flex flex-wrap gap-2">
            <Link className="btn btn-primary" href="/buy">{t("dashboard.buyNumber")}</Link>
            <Link className="btn btn-secondary" href="/deposit">{t("deposit.title")}</Link>
            <Link className="btn btn-secondary" href="/orders">{t("dashboard.viewOrders")}</Link>
            <Link className="btn btn-secondary" href="/api-docs">{t("nav.api")}</Link>
            <Link className="btn btn-secondary" href="/settings">{t("nav.settings")}</Link>
          </div>
        </Card>
      </section>

      <section className="mt-8">
        <Card title={t("dashboard.recentOrders")} description={t("dashboard.recentOrdersDesc")}>
          <DataTable
            rows={orders.slice(0, 5) as unknown as Record<string, unknown>[]}
            emptyTitle={t("dashboard.noOrders")}
            emptyDescription={t("dashboard.noOrdersDesc")}
            columns={[
              {key: "public_id", header: t("common.order"), render: (row) => <Link className="text-accent" href={`/orders/${row.public_id}`}>{String(row.public_id).slice(0, 8)}</Link>},
              {key: "service_code", header: t("common.service")},
              {key: "country_iso2", header: t("common.country")},
              {key: "status", header: t("common.status"), render: (row) => <StatusBadge status={String(row.status)} />},
              {key: "price", header: t("common.price"), render: (row) => money(row.price)},
              {key: "created_at", header: t("common.created"), render: (row) => dateTime(row.created_at)}
            ]}
          />
        </Card>
      </section>

      <section className="mt-8">
        <Card title={t("dashboard.walletTransactions")} description={t("dashboard.walletTransactionsDesc")}>
          <DataTable
            rows={transactions as unknown as Record<string, unknown>[]}
            emptyTitle={t("dashboard.noTransactions")}
            columns={[
              {key: "type", header: t("common.type"), render: (row) => <StatusBadge status={String(row.type)} />},
              {key: "amount", header: t("common.amount"), render: (row) => money(row.amount, balance?.currency)},
              {key: "status", header: t("common.status"), render: (row) => <StatusBadge status={String(row.status)} />},
              {key: "order_public_id", header: t("common.order"), render: (row) => row.order_public_id ? <Link className="text-accent" href={`/orders/${row.order_public_id}`}>{truncate(row.order_public_id, 12)}</Link> : "-"},
              {key: "reference", header: t("common.reference"), render: (row) => row.reference ? truncate(row.reference, 32) : "-"},
              {key: "created_at", header: t("common.created"), render: (row) => dateTime(row.created_at)}
            ]}
          />
          {transactions.length >= 10 && (
            <button className="btn btn-secondary mt-4" onClick={loadMoreTransactions}>{t("dashboard.loadMoreTransactions")}</button>
          )}
        </Card>
      </section>
    </PageShell>
  );
}

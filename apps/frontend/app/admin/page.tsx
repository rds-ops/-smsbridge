"use client";

import {useEffect, useMemo, useState} from "react";
import {AdminGuard} from "@/components/admin/admin-guard";
import {DataTable, type Column} from "@/components/shared/data-table";
import {Alert, Card, CopyButton, MetricCard, PageHeader, PageShell, StatusBadge, Toast} from "@/components/shared/ui";
import {
  createSupplier,
  getAdminMetrics,
  getAdminOrders,
  getAdminOpsSummary,
  getAdminUsers,
  getApiRequestLogs,
  getAuditLogs,
  getProviders,
  getSupplierActivations,
  getSupplierInventory,
  getSupplierSms,
  getSupplierTransactions,
  getSuppliers,
  manualDeposit,
  regenerateSupplierApiKey,
  updateSupplier
} from "@/lib/admin/api";
import {orderProfit, userRow} from "@/lib/admin/format";
import {dateTime, money, percent, truncate} from "@/lib/shared/format";
import type {
  AdminOpsSummary,
  Metrics,
  Order,
  Provider,
  Supplier,
  SupplierActivation,
  SupplierInventory,
  SupplierSms,
  SupplierTransaction,
  User,
  Wallet
} from "@/lib/shared/types";
import {useTranslation} from "@/lib/i18n";

type AdminTab = "ops" | "metrics" | "users" | "orders" | "providers" | "suppliers" | "supplier inventory" | "supplier activations" | "supplier sms" | "supplier transactions" | "audit" | "api logs";

const tabs: AdminTab[] = ["ops", "metrics", "users", "orders", "providers", "suppliers", "supplier inventory", "supplier activations", "supplier sms", "supplier transactions", "audit", "api logs"];
const supplierDetailTabs: AdminTab[] = ["supplier inventory", "supplier activations", "supplier sms", "supplier transactions"];

export default function AdminPage() {
  return <AdminGuard>{() => <AdminPanel />}</AdminGuard>;
}

function AdminPanel() {
  const {t} = useTranslation();
  const [tab, setTab] = useState<AdminTab>("ops");
  const [opsSummary, setOpsSummary] = useState<AdminOpsSummary | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [supplierInventory, setSupplierInventory] = useState<SupplierInventory[]>([]);
  const [supplierActivations, setSupplierActivations] = useState<SupplierActivation[]>([]);
  const [supplierSms, setSupplierSms] = useState<SupplierSms[]>([]);
  const [supplierTransactions, setSupplierTransactions] = useState<SupplierTransaction[]>([]);
  const [auditLogs, setAuditLogs] = useState<Array<Record<string, unknown>>>([]);
  const [apiLogs, setApiLogs] = useState<Array<Record<string, unknown>>>([]);
  const [query, setQuery] = useState("");
  const [depositUserId, setDepositUserId] = useState("2");
  const [depositAmount, setDepositAmount] = useState("10.00");
  const [depositReference, setDepositReference] = useState("manual-frontend");
  const [selectedSupplierId, setSelectedSupplierId] = useState("");
  const [supplierName, setSupplierName] = useState("Example Supplier");
  const [supplierEmail, setSupplierEmail] = useState("");
  const [supplierStatus, setSupplierStatus] = useState("pending");
  const [supplierReward, setSupplierReward] = useState("70.00");
  const [supplierNotes, setSupplierNotes] = useState("");
  const [supplierApiKey, setSupplierApiKey] = useState("");
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [toast, setToast] = useState<{type: "success" | "error"; message: string}>({type: "success", message: ""});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load(selectedTab = tab) {
    setLoading(true);
    setError("");
    try {
      if (selectedTab === "ops") setOpsSummary(await getAdminOpsSummary());
      if (selectedTab === "metrics") setMetrics(await getAdminMetrics());
      if (selectedTab === "users") setUsers(await getAdminUsers());
      if (selectedTab === "orders") setOrders(await getAdminOrders());
      if (selectedTab === "providers") setProviders(await getProviders());
      if (selectedTab === "suppliers") {
        const rows = await getSuppliers();
        setSuppliers(rows);
        if (!selectedSupplierId && rows[0]) setSelectedSupplierId(String(rows[0].id));
      }
      if (supplierDetailTabs.includes(selectedTab)) {
        const supplierId = Number(selectedSupplierId);
        if (!Number.isInteger(supplierId) || supplierId <= 0) {
          setSupplierInventory([]);
          setSupplierActivations([]);
          setSupplierSms([]);
          setSupplierTransactions([]);
          return;
        }
        if (selectedTab === "supplier inventory") setSupplierInventory(await getSupplierInventory(supplierId));
        if (selectedTab === "supplier activations") setSupplierActivations(await getSupplierActivations(supplierId));
        if (selectedTab === "supplier sms") setSupplierSms(await getSupplierSms(supplierId));
        if (selectedTab === "supplier transactions") setSupplierTransactions(await getSupplierTransactions(supplierId));
      }
      if (selectedTab === "audit") setAuditLogs(await getAuditLogs());
      if (selectedTab === "api logs") setApiLogs(await getApiRequestLogs());
    } catch (err) {
      setError(err instanceof Error ? err.message : t(supplierDetailTabs.includes(selectedTab) ? "admin.supplierLoadFailed" : "buy.loadFailed"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(tab);
  }, [tab]);

  useEffect(() => {
    if (supplierDetailTabs.includes(tab) && selectedSupplierId) load(tab);
  }, [selectedSupplierId]);

  async function deposit() {
    setError("");
    setToast({type: "success", message: ""});
    const userId = Number(depositUserId);
    const amount = Number(depositAmount);
    if (!Number.isInteger(userId) || userId <= 0) {
      setToast({type: "error", message: t("admin.positiveUser")});
      return;
    }
    if (!Number.isFinite(amount) || amount <= 0) {
      setToast({type: "error", message: t("admin.positiveAmount")});
      return;
    }
    try {
      const updatedWallet = await manualDeposit({
        user_id: userId,
        amount: amount.toFixed(2),
        reference: depositReference || null
      });
      setWallet(updatedWallet);
      setToast({type: "success", message: t("admin.depositSuccess", {userId, balance: money(updatedWallet.balance, updatedWallet.currency)})});
      await Promise.all([getAdminMetrics().then(setMetrics), getAdminUsers().then(setUsers)]);
      if (tab !== "metrics" && tab !== "users") await load(tab);
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("admin.depositFailed")});
    }
  }

  async function addSupplier() {
    setToast({type: "success", message: ""});
    const reward = Number(supplierReward);
    if (!supplierName.trim()) {
      setToast({type: "error", message: t("common.name")});
      return;
    }
    if (!Number.isFinite(reward) || reward < 0 || reward > 100) {
      setToast({type: "error", message: t("admin.rewardInvalid")});
      return;
    }
    try {
      const supplier = await createSupplier({
        name: supplierName.trim(),
        email: supplierEmail.trim() || null,
        status: supplierStatus,
        reward_percent: reward.toFixed(2),
        notes: supplierNotes.trim() || null
      });
      setSelectedSupplierId(String(supplier.id));
      setToast({type: "success", message: t("admin.supplierCreated")});
      await load("suppliers");
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("admin.supplierCreateFailed")});
    }
  }

  async function regenerateKey(supplierId: number) {
    try {
      const result = await regenerateSupplierApiKey(supplierId);
      setSupplierApiKey(result.api_key);
      setToast({type: "success", message: t("admin.supplierKeyGenerated")});
      await load("suppliers");
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("api.generateFailed")});
    }
  }

  async function changeSupplierStatus(supplierId: number, status: string) {
    try {
      await updateSupplier(supplierId, {status});
      setToast({type: "success", message: t("admin.supplierUpdated")});
      await load("suppliers");
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("admin.supplierUpdateFailed")});
    }
  }

  async function changeSupplierReward(supplierId: number, current: unknown) {
    const next = window.prompt(t("admin.rewardPrompt"), String(current ?? "70.00"));
    if (next === null) return;
    const reward = Number(next);
    if (!Number.isFinite(reward) || reward < 0 || reward > 100) {
      setToast({type: "error", message: t("admin.rewardInvalid")});
      return;
    }
    try {
      await updateSupplier(supplierId, {reward_percent: reward.toFixed(2)});
      setToast({type: "success", message: t("admin.supplierUpdated")});
      await load("suppliers");
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("admin.supplierUpdateFailed")});
    }
  }

  const filteredRows = useMemo(() => {
    const lower = query.trim().toLowerCase();
    const filter = (rows: Record<string, unknown>[]) => !lower ? rows : rows.filter((row) => JSON.stringify(row).toLowerCase().includes(lower));
    if (tab === "users") return filter(users.map(userRow));
    if (tab === "orders") return filter(orders.map((order) => ({...order, profit: orderProfit(order)} as Record<string, unknown>)));
    if (tab === "providers") return filter(providers as unknown as Record<string, unknown>[]);
    if (tab === "suppliers") return filter(suppliers as unknown as Record<string, unknown>[]);
    if (tab === "supplier inventory") return filter(supplierInventory as unknown as Record<string, unknown>[]);
    if (tab === "supplier activations") return filter(supplierActivations as unknown as Record<string, unknown>[]);
    if (tab === "supplier sms") return filter(supplierSms as unknown as Record<string, unknown>[]);
    if (tab === "supplier transactions") return filter(supplierTransactions as unknown as Record<string, unknown>[]);
    if (tab === "audit") return filter(auditLogs);
    if (tab === "api logs") return filter(apiLogs);
    return [];
  }, [tab, users, orders, providers, suppliers, supplierInventory, supplierActivations, supplierSms, supplierTransactions, auditLogs, apiLogs, query]);

  const columns = useMemo<Column<Record<string, unknown>>[]>(() => {
    if (tab === "users") return [
      {key: "id", header: t("common.id")},
      {key: "email", header: t("common.email")},
      {key: "role", header: t("common.role")},
      {key: "status", header: t("common.status"), render: (row) => <StatusBadge status={String(row.status)} />},
      {key: "tier", header: t("common.tier")},
      {key: "locale", header: t("common.locale")},
      {key: "max_orders_per_minute", header: t("common.ordersPerMinute")},
      {key: "max_orders_per_day", header: t("common.ordersPerDay")},
      {key: "max_active_orders", header: t("common.activeOrders")},
      {key: "max_daily_spend", header: t("common.dailySpend"), render: (row) => money(row.max_daily_spend)},
      {key: "balance", header: t("common.balance"), render: (row) => money(row.balance, String(row.currency || "USD"))},
      {key: "held_balance", header: t("common.heldBalance"), render: (row) => money(row.held_balance, String(row.currency || "USD"))},
      {key: "currency", header: t("common.currency")},
      {key: "api_key_status", header: t("common.apiKeyStatus")},
      {key: "created_at", header: t("common.created"), render: (row) => dateTime(row.created_at)}
    ];
    if (tab === "orders") return [
      {key: "public_id", header: "public_id", render: (row) => truncate(row.public_id, 12)},
      {key: "user_id", header: t("common.user")},
      {key: "service_code", header: t("common.service")},
      {key: "country_iso2", header: t("common.country")},
      {key: "phone_number", header: t("common.phone")},
      {key: "status", header: t("common.status"), render: (row) => <StatusBadge status={String(row.status)} />},
      {key: "price", header: t("common.price"), render: (row) => money(row.price)},
      {key: "provider_cost", header: t("common.providerCost"), render: (row) => money(row.provider_cost)},
      {key: "profit", header: t("common.profit"), render: (row) => money(row.profit)},
      {key: "sms_code", header: t("common.sms")},
      {key: "created_at", header: t("common.created"), render: (row) => dateTime(row.created_at)}
    ];
    if (tab === "providers") return [
      {key: "name", header: t("common.name")},
      {key: "code", header: t("common.code")},
      {key: "type", header: t("common.type")},
      {key: "status", header: t("common.status"), render: (row) => <StatusBadge status={String(row.status)} />},
      {key: "priority", header: t("common.priority")},
      {key: "default_markup_percent", header: t("common.markup"), render: (row) => `${Number(row.default_markup_percent || 0).toFixed(1)}%`}
    ];
    if (tab === "suppliers") return [
      {key: "id", header: t("common.id")},
      {key: "name", header: t("common.name")},
      {key: "status", header: t("common.status"), render: (row) => <StatusBadge status={String(row.status)} />},
      {key: "reward_percent", header: t("common.rewardPercent"), render: (row) => percent(row.reward_percent)},
      {key: "balance", header: t("common.balance"), render: (row) => money(row.balance, String(row.currency || "USD"))},
      {key: "held_balance", header: t("common.heldBalance"), render: (row) => money(row.held_balance, String(row.currency || "USD"))},
      {key: "inventory_count", header: t("common.inventoryCount")},
      {key: "created_at", header: t("common.created"), render: (row) => dateTime(row.created_at)},
      {key: "actions", header: t("common.actions"), render: (row) => (
        <div className="flex flex-wrap gap-2">
          <button className="btn btn-secondary px-2 py-1 text-xs" onClick={() => changeSupplierStatus(Number(row.id), "active")}>{t("admin.activateSupplier")}</button>
          <button className="btn btn-secondary px-2 py-1 text-xs" onClick={() => changeSupplierStatus(Number(row.id), "blocked")}>{t("admin.blockSupplier")}</button>
          <button className="btn btn-secondary px-2 py-1 text-xs" onClick={() => changeSupplierReward(Number(row.id), row.reward_percent)}>{t("admin.updateReward")}</button>
          <button className="btn btn-secondary px-2 py-1 text-xs" onClick={() => regenerateKey(Number(row.id))}>{t("admin.regenerateSupplierKey")}</button>
        </div>
      )}
    ];
    if (tab === "supplier inventory") return [
      {key: "service_code", header: t("common.service")},
      {key: "country_iso2", header: t("common.country")},
      {key: "operator", header: t("common.operator")},
      {key: "available_count", header: t("common.availableCount")},
      {key: "success_rate", header: t("common.successRate"), render: (row) => row.success_rate ? percent(row.success_rate) : "-"},
      {key: "avg_sms_time_seconds", header: t("common.avgSmsTime")},
      {key: "status", header: t("common.status"), render: (row) => <StatusBadge status={String(row.status)} />},
      {key: "last_sync_at", header: t("common.lastSync"), render: (row) => dateTime(row.last_sync_at)}
    ];
    if (tab === "supplier activations") return [
      {key: "supplier_activation_id", header: t("common.supplierActivationId"), render: (row) => truncate(row.supplier_activation_id, 16)},
      {key: "order_id", header: t("common.order")},
      {key: "phone_number", header: t("common.phone")},
      {key: "service_code", header: t("common.service")},
      {key: "country_iso2", header: t("common.country")},
      {key: "status", header: t("common.status"), render: (row) => <StatusBadge status={String(row.status)} />},
      {key: "client_price", header: t("common.clientPrice"), render: (row) => money(row.client_price)},
      {key: "supplier_reward", header: t("common.supplierReward"), render: (row) => money(row.supplier_reward)},
      {key: "sms_code", header: t("common.smsCode")},
      {key: "created_at", header: t("common.created"), render: (row) => dateTime(row.created_at)}
    ];
    if (tab === "supplier sms") return [
      {key: "supplier_sms_id", header: t("common.supplierSmsId"), render: (row) => truncate(row.supplier_sms_id, 16)},
      {key: "order_id", header: t("common.order")},
      {key: "phone_number", header: t("common.phone")},
      {key: "phone_from", header: t("common.phoneFrom")},
      {key: "text", header: t("common.text"), render: (row) => truncate(row.text, 60)},
      {key: "status", header: t("common.status"), render: (row) => <StatusBadge status={String(row.status)} />},
      {key: "created_at", header: t("common.created"), render: (row) => dateTime(row.created_at)}
    ];
    if (tab === "supplier transactions") return [
      {key: "type", header: t("common.type"), render: (row) => <StatusBadge status={String(row.type)} />},
      {key: "amount", header: t("common.amount"), render: (row) => money(row.amount)},
      {key: "status", header: t("common.status"), render: (row) => <StatusBadge status={String(row.status)} />},
      {key: "order_id", header: t("common.order")},
      {key: "reference", header: t("common.reference")},
      {key: "tx_metadata", header: t("common.metadata"), render: (row) => <pre className="max-w-md whitespace-pre-wrap rounded-md bg-panel p-2 text-xs">{JSON.stringify(row.tx_metadata || {}, null, 2)}</pre>},
      {key: "created_at", header: t("common.created"), render: (row) => dateTime(row.created_at)}
    ];
    if (tab === "audit") return [
      {key: "action", header: t("common.actions")},
      {key: "actor_user_id", header: t("common.actor")},
      {key: "entity_type", header: t("common.entity")},
      {key: "entity_id", header: t("common.entityId")},
      {key: "log_metadata", header: t("common.metadata"), render: (row) => <pre className="max-w-md whitespace-pre-wrap rounded-md bg-panel p-2 text-xs">{JSON.stringify(row.log_metadata || {}, null, 2)}</pre>},
      {key: "created_at", header: t("common.created"), render: (row) => dateTime(row.created_at)}
    ];
    return [
      {key: "user_id", header: t("common.user")},
      {key: "method", header: t("common.method")},
      {key: "endpoint", header: t("common.endpoint")},
      {key: "status_code", header: t("common.status"), render: (row) => <StatusBadge status={String(row.status_code)} />},
      {key: "ip_address", header: t("common.ipAddress")},
      {key: "created_at", header: t("common.created"), render: (row) => dateTime(row.created_at)}
    ];
  }, [tab, t]);

  return (
    <PageShell wide>
      <Toast type={toast.type} message={toast.message} />
      <PageHeader
        title={t("admin.title")}
        description={t("admin.description")}
        actions={<button className="btn btn-secondary" onClick={() => load(tab)} disabled={loading}>{loading ? t("common.refreshing") : t("common.refresh")}</button>}
      />

      <div className="mt-5 flex flex-wrap gap-2 rounded-xl border border-line bg-slate-900 p-2">
        {tabs.map((item) => (
          <button className={`btn ${tab === item ? "bg-white text-slate-950" : "text-white hover:bg-white/10"}`} key={item} onClick={() => setTab(item)}>{tabLabel(item, t)}</button>
        ))}
      </div>

      <Card
        className="mt-6"
        title={t("admin.manualDeposit")}
        description={t("admin.depositDesc")}
      >
        <div className="grid gap-3 md:grid-cols-[0.8fr_0.8fr_1fr_auto]">
          <label className="grid gap-1 text-sm">
            user_id
            <input className="field" value={depositUserId} onChange={(e) => setDepositUserId(e.target.value)} placeholder="2" />
          </label>
          <label className="grid gap-1 text-sm">
            {t("common.amount")}
            <input className="field" value={depositAmount} onChange={(e) => setDepositAmount(e.target.value)} placeholder="10.00" inputMode="decimal" />
          </label>
          <label className="grid gap-1 text-sm">
            {t("common.reference")} {t("common.optional")}
            <input className="field" value={depositReference} onChange={(e) => setDepositReference(e.target.value)} placeholder={t("common.reference")} />
          </label>
          <button className="btn btn-primary self-end" onClick={deposit}>{t("admin.depositButton")}</button>
        </div>
        {wallet && <p className="mt-3 text-sm text-neutral-600">{t("admin.lastWallet", {available: money(wallet.balance, wallet.currency), held: money(wallet.held_balance, wallet.currency)})}</p>}
      </Card>

      {(tab === "suppliers" || supplierDetailTabs.includes(tab)) && (
        <div className="mt-6 grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
          <Card title={t("admin.createSupplier")} description={t("admin.createSupplierDesc")}>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="grid gap-1 text-sm">
                {t("common.name")}
                <input className="field" value={supplierName} onChange={(event) => setSupplierName(event.target.value)} />
              </label>
              <label className="grid gap-1 text-sm">
                {t("common.email")} {t("common.optional")}
                <input className="field" value={supplierEmail} onChange={(event) => setSupplierEmail(event.target.value)} placeholder="supplier@example.com" />
              </label>
              <label className="grid gap-1 text-sm">
                {t("common.status")}
                <select className="field" value={supplierStatus} onChange={(event) => setSupplierStatus(event.target.value)}>
                  <option value="pending">{t("status.pending")}</option>
                  <option value="active">{t("status.active")}</option>
                  <option value="blocked">{t("status.blocked")}</option>
                </select>
              </label>
              <label className="grid gap-1 text-sm">
                {t("common.rewardPercent")}
                <input className="field" value={supplierReward} onChange={(event) => setSupplierReward(event.target.value)} inputMode="decimal" />
              </label>
              <label className="grid gap-1 text-sm md:col-span-2">
                {t("common.notes")} {t("common.optional")}
                <textarea className="field min-h-20" value={supplierNotes} onChange={(event) => setSupplierNotes(event.target.value)} />
              </label>
            </div>
            <button className="btn btn-primary mt-4" onClick={addSupplier}>{t("admin.createSupplierButton")}</button>
          </Card>
          <Card title={t("admin.selectSupplier")} description={t("admin.selectSupplierDesc")}>
            <label className="grid gap-1 text-sm">
              supplier_id
              <input className="field" value={selectedSupplierId} onChange={(event) => setSelectedSupplierId(event.target.value)} placeholder="1" inputMode="numeric" />
            </label>
            <button className="btn btn-secondary mt-4" onClick={() => load(tab)}>{t("common.refresh")}</button>
            {supplierApiKey && (
              <Alert type="success">
                <div className="grid gap-2">
                  <strong>{t("admin.supplierKeyShownOnce")}</strong>
                  <code className="break-all rounded-md bg-white p-2 text-xs">{supplierApiKey}</code>
                  <CopyButton value={supplierApiKey} />
                </div>
              </Alert>
            )}
          </Card>
        </div>
      )}

      {error && <div className="mt-4"><Alert type="error">{error}</Alert></div>}

      {tab === "ops" ? <OpsSummaryView summary={opsSummary} loading={loading} t={t} /> : tab === "metrics" ? <MetricsView metrics={metrics} t={t} /> : (
        <Card className="mt-6" title={tabLabel(tab, t)} description={t("admin.searchDesc")}>
          <input className="field mb-4 max-w-md" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("common.searchTable")} />
          <DataTable rows={filteredRows} columns={columns} emptyTitle={t("admin.noRows")} />
        </Card>
      )}
    </PageShell>
  );
}

function tabLabel(tab: AdminTab, t: (key: string, vars?: Record<string, string | number>) => string) {
  const labels: Record<AdminTab, string> = {
    ops: t("admin.ops"),
    metrics: t("admin.metrics"),
    users: t("admin.users"),
    orders: t("admin.orders"),
    providers: t("admin.providers"),
    suppliers: t("admin.suppliers"),
    "supplier inventory": t("admin.supplierInventory"),
    "supplier activations": t("admin.supplierActivations"),
    "supplier sms": t("admin.supplierSms"),
    "supplier transactions": t("admin.supplierTransactions"),
    audit: t("admin.audit"),
    "api logs": t("admin.apiLogs")
  };
  return labels[tab];
}

function OpsSummaryView({summary, loading, t}: {summary: AdminOpsSummary | null; loading: boolean; t: (key: string, vars?: Record<string, string | number>) => string}) {
  if (!summary) {
    return (
      <Card className="mt-6" title={t("admin.ops")} description={t("admin.opsDesc")}>
        <p className="text-sm text-neutral-600">{loading ? t("common.loading") : t("admin.noRows")}</p>
      </Card>
    );
  }

  const paymentIssues = countTotal(summary.payment_reconciliation_issue_counts);
  const payoutIssues = countTotal(summary.supplier_payout_reconciliation_issue_counts);
  const cards = [
    [t("admin.highRiskUsers"), summary.high_risk_users_count, t("admin.riskWatchlist")],
    [t("admin.watchlistedUsers"), summary.watchlisted_users_count, t("admin.riskWatchlist")],
    [t("admin.pendingRetries"), summary.pending_supplier_release_retries_count, t("admin.releaseRetries")],
    [t("admin.deadRetries"), summary.dead_supplier_release_retries_count, t("admin.releaseRetries")],
    [t("admin.pendingPaymentIntents"), summary.pending_payment_intents_count, t("admin.paymentQueue")],
    [t("admin.pendingSupplierPayouts"), summary.pending_supplier_payout_requests_count, t("admin.payoutQueue")],
    [t("admin.waitingSmsOrders"), summary.active_waiting_sms_orders_count, t("admin.orderQueue")],
    [t("admin.recent5xx"), summary.recent_5xx_request_count, t("admin.recentRequests")],
    [t("admin.recent429"), summary.recent_rate_limit_429_count, t("admin.recentRequests")]
  ];

  return (
    <section className="mt-6 grid gap-4">
      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
        {cards.map(([label, value, helper]) => (
          <MetricCard key={String(label)} label={String(label)} value={String(value ?? 0)} helper={String(helper)} />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title={t("admin.paymentReconciliation")} description={t("admin.issueCount", {count: paymentIssues})}>
          <IssueCounts counts={summary.payment_reconciliation_issue_counts} t={t} />
        </Card>
        <Card title={t("admin.payoutReconciliation")} description={t("admin.issueCount", {count: payoutIssues})}>
          <IssueCounts counts={summary.supplier_payout_reconciliation_issue_counts} t={t} />
        </Card>
      </div>
    </section>
  );
}

function IssueCounts({counts, t}: {counts: Record<string, number>; t: (key: string, vars?: Record<string, string | number>) => string}) {
  const entries = Object.entries(counts || {}).filter(([, value]) => Number(value) > 0);
  if (!entries.length) return <p className="text-sm text-neutral-600">{t("admin.noIssues")}</p>;
  return (
    <div className="grid gap-2">
      {entries.map(([key, value]) => (
        <p className="flex justify-between border-b border-line py-2 text-sm last:border-0" key={key}>
          <span>{key.replaceAll("_", " ")}</span>
          <strong>{value}</strong>
        </p>
      ))}
    </div>
  );
}

function countTotal(counts: Record<string, number> = {}) {
  return Object.values(counts).reduce((total, value) => total + Number(value || 0), 0);
}

function MetricsView({metrics, t}: {metrics: Metrics | null; t: (key: string, vars?: Record<string, string | number>) => string}) {
  const topServices = Array.isArray(metrics?.top_services) ? metrics?.top_services as Array<Record<string, unknown>> : [];
  const topCountries = Array.isArray(metrics?.top_countries) ? metrics?.top_countries as Array<Record<string, unknown>> : [];
  const cards = [
    [t("admin.totalUsers"), metrics?.total_users],
    [t("admin.ordersToday"), metrics?.orders_today],
    [t("admin.successfulToday"), metrics?.successful_orders_today],
    [t("admin.failedExpired"), metrics?.failed_expired_orders_today],
    [t("admin.grossRevenue"), money(metrics?.gross_revenue_today)],
    [t("admin.providerCost"), money(metrics?.provider_cost_today)],
    [t("admin.supplierReward"), money(metrics?.supplier_reward_today)],
    [t("admin.grossProfit"), money(metrics?.gross_profit_today)],
    [t("admin.refundAmount"), money(metrics?.refund_amount_today)]
  ];
  return (
    <section className="mt-6 grid gap-4">
      <div className="grid gap-3 md:grid-cols-4">
        {cards.map(([label, value]) => <MetricCard key={String(label)} label={String(label)} value={String(value ?? "-")} />)}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Card title={t("admin.topServices")}>{topServices.length ? topServices.map((row) => <p className="flex justify-between border-b border-line py-2 text-sm last:border-0" key={String(row.service_code)}><span>{String(row.service_code)}</span><strong>{String(row.orders)}</strong></p>) : <p className="text-sm text-neutral-600">{t("admin.noServiceData")}</p>}</Card>
        <Card title={t("admin.topCountries")}>{topCountries.length ? topCountries.map((row) => <p className="flex justify-between border-b border-line py-2 text-sm last:border-0" key={String(row.country_iso2)}><span>{String(row.country_iso2)}</span><strong>{String(row.orders)}</strong></p>) : <p className="text-sm text-neutral-600">{t("admin.noCountryData")}</p>}</Card>
      </div>
    </section>
  );
}

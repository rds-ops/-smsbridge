"use client";

import {useEffect, useMemo, useState} from "react";
import type {ReactNode} from "react";
import {AdminGuard} from "@/components/admin/admin-guard";
import {DataTable, type Column} from "@/components/shared/data-table";
import {Alert, Card, CopyButton, MetricCard, PageHeader, PageShell, StatusBadge, Toast} from "@/components/shared/ui";
import {
  approveSupplierPayoutRequest,
  createAdminRiskAction,
  createSupplier,
  getAdminMetrics,
  getAdminOrders,
  getAdminOpsSummary,
  getAdminPaymentIntent,
  getAdminPaymentIntents,
  getAdminRiskActions,
  getAdminRiskUser,
  getAdminRiskUsers,
  getAdminSupplierPayoutRequest,
  getAdminSupplierPayoutRequests,
  getAdminUsers,
  getApiRequestLogs,
  getAuditLogs,
  getProviders,
  getSupplierActivations,
  getSupplierInventory,
  getOperationalCleanupDryRun,
  getPaymentReconciliation,
  getSupplierPayoutReconciliation,
  getSupplierReleaseRetries,
  getSupplierSms,
  getSupplierTransactions,
  getSuppliers,
  manualCompletePaymentIntent,
  manualDeposit,
  markSupplierPayoutPaid,
  regenerateSupplierApiKey,
  rejectSupplierPayoutRequest,
  updateSupplier
} from "@/lib/admin/api";
import type {SupplierReservationPayload} from "@/lib/admin/api";
import {orderProfit, userRow} from "@/lib/admin/format";
import {dateTime, money, percent, truncate} from "@/lib/shared/format";
import type {
  AdminOpsSummary,
  AdminApiRequestLog,
  AdminPaymentIntent,
  AdminRiskAction,
  AdminRiskActionType,
  AdminRiskUserSummary,
  AdminSupplierPayoutRequest,
  Metrics,
  OperationalCleanupDryRun,
  Order,
  PaymentCreditReconciliation,
  Provider,
  Supplier,
  SupplierActivation,
  SupplierInventory,
  SupplierPayoutReconciliation,
  SupplierReleaseRetry,
  SupplierSms,
  SupplierTransaction,
  User,
  Wallet
} from "@/lib/shared/types";
import {useTranslation} from "@/lib/i18n";

type AdminTab = "ops" | "reliability" | "risk users" | "payment intents" | "supplier payouts" | "metrics" | "users" | "orders" | "providers" | "suppliers" | "supplier inventory" | "supplier activations" | "supplier sms" | "supplier transactions" | "audit" | "api logs";

const tabs: AdminTab[] = ["ops", "reliability", "risk users", "payment intents", "supplier payouts", "metrics", "users", "orders", "providers", "suppliers", "supplier inventory", "supplier activations", "supplier sms", "supplier transactions", "audit", "api logs"];
const supplierDetailTabs: AdminTab[] = ["supplier inventory", "supplier activations", "supplier sms", "supplier transactions"];

export default function AdminPage() {
  return <AdminGuard>{() => <AdminPanel />}</AdminGuard>;
}

function AdminPanel() {
  const {t} = useTranslation();
  const [tab, setTab] = useState<AdminTab>("ops");
  const [opsSummary, setOpsSummary] = useState<AdminOpsSummary | null>(null);
  const [riskUsers, setRiskUsers] = useState<AdminRiskUserSummary[]>([]);
  const [riskDetail, setRiskDetail] = useState<AdminRiskUserSummary | null>(null);
  const [riskActions, setRiskActions] = useState<AdminRiskAction[]>([]);
  const [riskFilter, setRiskFilter] = useState("");
  const [riskActionType, setRiskActionType] = useState<AdminRiskActionType>("note");
  const [riskNote, setRiskNote] = useState("");
  const [riskActionLoading, setRiskActionLoading] = useState(false);
  const [paymentIntents, setPaymentIntents] = useState<AdminPaymentIntent[]>([]);
  const [paymentIntentDetail, setPaymentIntentDetail] = useState<AdminPaymentIntent | null>(null);
  const [paymentIntentStatusFilter, setPaymentIntentStatusFilter] = useState("");
  const [paymentIntentProviderFilter, setPaymentIntentProviderFilter] = useState("");
  const [paymentIntentUserFilter, setPaymentIntentUserFilter] = useState("");
  const [manualCompleteLoading, setManualCompleteLoading] = useState(false);
  const [supplierPayouts, setSupplierPayouts] = useState<AdminSupplierPayoutRequest[]>([]);
  const [supplierPayoutDetail, setSupplierPayoutDetail] = useState<AdminSupplierPayoutRequest | null>(null);
  const [supplierPayoutStatusFilter, setSupplierPayoutStatusFilter] = useState("");
  const [supplierPayoutSupplierFilter, setSupplierPayoutSupplierFilter] = useState("");
  const [supplierPayoutActionLoading, setSupplierPayoutActionLoading] = useState(false);
  const [supplierReleaseRetries, setSupplierReleaseRetries] = useState<SupplierReleaseRetry[]>([]);
  const [paymentReconciliation, setPaymentReconciliation] = useState<PaymentCreditReconciliation | null>(null);
  const [supplierPayoutReconciliation, setSupplierPayoutReconciliation] = useState<SupplierPayoutReconciliation | null>(null);
  const [cleanupDryRun, setCleanupDryRun] = useState<OperationalCleanupDryRun | null>(null);
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
  const [apiLogs, setApiLogs] = useState<AdminApiRequestLog[]>([]);
  const [query, setQuery] = useState("");
  const [requestIdFilter, setRequestIdFilter] = useState("");
  const [depositUserId, setDepositUserId] = useState("2");
  const [depositAmount, setDepositAmount] = useState("10.00");
  const [depositReference, setDepositReference] = useState("manual-frontend");
  const [selectedSupplierId, setSelectedSupplierId] = useState("");
  const [supplierName, setSupplierName] = useState("Example Supplier");
  const [supplierEmail, setSupplierEmail] = useState("");
  const [supplierStatus, setSupplierStatus] = useState("pending");
  const [supplierReward, setSupplierReward] = useState("70.00");
  const [supplierNotes, setSupplierNotes] = useState("");
  const [supplierReservationEnabled, setSupplierReservationEnabled] = useState(false);
  const [supplierReservationUrl, setSupplierReservationUrl] = useState("");
  const [supplierReservationAuthType, setSupplierReservationAuthType] = useState("none");
  const [supplierReservationAuthSecret, setSupplierReservationAuthSecret] = useState("");
  const [supplierReservationTimeout, setSupplierReservationTimeout] = useState("5");
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
      if (selectedTab === "reliability") {
        const [retries, payment, payout, cleanup] = await Promise.all([
          getSupplierReleaseRetries(),
          getPaymentReconciliation(),
          getSupplierPayoutReconciliation(),
          getOperationalCleanupDryRun()
        ]);
        setSupplierReleaseRetries(retries);
        setPaymentReconciliation(payment);
        setSupplierPayoutReconciliation(payout);
        setCleanupDryRun(cleanup);
      }
      if (selectedTab === "risk users") {
        const rows = await getAdminRiskUsers(riskFilter ? {risk_level: riskFilter} : {});
        setRiskUsers(rows);
        if (rows[0]) await selectRiskUser(rows[0].user_id);
        else {
          setRiskDetail(null);
          setRiskActions([]);
        }
      }
      if (selectedTab === "payment intents") {
        const rows = await getAdminPaymentIntents(paymentIntentFilters(paymentIntentStatusFilter, paymentIntentProviderFilter, paymentIntentUserFilter));
        setPaymentIntents(rows);
        if (rows[0]) await selectPaymentIntent(rows[0].id);
        else setPaymentIntentDetail(null);
      }
      if (selectedTab === "supplier payouts") {
        if (!suppliers.length) setSuppliers(await getSuppliers());
        const rows = await getAdminSupplierPayoutRequests(supplierPayoutFilters(supplierPayoutStatusFilter, supplierPayoutSupplierFilter));
        setSupplierPayouts(rows);
        if (rows[0]) await selectSupplierPayout(rows[0].id);
        else setSupplierPayoutDetail(null);
      }
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

  useEffect(() => {
    const selected = suppliers.find((supplier) => String(supplier.id) === selectedSupplierId);
    if (!selected) return;
    setSupplierReservationEnabled(Boolean(selected.reservation_enabled));
    setSupplierReservationUrl(selected.reservation_url || "");
    setSupplierReservationAuthType(selected.reservation_auth_type || "none");
    setSupplierReservationAuthSecret("");
    setSupplierReservationTimeout(String(selected.reservation_timeout_seconds || 5));
  }, [selectedSupplierId, suppliers]);

  useEffect(() => {
    if (tab === "risk users") load(tab);
  }, [riskFilter]);

  useEffect(() => {
    if (tab === "payment intents") load(tab);
  }, [paymentIntentStatusFilter, paymentIntentProviderFilter]);

  useEffect(() => {
    if (tab === "supplier payouts") load(tab);
  }, [supplierPayoutStatusFilter]);

  async function selectRiskUser(userId: number) {
    const [detail, actions] = await Promise.all([getAdminRiskUser(userId), getAdminRiskActions(userId)]);
    setRiskDetail(detail);
    setRiskActions(actions);
  }

  async function submitRiskAction() {
    if (!riskDetail) return;
    const note = riskNote.trim();
    if (note.length > 1000) {
      setToast({type: "error", message: t("admin.riskNoteTooLong")});
      return;
    }
    if (riskActionType === "note" && !note) {
      setToast({type: "error", message: t("admin.riskNoteRequired")});
      return;
    }
    setRiskActionLoading(true);
    setToast({type: "success", message: ""});
    try {
      await createAdminRiskAction(riskDetail.user_id, {action: riskActionType, note: note || null});
      setRiskNote("");
      setToast({type: "success", message: t("admin.riskActionCreated")});
      const [rows] = await Promise.all([
        getAdminRiskUsers(riskFilter ? {risk_level: riskFilter} : {}).then(setRiskUsers),
        selectRiskUser(riskDetail.user_id)
      ]);
      void rows;
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("admin.riskActionFailed")});
    } finally {
      setRiskActionLoading(false);
    }
  }

  async function selectPaymentIntent(id: number) {
    setPaymentIntentDetail(await getAdminPaymentIntent(id));
  }

  async function applyPaymentIntentFilters() {
    if (tab === "payment intents") await load("payment intents");
  }

  async function completePaymentIntent(id: number) {
    setManualCompleteLoading(true);
    setToast({type: "success", message: ""});
    try {
      const updated = await manualCompletePaymentIntent(id);
      setPaymentIntentDetail(updated);
      setToast({type: "success", message: t("admin.paymentIntentCompleted")});
      setPaymentIntents(await getAdminPaymentIntents(paymentIntentFilters(paymentIntentStatusFilter, paymentIntentProviderFilter, paymentIntentUserFilter)));
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("admin.paymentIntentCompleteFailed")});
    } finally {
      setManualCompleteLoading(false);
    }
  }

  async function selectSupplierPayout(id: number) {
    setSupplierPayoutDetail(await getAdminSupplierPayoutRequest(id));
  }

  async function applySupplierPayoutFilters() {
    if (tab === "supplier payouts") await load("supplier payouts");
  }

  async function runSupplierPayoutAction(action: "approve" | "reject" | "paid", payout: AdminSupplierPayoutRequest) {
    const labels = {
      approve: t("admin.approvePayout"),
      reject: t("admin.rejectPayout"),
      paid: t("admin.markPayoutPaid")
    };
    if (!window.confirm(t("admin.confirmPayoutAction", {action: labels[action], id: payout.public_id}))) return;
    const note = window.prompt(t(action === "reject" ? "admin.payoutRejectReasonPrompt" : "admin.payoutAdminNotePrompt"), "") || "";
    setSupplierPayoutActionLoading(true);
    setToast({type: "success", message: ""});
    try {
      const body = action === "reject" ? {reason: note || null, admin_note: note || null} : {admin_note: note || null};
      const updated = action === "approve"
        ? await approveSupplierPayoutRequest(payout.id, body)
        : action === "reject"
          ? await rejectSupplierPayoutRequest(payout.id, body)
          : await markSupplierPayoutPaid(payout.id, body);
      setSupplierPayoutDetail(updated);
      setSupplierPayouts(await getAdminSupplierPayoutRequests(supplierPayoutFilters(supplierPayoutStatusFilter, supplierPayoutSupplierFilter)));
      setToast({type: "success", message: t("admin.supplierPayoutUpdated")});
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("admin.supplierPayoutUpdateFailed")});
    } finally {
      setSupplierPayoutActionLoading(false);
    }
  }

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
    const reservationPayload = buildReservationPayload();
    if (!reservationPayload) return;
    try {
      const supplier = await createSupplier({
        name: supplierName.trim(),
        email: supplierEmail.trim() || null,
        status: supplierStatus,
        reward_percent: reward.toFixed(2),
        notes: supplierNotes.trim() || null,
        ...reservationPayload
      });
      setSelectedSupplierId(String(supplier.id));
      setSupplierReservationAuthSecret("");
      setToast({type: "success", message: t("admin.supplierCreated")});
      await load("suppliers");
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("admin.supplierCreateFailed")});
    }
  }

  function buildReservationPayload(): SupplierReservationPayload | null {
    const url = supplierReservationUrl.trim();
    const authSecret = supplierReservationAuthSecret.trim();
    const timeout = Number(supplierReservationTimeout);
    if (supplierReservationEnabled && !url) {
      setToast({type: "error", message: t("admin.reservationUrlRequired")});
      return null;
    }
    if (!Number.isInteger(timeout) || timeout < 1 || timeout > 120) {
      setToast({type: "error", message: t("admin.reservationTimeoutInvalid")});
      return null;
    }
    return {
      reservation_enabled: supplierReservationEnabled,
      reservation_url: url || null,
      reservation_auth_type: supplierReservationAuthType || "none",
      reservation_timeout_seconds: timeout,
      ...(authSecret ? {reservation_auth_secret_encrypted: authSecret} : {})
    };
  }

  async function saveSupplierReservation() {
    const supplierId = Number(selectedSupplierId);
    if (!Number.isInteger(supplierId) || supplierId <= 0) {
      setToast({type: "error", message: t("admin.selectSupplierFirst")});
      return;
    }
    const reservationPayload = buildReservationPayload();
    if (!reservationPayload) return;
    try {
      await updateSupplier(supplierId, reservationPayload);
      setSupplierReservationAuthSecret("");
      setToast({type: "success", message: t("admin.reservationSaved")});
      await load("suppliers");
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("admin.supplierUpdateFailed")});
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
    if (tab === "api logs") {
      const requestLower = requestIdFilter.trim().toLowerCase();
      const rows = requestLower
        ? apiLogs.filter((row) => String(row.request_id || "").toLowerCase().includes(requestLower))
        : apiLogs;
      return filter(rows as unknown as Record<string, unknown>[]);
    }
    return [];
  }, [tab, users, orders, providers, suppliers, supplierInventory, supplierActivations, supplierSms, supplierTransactions, auditLogs, apiLogs, query, requestIdFilter]);

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
      {key: "reservation_enabled", header: t("admin.reservationEnabled"), render: (row) => row.reservation_enabled ? t("common.yes") : t("common.no")},
      {key: "reservation_auth_type", header: t("admin.reservationAuthType"), render: (row) => String(row.reservation_auth_type || "none")},
      {key: "reservation_timeout_seconds", header: t("admin.reservationTimeoutSeconds"), render: (row) => row.reservation_timeout_seconds ? `${row.reservation_timeout_seconds}s` : "-"},
      {key: "reservation_url", header: t("admin.reservationUrl"), render: (row) => truncate(row.reservation_url, 32)},
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
    if (tab === "api logs") return [
      {key: "created_at", header: t("common.created"), render: (row) => dateTime(row.created_at)},
      {key: "request_id", header: "request_id", render: (row) => (
        <span className="flex max-w-[220px] items-center gap-2">
          <code className="truncate rounded bg-panel px-1 py-0.5 text-xs">{row.request_id ? String(row.request_id) : "-"}</code>
          {row.request_id ? <CopyButton value={String(row.request_id)} /> : null}
        </span>
      )},
      {key: "method", header: t("common.method")},
      {key: "endpoint", header: t("common.endpoint"), render: (row) => truncate(row.endpoint || row.path || "-", 48)},
      {key: "status_code", header: t("common.status"), render: (row) => <StatusBadge status={String(row.status_code)} />},
      {key: "user_id", header: t("common.userId"), render: (row) => row.user_id ? String(row.user_id) : "-"},
      {key: "supplier_id", header: "supplier_id", render: (row) => row.supplier_id ? String(row.supplier_id) : "-"},
      {key: "buyer_api_key_id", header: "buyer_api_key_id", render: (row) => row.buyer_api_key_id ? String(row.buyer_api_key_id) : "-"},
      {key: "duration_ms", header: "duration_ms", render: (row) => row.duration_ms ? String(row.duration_ms) : "-"},
      {key: "ip_address", header: t("common.ipAddress"), render: (row) => row.ip_address || row.ip ? String(row.ip_address || row.ip) : "-"}
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
            <div className="mt-5 rounded-xl border border-line bg-panel p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-slate-950">{t("admin.reservationConfig")}</h3>
                  <p className="mt-1 text-sm text-neutral-600">{t("admin.reservationConfigHelp")}</p>
                </div>
                <label className="flex items-center gap-2 text-sm font-medium">
                  <input
                    type="checkbox"
                    checked={supplierReservationEnabled}
                    onChange={(event) => setSupplierReservationEnabled(event.target.checked)}
                  />
                  {t("admin.reservationEnabled")}
                </label>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <label className="grid gap-1 text-sm md:col-span-2">
                  {t("admin.reservationUrl")}
                  <input
                    className="field"
                    value={supplierReservationUrl}
                    onChange={(event) => setSupplierReservationUrl(event.target.value)}
                    placeholder="http://fake-supplier:8010/v1/reservations"
                  />
                </label>
                <label className="grid gap-1 text-sm">
                  {t("admin.reservationAuthType")}
                  <select className="field" value={supplierReservationAuthType} onChange={(event) => setSupplierReservationAuthType(event.target.value)}>
                    <option value="none">none</option>
                    <option value="bearer">bearer</option>
                  </select>
                </label>
                <label className="grid gap-1 text-sm">
                  {t("admin.reservationTimeoutSeconds")}
                  <input className="field" value={supplierReservationTimeout} onChange={(event) => setSupplierReservationTimeout(event.target.value)} inputMode="numeric" />
                </label>
                <label className="grid gap-1 text-sm md:col-span-2">
                  {t("admin.reservationAuthSecret")} {t("common.optional")}
                  <input
                    className="field"
                    type="password"
                    value={supplierReservationAuthSecret}
                    onChange={(event) => setSupplierReservationAuthSecret(event.target.value)}
                    placeholder={t("admin.reservationAuthSecretPlaceholder")}
                  />
                </label>
              </div>
            </div>
            <button className="btn btn-primary mt-4" onClick={addSupplier}>{t("admin.createSupplierButton")}</button>
          </Card>
          <Card title={t("admin.selectSupplier")} description={t("admin.selectSupplierDesc")}>
            <label className="grid gap-1 text-sm">
              supplier_id
              <input className="field" value={selectedSupplierId} onChange={(event) => setSelectedSupplierId(event.target.value)} placeholder="1" inputMode="numeric" />
            </label>
            <div className="mt-4 flex flex-wrap gap-2">
              <button className="btn btn-secondary" onClick={() => load(tab)}>{t("common.refresh")}</button>
              <button className="btn btn-primary" onClick={saveSupplierReservation}>{t("admin.saveReservationConfig")}</button>
            </div>
            <p className="mt-3 text-sm text-neutral-600">{t("admin.reservationSecretHelp")}</p>
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

      {tab === "ops" ? <OpsSummaryView summary={opsSummary} loading={loading} t={t} /> : tab === "reliability" ? (
        <ReliabilityCenterView
          retries={supplierReleaseRetries}
          payment={paymentReconciliation}
          payout={supplierPayoutReconciliation}
          cleanup={cleanupDryRun}
          loading={loading}
          t={t}
        />
      ) : tab === "risk users" ? (
        <RiskUsersView
          users={riskUsers}
          detail={riskDetail}
          actions={riskActions}
          filter={riskFilter}
          setFilter={setRiskFilter}
          actionType={riskActionType}
          setActionType={setRiskActionType}
          note={riskNote}
          setNote={setRiskNote}
          loading={loading}
          actionLoading={riskActionLoading}
          onSelect={(userId) => selectRiskUser(userId).catch((err) => setToast({type: "error", message: err instanceof Error ? err.message : t("buy.loadFailed")}))}
          onSubmit={submitRiskAction}
          t={t}
        />
      ) : tab === "payment intents" ? (
        <PaymentIntentsView
          intents={paymentIntents}
          detail={paymentIntentDetail}
          statusFilter={paymentIntentStatusFilter}
          setStatusFilter={setPaymentIntentStatusFilter}
          providerFilter={paymentIntentProviderFilter}
          setProviderFilter={setPaymentIntentProviderFilter}
          userFilter={paymentIntentUserFilter}
          setUserFilter={setPaymentIntentUserFilter}
          loading={loading}
          manualCompleteLoading={manualCompleteLoading}
          onApplyFilters={applyPaymentIntentFilters}
          onSelect={(id) => selectPaymentIntent(id).catch((err) => setToast({type: "error", message: err instanceof Error ? err.message : t("buy.loadFailed")}))}
          onManualComplete={completePaymentIntent}
          t={t}
        />
      ) : tab === "supplier payouts" ? (
        <SupplierPayoutsView
          payouts={supplierPayouts}
          detail={supplierPayoutDetail}
          suppliers={suppliers}
          statusFilter={supplierPayoutStatusFilter}
          setStatusFilter={setSupplierPayoutStatusFilter}
          supplierFilter={supplierPayoutSupplierFilter}
          setSupplierFilter={setSupplierPayoutSupplierFilter}
          loading={loading}
          actionLoading={supplierPayoutActionLoading}
          onApplyFilters={applySupplierPayoutFilters}
          onSelect={(id) => selectSupplierPayout(id).catch((err) => setToast({type: "error", message: err instanceof Error ? err.message : t("buy.loadFailed")}))}
          onAction={runSupplierPayoutAction}
          t={t}
        />
      ) : tab === "metrics" ? <MetricsView metrics={metrics} t={t} /> : (
        <Card className="mt-6" title={tabLabel(tab, t)} description={t("admin.searchDesc")}>
          {tab === "api logs" ? (
            <div className="mb-4 grid gap-3 md:grid-cols-2">
              <label className="grid gap-1 text-sm">
                request_id
                <input className="field" value={requestIdFilter} onChange={(e) => setRequestIdFilter(e.target.value)} placeholder="request_id" />
              </label>
              <label className="grid gap-1 text-sm">
                {t("common.search")}
                <input className="field" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("common.searchTable")} />
              </label>
            </div>
          ) : (
            <input className="field mb-4 max-w-md" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("common.searchTable")} />
          )}
          <DataTable rows={filteredRows} columns={columns} emptyTitle={t("admin.noRows")} />
        </Card>
      )}
    </PageShell>
  );
}

function tabLabel(tab: AdminTab, t: (key: string, vars?: Record<string, string | number>) => string) {
  const labels: Record<AdminTab, string> = {
    ops: t("admin.ops"),
    reliability: t("admin.reliability"),
    "risk users": t("admin.riskUsers"),
    "payment intents": t("admin.paymentIntents"),
    "supplier payouts": t("admin.supplierPayouts"),
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

function ReliabilityCenterView({
  retries,
  payment,
  payout,
  cleanup,
  loading,
  t
}: {
  retries: SupplierReleaseRetry[];
  payment: PaymentCreditReconciliation | null;
  payout: SupplierPayoutReconciliation | null;
  cleanup: OperationalCleanupDryRun | null;
  loading: boolean;
  t: (key: string, vars?: Record<string, string | number>) => string;
}) {
  if (loading && !payment && !payout && !cleanup && !retries.length) {
    return (
      <Card className="mt-6" title={t("admin.reliability")} description={t("admin.reliabilityDesc")}>
        <p className="text-sm text-neutral-600">{t("common.loading")}</p>
      </Card>
    );
  }
  return (
    <section className="mt-6 grid gap-4">
      <div className="grid gap-3 md:grid-cols-4">
        <MetricCard label={t("admin.deadRetries")} value={retries.filter((retry) => retry.status === "dead").length} helper={t("admin.releaseRetries")} />
        <MetricCard label={t("admin.pendingRetries")} value={retries.filter((retry) => retry.status === "pending").length} helper={t("admin.releaseRetries")} />
        <MetricCard label={t("admin.paymentIssues")} value={countTotal(payment?.counts || {})} helper={t("admin.paymentReconciliation")} />
        <MetricCard label={t("admin.payoutIssues")} value={countTotal(payout?.counts || {})} helper={t("admin.payoutReconciliation")} />
      </div>
      <Card title={t("admin.supplierReleaseRetries")} description={t("admin.supplierReleaseRetriesDesc")}>
        {!retries.length ? <p className="text-sm text-neutral-600">{t("admin.noIssues")}</p> : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-line text-sm">
              <thead className="bg-panel text-left text-xs uppercase tracking-wide text-neutral-500">
                <tr>
                  <th className="px-3 py-2">{t("admin.supplier")}</th>
                  <th className="px-3 py-2">{t("admin.activation")}</th>
                  <th className="px-3 py-2">{t("common.status")}</th>
                  <th className="px-3 py-2">{t("admin.attempts")}</th>
                  <th className="px-3 py-2">{t("admin.nextRetry")}</th>
                  <th className="px-3 py-2">{t("admin.lastError")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {retries.map((retry) => (
                  <tr className={retry.status === "dead" || retry.attempt_count >= 3 ? "bg-red-50" : ""} key={retry.id}>
                    <td className="px-3 py-2">#{retry.supplier_id}</td>
                    <td className="px-3 py-2">#{retry.supplier_activation_id}</td>
                    <td className="px-3 py-2"><StatusBadge status={retry.status} /></td>
                    <td className="px-3 py-2">{retry.attempt_count}</td>
                    <td className="px-3 py-2">{dateTime(retry.next_retry_at)}</td>
                    <td className="max-w-md px-3 py-2 text-xs text-neutral-600">{retry.last_error ? truncate(retry.last_error, 100) : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        <ReconciliationCard
          title={t("admin.paymentReconciliation")}
          counts={payment?.counts || {}}
          issues={payment?.issues || []}
          emptyText={t("admin.noIssues")}
          renderIssue={(issue) => (
            <p className="grid gap-1 border-b border-line py-2 text-sm last:border-0" key={`${issue.issue_type}-${issue.payment_intent_id || issue.payment_intent_public_id || issue.wallet_transaction_id}`}>
              <span className="font-medium">{issue.issue_type}</span>
              <span className="text-xs text-neutral-600">intent: {issue.payment_intent_public_id || issue.payment_intent_id || "-"} · user: {issue.user_id || "-"} · status: {issue.status || "-"}</span>
            </p>
          )}
          t={t}
        />
        <ReconciliationCard
          title={t("admin.payoutReconciliation")}
          counts={payout?.counts || {}}
          issues={payout?.issues || []}
          emptyText={t("admin.noIssues")}
          renderIssue={(issue) => (
            <p className="grid gap-1 border-b border-line py-2 text-sm last:border-0" key={`${issue.issue_type}-${issue.payout_id || issue.payout_public_id}`}>
              <span className="font-medium">{issue.issue_type}</span>
              <span className="text-xs text-neutral-600">payout: {issue.payout_public_id || issue.payout_id || "-"} · supplier: {issue.supplier_id} · status: {issue.status || "-"}</span>
            </p>
          )}
          t={t}
        />
      </div>
      <Card title={t("admin.cleanupDryRun")} description={t("admin.cleanupDryRunDesc")}>
        {cleanup ? (
          <div className="grid gap-3 md:grid-cols-4">
            <MetricCard label="api_request_logs" value={cleanup.api_request_logs} />
            <MetricCard label="payment_webhook_events" value={cleanup.payment_webhook_events} />
            <MetricCard label="supplier_release_retries" value={cleanup.supplier_release_retries} />
            <MetricCard label={t("admin.total")} value={cleanup.total} helper={cleanup.dry_run ? t("admin.dryRunOnly") : ""} />
          </div>
        ) : <p className="text-sm text-neutral-600">{t("admin.noRows")}</p>}
      </Card>
    </section>
  );
}

function ReconciliationCard<T>({
  title,
  counts,
  issues,
  emptyText,
  renderIssue,
  t
}: {
  title: string;
  counts: Record<string, number>;
  issues: T[];
  emptyText: string;
  renderIssue: (issue: T) => ReactNode;
  t: (key: string, vars?: Record<string, string | number>) => string;
}) {
  return (
    <Card title={title} description={t("admin.issueCount", {count: countTotal(counts)})}>
      <IssueCounts counts={counts} t={t} />
      <div className="mt-4">
        <h3 className="text-sm font-semibold">{t("admin.recentIssues")}</h3>
        {!issues.length ? <p className="mt-2 text-sm text-neutral-600">{emptyText}</p> : <div className="mt-2">{issues.slice(0, 8).map(renderIssue)}</div>}
      </div>
    </Card>
  );
}

function RiskUsersView({
  users,
  detail,
  actions,
  filter,
  setFilter,
  actionType,
  setActionType,
  note,
  setNote,
  loading,
  actionLoading,
  onSelect,
  onSubmit,
  t
}: {
  users: AdminRiskUserSummary[];
  detail: AdminRiskUserSummary | null;
  actions: AdminRiskAction[];
  filter: string;
  setFilter: (value: string) => void;
  actionType: AdminRiskActionType;
  setActionType: (value: AdminRiskActionType) => void;
  note: string;
  setNote: (value: string) => void;
  loading: boolean;
  actionLoading: boolean;
  onSelect: (userId: number) => void;
  onSubmit: () => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}) {
  return (
    <section className="mt-6 grid gap-4 xl:grid-cols-[1.35fr_0.85fr]">
      <Card title={t("admin.riskUsers")} description={t("admin.riskUsersDesc")}>
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <label className="grid gap-1 text-sm">
            {t("admin.riskLevel")}
            <select className="field min-w-40" value={filter} onChange={(event) => setFilter(event.target.value)}>
              <option value="">{t("admin.allRiskLevels")}</option>
              <option value="low">{t("admin.riskLow")}</option>
              <option value="medium">{t("admin.riskMedium")}</option>
              <option value="high">{t("admin.riskHigh")}</option>
            </select>
          </label>
        </div>
        {!users.length ? (
          <p className="text-sm text-neutral-600">{loading ? t("common.loading") : t("admin.noRows")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-line text-sm">
              <thead className="bg-panel text-left text-xs uppercase tracking-wide text-neutral-500">
                <tr>
                  <th className="px-3 py-2">{t("common.user")}</th>
                  <th className="px-3 py-2">{t("admin.riskLevel")}</th>
                  <th className="px-3 py-2">{t("admin.orders")}</th>
                  <th className="px-3 py-2">{t("admin.rates")}</th>
                  <th className="px-3 py-2">{t("admin.recentOrders")}</th>
                  <th className="px-3 py-2">{t("admin.watchlisted")}</th>
                  <th className="px-3 py-2">{t("admin.latestNote")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {users.map((user) => (
                  <tr
                    className={`cursor-pointer hover:bg-panel ${detail?.user_id === user.user_id ? "bg-blue-50" : ""}`}
                    key={user.user_id}
                    onClick={() => onSelect(user.user_id)}
                  >
                    <td className="px-3 py-2">
                      <div className="font-medium">#{user.user_id}</div>
                      <div className="text-xs text-neutral-500">{user.email}</div>
                    </td>
                    <td className="px-3 py-2"><RiskBadge level={user.risk_level} t={t} /></td>
                    <td className="px-3 py-2">{user.total_orders}</td>
                    <td className="px-3 py-2 text-xs text-neutral-600">
                      {t("admin.cancelShort")}: {formatRate(user.cancellation_rate)}<br />
                      {t("admin.expireShort")}: {formatRate(user.expiration_rate)}<br />
                      {t("admin.failShort")}: {formatRate(user.failed_rate)}
                    </td>
                    <td className="px-3 py-2 text-xs text-neutral-600">1h: {user.orders_last_1h}<br />24h: {user.orders_last_24h}</td>
                    <td className="px-3 py-2">{user.watchlisted ? t("admin.yes") : t("admin.no")}</td>
                    <td className="max-w-xs px-3 py-2 text-xs text-neutral-600">{user.latest_note ? truncate(user.latest_note, 80) : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="grid gap-4">
        <Card title={detail ? `${t("admin.riskDetail")} #${detail.user_id}` : t("admin.riskDetail")} description={detail?.email || t("admin.selectRiskUser")}>
          {detail ? (
            <div className="grid gap-3 text-sm">
              <div className="flex items-center justify-between"><span>{t("admin.riskLevel")}</span><RiskBadge level={detail.risk_level} t={t} /></div>
              <RiskDetailRow label={t("admin.riskScore")} value={detail.risk_score} />
              <RiskDetailRow label={t("admin.activeOrders")} value={detail.active_orders} />
              <RiskDetailRow label={t("admin.completedOrders")} value={detail.completed_orders} />
              <RiskDetailRow label={t("admin.apiRequestsLast1h")} value={detail.api_requests_last_1h} />
              <RiskDetailRow label={t("admin.managedKeys")} value={detail.managed_api_key_count} />
              <RiskDetailRow label={t("admin.revokedKeys")} value={detail.revoked_api_key_count} />
              <RiskDetailRow label={t("admin.lastOrder")} value={dateTime(detail.last_order_at)} />
              <RiskDetailRow label={t("admin.lastApiRequest")} value={dateTime(detail.last_api_request_at)} />
              <RiskDetailRow label={t("admin.lastReviewed")} value={dateTime(detail.last_reviewed_at)} />
            </div>
          ) : <p className="text-sm text-neutral-600">{t("admin.selectRiskUser")}</p>}
        </Card>

        <Card title={t("admin.addRiskAction")} description={t("admin.riskActionDesc")}>
          <div className="grid gap-3">
            <label className="grid gap-1 text-sm">
              {t("common.actions")}
              <select className="field" value={actionType} onChange={(event) => setActionType(event.target.value as AdminRiskActionType)} disabled={!detail}>
                <option value="watch">{t("admin.actionWatch")}</option>
                <option value="note">{t("admin.actionNote")}</option>
                <option value="clear_watch">{t("admin.actionClearWatch")}</option>
                <option value="mark_reviewed">{t("admin.actionMarkReviewed")}</option>
              </select>
            </label>
            <label className="grid gap-1 text-sm">
              {t("common.notes")} {t("common.optional")}
              <textarea className="field min-h-24" value={note} onChange={(event) => setNote(event.target.value)} maxLength={1000} disabled={!detail} />
            </label>
            <button className="btn btn-primary" onClick={onSubmit} disabled={!detail || actionLoading}>{actionLoading ? t("admin.saving") : t("admin.submitRiskAction")}</button>
          </div>
        </Card>

        <Card title={t("admin.riskActionHistory")}>
          {!actions.length ? <p className="text-sm text-neutral-600">{t("admin.noRiskActions")}</p> : (
            <div className="grid gap-3">
              {actions.map((action) => (
                <div className="rounded-md border border-line bg-panel p-3 text-sm" key={action.id}>
                  <div className="flex justify-between gap-3">
                    <strong>{action.action}</strong>
                    <span className="text-xs text-neutral-500">{dateTime(action.created_at)}</span>
                  </div>
                  {action.note && <p className="mt-2 text-neutral-700">{action.note}</p>}
                  <p className="mt-2 text-xs text-neutral-500">{t("common.actor")}: {action.actor_user_id ?? "-"}</p>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </section>
  );
}

function PaymentIntentsView({
  intents,
  detail,
  statusFilter,
  setStatusFilter,
  providerFilter,
  setProviderFilter,
  userFilter,
  setUserFilter,
  loading,
  manualCompleteLoading,
  onApplyFilters,
  onSelect,
  onManualComplete,
  t
}: {
  intents: AdminPaymentIntent[];
  detail: AdminPaymentIntent | null;
  statusFilter: string;
  setStatusFilter: (value: string) => void;
  providerFilter: string;
  setProviderFilter: (value: string) => void;
  userFilter: string;
  setUserFilter: (value: string) => void;
  loading: boolean;
  manualCompleteLoading: boolean;
  onApplyFilters: () => void;
  onSelect: (id: number) => void;
  onManualComplete: (id: number) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}) {
  const canManualComplete = detail?.provider === "manual_test" && ["created", "pending"].includes(detail.status);
  return (
    <section className="mt-6 grid gap-4 xl:grid-cols-[1.35fr_0.85fr]">
      <Card title={t("admin.paymentIntents")} description={t("admin.paymentIntentsDesc")}>
        <div className="mb-4 grid gap-3 md:grid-cols-[0.8fr_0.9fr_0.8fr_auto]">
          <label className="grid gap-1 text-sm">
            {t("common.status")}
            <select className="field" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">{t("admin.allStatuses")}</option>
              <option value="created">created</option>
              <option value="pending">pending</option>
              <option value="succeeded">succeeded</option>
              <option value="failed">failed</option>
              <option value="cancelled">cancelled</option>
              <option value="expired">expired</option>
            </select>
          </label>
          <label className="grid gap-1 text-sm">
            {t("common.provider")}
            <select className="field" value={providerFilter} onChange={(event) => setProviderFilter(event.target.value)}>
              <option value="">{t("admin.allProviders")}</option>
              <option value="manual_test">manual_test</option>
              <option value="payme">payme</option>
              <option value="click">click</option>
              <option value="crypto_usdt">crypto_usdt</option>
            </select>
          </label>
          <label className="grid gap-1 text-sm">
            user_id
            <input className="field" value={userFilter} onChange={(event) => setUserFilter(event.target.value)} inputMode="numeric" />
          </label>
          <button className="btn btn-secondary self-end" onClick={onApplyFilters}>{t("common.search")}</button>
        </div>
        {!intents.length ? (
          <p className="text-sm text-neutral-600">{loading ? t("common.loading") : t("admin.noRows")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-line text-sm">
              <thead className="bg-panel text-left text-xs uppercase tracking-wide text-neutral-500">
                <tr>
                  <th className="px-3 py-2">{t("common.id")}</th>
                  <th className="px-3 py-2">public_id</th>
                  <th className="px-3 py-2">{t("common.user")}</th>
                  <th className="px-3 py-2">{t("common.provider")}</th>
                  <th className="px-3 py-2">{t("common.amount")}</th>
                  <th className="px-3 py-2">{t("common.status")}</th>
                  <th className="px-3 py-2">{t("admin.providerReference")}</th>
                  <th className="px-3 py-2">{t("common.created")}</th>
                  <th className="px-3 py-2">{t("admin.webhook")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {intents.map((intent) => (
                  <tr
                    className={`cursor-pointer hover:bg-panel ${detail?.id === intent.id ? "bg-blue-50" : ""}`}
                    key={intent.id}
                    onClick={() => onSelect(intent.id)}
                  >
                    <td className="px-3 py-2">{intent.id}</td>
                    <td className="px-3 py-2">{truncate(intent.public_id, 14)}</td>
                    <td className="px-3 py-2">{intent.user_id}</td>
                    <td className="px-3 py-2">{intent.provider}</td>
                    <td className="px-3 py-2">{money(intent.amount, intent.currency)}</td>
                    <td className="px-3 py-2"><StatusBadge status={intent.status} /></td>
                    <td className="px-3 py-2">{intent.provider_reference ? truncate(intent.provider_reference, 16) : "-"}</td>
                    <td className="px-3 py-2">{dateTime(intent.created_at)}</td>
                    <td className="px-3 py-2">{intent.last_webhook_status || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="grid gap-4">
        <Card title={detail ? `${t("admin.paymentIntentDetail")} #${detail.id}` : t("admin.paymentIntentDetail")} description={detail?.public_id || t("admin.selectPaymentIntent")}>
          {detail ? (
            <div className="grid gap-3 text-sm">
              <RiskDetailRow label="public_id" value={detail.public_id} />
              <RiskDetailRow label={t("common.user")} value={detail.user_id} />
              <RiskDetailRow label={t("common.provider")} value={detail.provider} />
              <RiskDetailRow label={t("common.amount")} value={money(detail.amount, detail.currency)} />
              <div className="flex items-center justify-between"><span className="text-neutral-600">{t("common.status")}</span><StatusBadge status={detail.status} /></div>
              <RiskDetailRow label={t("admin.providerReference")} value={detail.provider_reference || "-"} />
              <RiskDetailRow label={t("admin.succeededAt")} value={dateTime(detail.succeeded_at)} />
              <RiskDetailRow label={t("admin.failedAt")} value={dateTime(detail.failed_at)} />
              <RiskDetailRow label={t("admin.cancelledAt")} value={dateTime(detail.cancelled_at)} />
              <RiskDetailRow label={t("admin.lastWebhookStatus")} value={detail.last_webhook_status || "-"} />
              <RiskDetailRow label={t("admin.lastWebhookAt")} value={dateTime(detail.last_webhook_at)} />
              <RiskDetailRow label={t("admin.lastWebhookEvent")} value={detail.last_webhook_event_id ? truncate(detail.last_webhook_event_id, 28) : "-"} />
              <RiskDetailRow label={t("admin.lastWebhookError")} value={detail.last_webhook_error || detail.failed_reason || "-"} />
              <button className="btn btn-primary mt-2" onClick={() => onManualComplete(detail.id)} disabled={!canManualComplete || manualCompleteLoading}>
                {manualCompleteLoading ? t("admin.saving") : t("admin.manualComplete")}
              </button>
              {!canManualComplete && <p className="text-xs text-neutral-500">{t("admin.manualCompleteUnavailable")}</p>}
            </div>
          ) : <p className="text-sm text-neutral-600">{t("admin.selectPaymentIntent")}</p>}
        </Card>
        {detail?.metadata && Object.keys(detail.metadata).length > 0 && (
          <Card title={t("common.metadata")}>
            <pre className="max-h-80 overflow-auto rounded-md bg-panel p-3 text-xs">{JSON.stringify(detail.metadata, null, 2)}</pre>
          </Card>
        )}
      </div>
    </section>
  );
}

function SupplierPayoutsView({
  payouts,
  detail,
  suppliers,
  statusFilter,
  setStatusFilter,
  supplierFilter,
  setSupplierFilter,
  loading,
  actionLoading,
  onApplyFilters,
  onSelect,
  onAction,
  t
}: {
  payouts: AdminSupplierPayoutRequest[];
  detail: AdminSupplierPayoutRequest | null;
  suppliers: Supplier[];
  statusFilter: string;
  setStatusFilter: (value: string) => void;
  supplierFilter: string;
  setSupplierFilter: (value: string) => void;
  loading: boolean;
  actionLoading: boolean;
  onApplyFilters: () => void;
  onSelect: (id: number) => void;
  onAction: (action: "approve" | "reject" | "paid", payout: AdminSupplierPayoutRequest) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}) {
  const supplierName = (supplierId: number) => suppliers.find((supplier) => supplier.id === supplierId)?.name || "-";
  return (
    <section className="mt-6 grid gap-4 xl:grid-cols-[1.35fr_0.85fr]">
      <Card title={t("admin.supplierPayouts")} description={t("admin.supplierPayoutsDesc")}>
        <div className="mb-4 grid gap-3 md:grid-cols-[0.9fr_0.8fr_auto]">
          <label className="grid gap-1 text-sm">
            {t("common.status")}
            <select className="field" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">{t("admin.allStatuses")}</option>
              <option value="requested">requested</option>
              <option value="approved">approved</option>
              <option value="rejected">rejected</option>
              <option value="cancelled">cancelled</option>
              <option value="paid">paid</option>
              <option value="failed">failed</option>
            </select>
          </label>
          <label className="grid gap-1 text-sm">
            supplier_id
            <input className="field" value={supplierFilter} onChange={(event) => setSupplierFilter(event.target.value)} inputMode="numeric" />
          </label>
          <button className="btn btn-secondary self-end" onClick={onApplyFilters}>{t("common.search")}</button>
        </div>
        {!payouts.length ? (
          <p className="text-sm text-neutral-600">{loading ? t("common.loading") : t("admin.noRows")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-line text-sm">
              <thead className="bg-panel text-left text-xs uppercase tracking-wide text-neutral-500">
                <tr>
                  <th className="px-3 py-2">public_id</th>
                  <th className="px-3 py-2">{t("admin.supplier")}</th>
                  <th className="px-3 py-2">{t("common.amount")}</th>
                  <th className="px-3 py-2">{t("common.status")}</th>
                  <th className="px-3 py-2">{t("common.created")}</th>
                  <th className="px-3 py-2">{t("admin.updated")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {payouts.map((payout) => (
                  <tr
                    className={`cursor-pointer hover:bg-panel ${detail?.id === payout.id ? "bg-blue-50" : ""}`}
                    key={payout.id}
                    onClick={() => onSelect(payout.id)}
                  >
                    <td className="px-3 py-2">{truncate(payout.public_id, 16)}</td>
                    <td className="px-3 py-2">
                      <div>#{payout.supplier_id}</div>
                      <div className="text-xs text-neutral-500">{supplierName(payout.supplier_id)}</div>
                    </td>
                    <td className="px-3 py-2">{money(payout.amount, payout.currency)}</td>
                    <td className="px-3 py-2"><StatusBadge status={payout.status} /></td>
                    <td className="px-3 py-2">{dateTime(payout.created_at)}</td>
                    <td className="px-3 py-2">{dateTime(payout.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title={detail ? `${t("admin.supplierPayoutDetail")} #${detail.id}` : t("admin.supplierPayoutDetail")} description={detail?.public_id || t("admin.selectSupplierPayout")}>
        {detail ? (
          <div className="grid gap-3 text-sm">
            <RiskDetailRow label="public_id" value={detail.public_id} />
            <RiskDetailRow label={t("admin.supplier")} value={`#${detail.supplier_id} ${supplierName(detail.supplier_id)}`} />
            <RiskDetailRow label={t("common.amount")} value={money(detail.amount, detail.currency)} />
            <div className="flex items-center justify-between"><span className="text-neutral-600">{t("common.status")}</span><StatusBadge status={detail.status} /></div>
            <RiskDetailRow label={t("admin.payoutMethod")} value={detail.payout_method || "-"} />
            <RiskDetailRow label={t("admin.payoutAddress")} value={detail.payout_address ? truncate(detail.payout_address, 36) : "-"} />
            <RiskDetailRow label={t("admin.requestedAt")} value={dateTime(detail.requested_at)} />
            <RiskDetailRow label={t("admin.approvedAt")} value={dateTime(detail.approved_at)} />
            <RiskDetailRow label={t("admin.rejectedAt")} value={dateTime(detail.rejected_at)} />
            <RiskDetailRow label={t("admin.paidAt")} value={dateTime(detail.paid_at)} />
            <RiskDetailRow label={t("admin.updated")} value={dateTime(detail.updated_at)} />
            <RiskDetailRow label={t("admin.adminNote")} value={detail.admin_note || "-"} />
            <RiskDetailRow label={t("admin.failureReason")} value={detail.failure_reason || "-"} />
            {detail.status === "requested" && (
              <div className="flex flex-wrap gap-2 pt-2">
                <button className="btn btn-primary" onClick={() => onAction("approve", detail)} disabled={actionLoading}>{actionLoading ? t("admin.saving") : t("admin.approvePayout")}</button>
                <button className="btn btn-secondary" onClick={() => onAction("reject", detail)} disabled={actionLoading}>{t("admin.rejectPayout")}</button>
              </div>
            )}
            {detail.status === "approved" && (
              <button className="btn btn-primary mt-2" onClick={() => onAction("paid", detail)} disabled={actionLoading}>{actionLoading ? t("admin.saving") : t("admin.markPayoutPaid")}</button>
            )}
            {["paid", "rejected", "cancelled", "failed"].includes(detail.status) && <p className="text-xs text-neutral-500">{t("admin.supplierPayoutReadOnly")}</p>}
          </div>
        ) : <p className="text-sm text-neutral-600">{t("admin.selectSupplierPayout")}</p>}
      </Card>
    </section>
  );
}

function RiskBadge({level, t}: {level: string; t: (key: string, vars?: Record<string, string | number>) => string}) {
  const classes: Record<string, string> = {
    low: "bg-green-50 text-green-700 ring-green-200",
    medium: "bg-amber-50 text-amber-800 ring-amber-200",
    high: "bg-red-50 text-red-700 ring-red-200"
  };
  return <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ring-1 ring-inset ${classes[level] || "bg-slate-50 text-slate-700 ring-slate-200"}`}>{t(`admin.risk${capitalize(level)}`)}</span>;
}

function RiskDetailRow({label, value}: {label: string; value: ReactNode}) {
  return <p className="flex justify-between gap-3 border-b border-line pb-2 last:border-0"><span className="text-neutral-600">{label}</span><strong>{value || "-"}</strong></p>;
}

function formatRate(value: number) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

function capitalize(value: string) {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : value;
}

function paymentIntentFilters(status: string, provider: string, userId: string) {
  const parsedUserId = Number(userId);
  return {
    ...(status ? {status} : {}),
    ...(provider ? {provider} : {}),
    ...(Number.isInteger(parsedUserId) && parsedUserId > 0 ? {user_id: parsedUserId} : {})
  };
}

function supplierPayoutFilters(status: string, supplierId: string) {
  const parsedSupplierId = Number(supplierId);
  return {
    ...(status ? {status} : {}),
    ...(Number.isInteger(parsedSupplierId) && parsedSupplierId > 0 ? {supplier_id: parsedSupplierId} : {})
  };
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

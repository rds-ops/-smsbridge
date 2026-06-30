"use client";

import Link from "next/link";
import {useEffect, useState} from "react";
import {DataTable} from "@/components/shared/data-table";
import {Alert, Card, CopyButton, MetricCard, PageHeader, PageShell, StatusBadge, Toast} from "@/components/shared/ui";
import {createSupplierPayoutRequest, getSupplierActivations, getSupplierInventory, getSupplierPayoutRequests, getSupplierTransactions, pushSupplierSms, supplierMe, updateSupplierInventory} from "@/lib/supplier/api";
import {dateTime, money, percent, truncate} from "@/lib/shared/format";
import type {SupplierActivationHistoryRow, SupplierInventoryRow, SupplierPayoutRequest, SupplierProfile, SupplierSmsPushResponse, SupplierTransactionHistoryRow} from "@/lib/shared/types";
import {useTranslation} from "@/lib/i18n";

type SupplierTab = "profile" | "inventory" | "activations" | "sms" | "payouts" | "transactions";

const storageKey = "smsbridge_supplier_api_key";
const TRANSACTION_LIMIT = 50;
const ACTIVATION_LIMIT = 50;

export default function SupplierPage() {
  const {t} = useTranslation();
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [profile, setProfile] = useState<SupplierProfile | null>(null);
  const [inventory, setInventory] = useState<SupplierInventoryRow[]>([]);
  const [activations, setActivations] = useState<SupplierActivationHistoryRow[]>([]);
  const [activationOffset, setActivationOffset] = useState(0);
  const [activationsHasMore, setActivationsHasMore] = useState(false);
  const [activationsLoadingMore, setActivationsLoadingMore] = useState(false);
  const [payouts, setPayouts] = useState<SupplierPayoutRequest[]>([]);
  const [transactions, setTransactions] = useState<SupplierTransactionHistoryRow[]>([]);
  const [transactionOffset, setTransactionOffset] = useState(0);
  const [transactionsHasMore, setTransactionsHasMore] = useState(false);
  const [transactionsLoadingMore, setTransactionsLoadingMore] = useState(false);
  const [tab, setTab] = useState<SupplierTab>("profile");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<{type: "success" | "error"; message: string} | null>(null);

  const [serviceCode, setServiceCode] = useState("telegram");
  const [countryIso2, setCountryIso2] = useState("US");
  const [operator, setOperator] = useState("");
  const [availableCount, setAvailableCount] = useState("0");
  const [successRate, setSuccessRate] = useState("");
  const [avgSmsTime, setAvgSmsTime] = useState("");
  const [inventoryStatus, setInventoryStatus] = useState("active");

  const [activationStatusFilter, setActivationStatusFilter] = useState("");
  const [activationServiceFilter, setActivationServiceFilter] = useState("");
  const [activationCountryFilter, setActivationCountryFilter] = useState("");
  const [activationPhoneFilter, setActivationPhoneFilter] = useState("");

  const [payoutAmount, setPayoutAmount] = useState("");
  const [payoutMethod, setPayoutMethod] = useState("");
  const [payoutAddress, setPayoutAddress] = useState("");
  const [supplierSmsId, setSupplierSmsId] = useState("");
  const [smsPhoneNumber, setSmsPhoneNumber] = useState("");
  const [smsPhoneFrom, setSmsPhoneFrom] = useState("");
  const [smsText, setSmsText] = useState("");
  const [smsActivationId, setSmsActivationId] = useState("");
  const [smsLoading, setSmsLoading] = useState(false);
  const [smsResult, setSmsResult] = useState<SupplierSmsPushResponse | null>(null);

  useEffect(() => {
    const stored = sessionStorage.getItem(storageKey);
    if (stored) {
      setApiKey(stored);
      load(stored);
    }
  }, []);

  async function load(key = apiKey) {
    if (!key) return;
    setLoading(true);
    setError("");
    try {
      const [profileData, inventoryData, activationData, payoutData] = await Promise.all([
        supplierMe(key),
        getSupplierInventory(key),
        getSupplierActivations(key, {limit: ACTIVATION_LIMIT, offset: 0}),
        getSupplierPayoutRequests(key)
      ]);
      const transactionData = await getSupplierTransactions(key, {limit: TRANSACTION_LIMIT, offset: 0});
      setProfile(profileData);
      setInventory(inventoryData);
      setActivations(activationData);
      setActivationOffset(0);
      setActivationsHasMore(activationData.length === ACTIVATION_LIMIT);
      setPayouts(payoutData);
      setTransactions(transactionData);
      setTransactionOffset(0);
      setTransactionsHasMore(transactionData.length === TRANSACTION_LIMIT);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("supplierCabinet.loadFailed"));
    } finally {
      setLoading(false);
    }
  }

  async function connect() {
    const trimmed = apiKeyInput.trim();
    if (!trimmed) {
      setError(t("supplierCabinet.keyRequired"));
      return;
    }
    sessionStorage.setItem(storageKey, trimmed);
    setApiKey(trimmed);
    setApiKeyInput("");
    await load(trimmed);
  }

  function clearKey() {
    sessionStorage.removeItem(storageKey);
    setApiKey("");
    setApiKeyInput("");
    setProfile(null);
    setInventory([]);
    setActivations([]);
    setActivationOffset(0);
    setActivationsHasMore(false);
    setActivationStatusFilter("");
    setActivationServiceFilter("");
    setActivationCountryFilter("");
    setActivationPhoneFilter("");
    setPayouts([]);
    setTransactions([]);
    setTransactionOffset(0);
    setTransactionsHasMore(false);
    setError("");
  }

  async function submitInventory(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const count = Number(availableCount);
    const country = countryIso2.trim().toUpperCase();
    if (!serviceCode.trim() || country.length !== 2 || !Number.isFinite(count) || count < 0) {
      setToast({type: "error", message: t("supplierCabinet.invalidInventory")});
      return;
    }
    try {
      await updateSupplierInventory(apiKey, [{
        service_code: serviceCode.trim(),
        country_iso2: country,
        operator: operator.trim() || null,
        available_count: count,
        success_rate: successRate.trim() || null,
        avg_sms_time_seconds: avgSmsTime.trim() ? Number(avgSmsTime) : null,
        status: inventoryStatus
      }]);
      setInventory(await getSupplierInventory(apiKey));
      setToast({type: "success", message: t("supplierCabinet.updatedInventory")});
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("supplierCabinet.updateFailed")});
    }
  }

  async function submitPayout(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const amount = Number(payoutAmount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setToast({type: "error", message: t("supplierCabinet.invalidAmount")});
      return;
    }
    try {
      await createSupplierPayoutRequest(apiKey, {
        amount: payoutAmount.trim(),
        payout_method: payoutMethod.trim() || null,
        payout_address: payoutAddress.trim() || null
      });
      const [profileData, payoutData, transactionData] = await Promise.all([
        supplierMe(apiKey),
        getSupplierPayoutRequests(apiKey),
        getSupplierTransactions(apiKey, {limit: TRANSACTION_LIMIT, offset: 0})
      ]);
      setProfile(profileData);
      setPayouts(payoutData);
      setTransactions(transactionData);
      setTransactionOffset(0);
      setTransactionsHasMore(transactionData.length === TRANSACTION_LIMIT);
      setPayoutAmount("");
      setPayoutMethod("");
      setPayoutAddress("");
      setToast({type: "success", message: t("supplierCabinet.payoutCreated")});
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("supplierCabinet.payoutFailed")});
    }
  }

  async function submitSms(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const supplierSmsIdValue = supplierSmsId.trim();
    const phoneNumber = smsPhoneNumber.trim();
    const text = smsText.trim();
    if (!supplierSmsIdValue || !phoneNumber || !text) {
      setToast({type: "error", message: t("supplierCabinet.smsRequired")});
      return;
    }
    if (!phoneNumber.startsWith("+")) {
      setToast({type: "error", message: t("supplierCabinet.smsPhoneInvalid")});
      return;
    }
    setSmsLoading(true);
    setSmsResult(null);
    try {
      const result = await pushSupplierSms(apiKey, {
        supplier_sms_id: supplierSmsIdValue,
        phone_number: phoneNumber,
        phone_from: smsPhoneFrom.trim() || null,
        text,
        supplier_activation_id: smsActivationId.trim() || null
      });
      setSmsResult(result);
      setSmsText("");
      refreshActivations();
      setToast({
        type: "success",
        message: result.duplicate ? t("supplierCabinet.smsDuplicate") : t("supplierCabinet.smsPushed")
      });
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("supplierCabinet.smsFailed")});
    } finally {
      setSmsLoading(false);
    }
  }

  function activationFilters() {
    return {
      status: activationStatusFilter.trim() || undefined,
      service: activationServiceFilter.trim() || undefined,
      country: activationCountryFilter.trim() ? activationCountryFilter.trim().toUpperCase() : undefined,
      phone: activationPhoneFilter.trim() || undefined
    };
  }

  async function refreshActivations(event?: React.FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (!apiKey) return;
    try {
      const rows = await getSupplierActivations(apiKey, {limit: ACTIVATION_LIMIT, offset: 0, ...activationFilters()});
      setActivations(rows);
      setActivationOffset(0);
      setActivationsHasMore(rows.length === ACTIVATION_LIMIT);
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("supplierCabinet.activationsFailed")});
    }
  }

  async function clearActivationFilters() {
    setActivationStatusFilter("");
    setActivationServiceFilter("");
    setActivationCountryFilter("");
    setActivationPhoneFilter("");
    if (!apiKey) return;
    try {
      const rows = await getSupplierActivations(apiKey, {limit: ACTIVATION_LIMIT, offset: 0});
      setActivations(rows);
      setActivationOffset(0);
      setActivationsHasMore(rows.length === ACTIVATION_LIMIT);
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("supplierCabinet.activationsFailed")});
    }
  }

  async function loadMoreActivations() {
    if (!apiKey || activationsLoadingMore) return;
    const nextOffset = activationOffset + ACTIVATION_LIMIT;
    setActivationsLoadingMore(true);
    try {
      const nextRows = await getSupplierActivations(apiKey, {limit: ACTIVATION_LIMIT, offset: nextOffset, ...activationFilters()});
      setActivations((current) => [...current, ...nextRows]);
      setActivationOffset(nextOffset);
      setActivationsHasMore(nextRows.length === ACTIVATION_LIMIT);
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("supplierCabinet.activationsFailed")});
    } finally {
      setActivationsLoadingMore(false);
    }
  }

  async function loadMoreTransactions() {
    if (!apiKey || transactionsLoadingMore) return;
    const nextOffset = transactionOffset + TRANSACTION_LIMIT;
    setTransactionsLoadingMore(true);
    try {
      const nextRows = await getSupplierTransactions(apiKey, {limit: TRANSACTION_LIMIT, offset: nextOffset});
      setTransactions((current) => [...current, ...nextRows]);
      setTransactionOffset(nextOffset);
      setTransactionsHasMore(nextRows.length === TRANSACTION_LIMIT);
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("supplierCabinet.transactionsFailed")});
    } finally {
      setTransactionsLoadingMore(false);
    }
  }

  return (
    <PageShell wide>
      {toast && <Toast type={toast.type} message={toast.message} />}
      <PageHeader
        title={t("supplierCabinet.title")}
        description={t("supplierCabinet.description")}
        actions={apiKey ? <button className="btn btn-secondary" onClick={clearKey}>{t("supplierCabinet.clearKey")}</button> : undefined}
      />

      {!apiKey ? (
        <section className="mt-6 max-w-xl">
          <Card title={t("supplierCabinet.keyTitle")} description={t("supplierCabinet.keyDesc")}>
            <form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); connect(); }}>
              <input
                className="field"
                type="password"
                value={apiKeyInput}
                onChange={(event) => setApiKeyInput(event.target.value)}
                placeholder={t("supplierCabinet.keyPlaceholder")}
                autoComplete="off"
              />
              <button className="btn btn-primary justify-self-start" type="submit">{t("supplierCabinet.connect")}</button>
            </form>
            <p className="mt-4 text-sm leading-6 text-neutral-600">{t("supplierCabinet.sessionWarning")}</p>
            <Link className="btn btn-secondary mt-3 w-fit" href="/suppliers">{t("supplierCabinet.applyLink")}</Link>
            {error && <div className="mt-4"><Alert type="error">{error}</Alert></div>}
          </Card>
        </section>
      ) : (
        <>
          {error && <div className="mt-4"><Alert type="error">{error}</Alert></div>}
          <div className="mt-6 flex flex-wrap gap-2">
            {(["profile", "inventory", "activations", "sms", "payouts", "transactions"] as SupplierTab[]).map((item) => (
              <button className={`btn ${tab === item ? "btn-primary" : "btn-secondary"}`} key={item} onClick={() => setTab(item)}>
                {t(`supplierCabinet.${item}`)}
              </button>
            ))}
            <button className="btn btn-secondary" onClick={() => load()}>{loading ? t("common.refreshing") : t("common.refresh")}</button>
          </div>

          {tab === "profile" && (
            <section className="mt-6 grid gap-4 lg:grid-cols-5">
              <MetricCard label={t("common.balance")} value={money(profile?.balance, profile?.currency)} helper={t("common.availableBalance")} />
              <MetricCard label={t("common.heldBalance")} value={money(profile?.held_balance, profile?.currency)} helper={t("common.held")} />
              <MetricCard label={t("common.rewardPercent")} value={percent(profile?.reward_percent)} helper={t("common.supplierReward")} />
              <MetricCard label={t("common.status")} value={profile ? <StatusBadge status={profile.status} /> : "-"} />
              <MetricCard label={t("common.currency")} value={profile?.currency || "-"} />
              <Card className="lg:col-span-5" title={profile?.name || t("supplierCabinet.profile")} description={t("supplierCabinet.profileDesc")}>
                <div className="grid gap-3 text-sm md:grid-cols-3">
                  <Detail label={t("common.id")} value={profile?.id ?? "-"} />
                  <Detail label={t("common.email")} value={profile?.email || "-"} />
                  <Detail label={t("common.status")} value={profile ? <StatusBadge status={profile.status} /> : "-"} />
                </div>
              </Card>
            </section>
          )}

          {tab === "inventory" && (
            <section className="mt-6 grid gap-4 xl:grid-cols-[0.85fr_1.35fr]">
              <Card title={t("supplierCabinet.updateInventory")} description={t("supplierCabinet.updateInventoryDesc")}>
                <form className="grid gap-3" onSubmit={submitInventory}>
                  <label className="grid gap-1 text-sm">
                    {t("supplierCabinet.serviceCode")}
                    <input className="field" value={serviceCode} onChange={(event) => setServiceCode(event.target.value)} />
                  </label>
                  <label className="grid gap-1 text-sm">
                    {t("supplierCabinet.countryIso")}
                    <input className="field" value={countryIso2} onChange={(event) => setCountryIso2(event.target.value)} maxLength={2} />
                  </label>
                  <label className="grid gap-1 text-sm">
                    {t("supplierCabinet.operatorOptional")}
                    <input className="field" value={operator} onChange={(event) => setOperator(event.target.value)} />
                  </label>
                  <label className="grid gap-1 text-sm">
                    {t("supplierCabinet.availableCount")}
                    <input className="field" value={availableCount} onChange={(event) => setAvailableCount(event.target.value)} inputMode="numeric" />
                  </label>
                  <label className="grid gap-1 text-sm">
                    {t("supplierCabinet.successRate")}
                    <input className="field" value={successRate} onChange={(event) => setSuccessRate(event.target.value)} inputMode="decimal" />
                  </label>
                  <label className="grid gap-1 text-sm">
                    {t("supplierCabinet.avgSmsTime")}
                    <input className="field" value={avgSmsTime} onChange={(event) => setAvgSmsTime(event.target.value)} inputMode="numeric" />
                  </label>
                  <label className="grid gap-1 text-sm">
                    {t("common.status")}
                    <select className="field" value={inventoryStatus} onChange={(event) => setInventoryStatus(event.target.value)}>
                      <option value="active">{t("status.active")}</option>
                      <option value="inactive">{t("status.inactive")}</option>
                    </select>
                  </label>
                  <button className="btn btn-primary justify-self-start" type="submit">{t("supplierCabinet.updateInventory")}</button>
                </form>
              </Card>
              <Card title={t("supplierCabinet.inventory")} description={t("supplierCabinet.inventoryDesc")}>
                <DataTable
                  rows={inventory as unknown as Record<string, unknown>[]}
                  emptyTitle={t("supplierCabinet.noInventory")}
                  columns={[
                    {key: "service_code", header: t("common.service")},
                    {key: "country_iso2", header: t("common.country")},
                    {key: "operator", header: t("common.operator"), render: (row) => row.operator ? String(row.operator) : t("common.any")},
                    {key: "available_count", header: t("common.availableCount")},
                    {key: "status", header: t("common.status"), render: (row) => <StatusBadge status={String(row.status)} />},
                    {key: "success_rate", header: t("common.successRate"), render: (row) => row.success_rate ? percent(row.success_rate) : "-"},
                    {key: "avg_sms_time_seconds", header: t("common.avgSmsTime"), render: (row) => row.avg_sms_time_seconds ? String(row.avg_sms_time_seconds) : "-"},
                    {key: "last_sync_at", header: t("common.lastSync"), render: (row) => dateTime(row.last_sync_at || row.updated_at)}
                  ]}
                />
              </Card>
            </section>
          )}

          {tab === "activations" && (
            <section className="mt-6">
              <Card title={t("supplierCabinet.activations")} description={t("supplierCabinet.activationsDesc")}>
                <form className="mb-4 grid gap-3 lg:grid-cols-[1fr_1fr_1fr_1.2fr_auto_auto]" onSubmit={refreshActivations}>
                  <label className="grid gap-1 text-sm">
                    {t("common.status")}
                    <select className="field" value={activationStatusFilter} onChange={(event) => setActivationStatusFilter(event.target.value)}>
                      <option value="">{t("admin.allStatuses")}</option>
                      <option value="reserved">{t("status.reserved")}</option>
                      <option value="waiting_sms">{t("status.waiting_sms")}</option>
                      <option value="sms_received">{t("status.sms_received")}</option>
                      <option value="completed">{t("status.completed")}</option>
                      <option value="cancelled">{t("status.cancelled")}</option>
                      <option value="expired">{t("status.expired")}</option>
                      <option value="refunded">{t("status.refunded")}</option>
                      <option value="failed">{t("status.failed")}</option>
                    </select>
                  </label>
                  <label className="grid gap-1 text-sm">
                    {t("common.service")}
                    <input
                      className="field"
                      value={activationServiceFilter}
                      onChange={(event) => setActivationServiceFilter(event.target.value)}
                      placeholder="telegram"
                    />
                  </label>
                  <label className="grid gap-1 text-sm">
                    {t("common.country")}
                    <input
                      className="field"
                      value={activationCountryFilter}
                      onChange={(event) => setActivationCountryFilter(event.target.value)}
                      placeholder="ID"
                      maxLength={2}
                    />
                  </label>
                  <label className="grid gap-1 text-sm">
                    {t("common.phone")}
                    <input
                      className="field"
                      value={activationPhoneFilter}
                      onChange={(event) => setActivationPhoneFilter(event.target.value)}
                      placeholder="+628123456789"
                    />
                  </label>
                  <button className="btn btn-secondary self-end" type="submit">{t("common.refresh")}</button>
                  <button className="btn btn-secondary self-end" type="button" onClick={clearActivationFilters}>{t("common.clearFilters")}</button>
                </form>
                <DataTable
                  rows={activations as unknown as Record<string, unknown>[]}
                  emptyTitle={t("supplierCabinet.noActivations")}
                  columns={[
                    {
                      key: "supplier_activation_id",
                      header: t("common.supplierActivationId"),
                      render: (row) => (
                        <span className="flex min-w-0 items-center gap-2">
                          <span className="truncate">{row.supplier_activation_id ? truncate(row.supplier_activation_id, 22) : "-"}</span>
                          <CopyButton value={row.supplier_activation_id ? String(row.supplier_activation_id) : null} />
                        </span>
                      )
                    },
                    {
                      key: "phone_number",
                      header: t("common.phone"),
                      render: (row) => (
                        <span className="flex min-w-0 items-center gap-2">
                          <span className="truncate">{String(row.phone_number || "-")}</span>
                          <CopyButton value={row.phone_number ? String(row.phone_number) : null} />
                        </span>
                      )
                    },
                    {key: "service_code", header: t("common.service")},
                    {key: "country_iso2", header: t("common.country")},
                    {key: "operator", header: t("common.operator"), render: (row) => row.operator ? String(row.operator) : t("common.any")},
                    {key: "status", header: t("common.status"), render: (row) => <StatusBadge status={String(row.status)} />},
                    {
                      key: "order_public_id",
                      header: t("common.order"),
                      render: (row) => row.order_public_id ? (
                        <span className="flex min-w-0 items-center gap-2">
                          <span className="truncate">{truncate(row.order_public_id, 18)}</span>
                          <CopyButton value={String(row.order_public_id)} />
                        </span>
                      ) : "-"
                    },
                    {key: "sms_count", header: t("supplierCabinet.smsCount")},
                    {key: "latest_sms_at", header: t("supplierCabinet.latestSmsAt"), render: (row) => dateTime(row.latest_sms_at)},
                    {key: "created_at", header: t("common.createdAt"), render: (row) => dateTime(row.created_at)},
                    {key: "updated_at", header: t("supplierCabinet.updatedAt"), render: (row) => dateTime(row.updated_at)}
                  ]}
                />
                {activationsHasMore && (
                  <div className="mt-4">
                    <button className="btn btn-secondary" onClick={loadMoreActivations} disabled={activationsLoadingMore}>
                      {activationsLoadingMore ? t("common.loading") : t("supplierCabinet.loadMoreActivations")}
                    </button>
                  </div>
                )}
              </Card>
            </section>
          )}

          {tab === "sms" && (
            <section className="mt-6 grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
              <Card title={t("supplierCabinet.pushSms")} description={t("supplierCabinet.smsHelperDesc")}>
                <form className="grid gap-3" onSubmit={submitSms}>
                  <label className="grid gap-1 text-sm">
                    {t("supplierCabinet.supplierSmsId")}
                    <input className="field" value={supplierSmsId} onChange={(event) => setSupplierSmsId(event.target.value)} autoComplete="off" />
                  </label>
                  <label className="grid gap-1 text-sm">
                    {t("supplierCabinet.phoneNumber")}
                    <input className="field" value={smsPhoneNumber} onChange={(event) => setSmsPhoneNumber(event.target.value)} placeholder="+628123456789" autoComplete="off" />
                  </label>
                  <label className="grid gap-1 text-sm">
                    {t("supplierCabinet.phoneFromOptional")}
                    <input className="field" value={smsPhoneFrom} onChange={(event) => setSmsPhoneFrom(event.target.value)} placeholder="Telegram" autoComplete="off" />
                  </label>
                  <label className="grid gap-1 text-sm">
                    {t("supplierCabinet.smsText")}
                    <textarea className="field min-h-28" value={smsText} onChange={(event) => setSmsText(event.target.value)} autoComplete="off" />
                  </label>
                  <label className="grid gap-1 text-sm">
                    {t("supplierCabinet.activationIdOptional")}
                    <input className="field" value={smsActivationId} onChange={(event) => setSmsActivationId(event.target.value)} autoComplete="off" />
                  </label>
                  <button className="btn btn-primary justify-self-start" disabled={smsLoading} type="submit">
                    {smsLoading ? t("common.saving") : t("supplierCabinet.pushSms")}
                  </button>
                </form>
              </Card>
              <Card title={t("supplierCabinet.smsResult")} description={t("supplierCabinet.smsResultDesc")}>
                <div className="grid gap-4">
                  <Alert type="info">{t("supplierCabinet.smsHelperNote")}</Alert>
                  {smsResult ? (
                    <div className="grid gap-3 md:grid-cols-2">
                      <Detail label={t("common.status")} value={smsResult.status} />
                      <Detail
                        label={t("supplierCabinet.duplicate")}
                        value={
                          <span className={`rounded-full px-2 py-1 text-xs font-medium ring-1 ring-inset ${
                            smsResult.duplicate ? "bg-amber-50 text-amber-800 ring-amber-200" : "bg-green-50 text-green-700 ring-green-200"
                          }`}>
                            {smsResult.duplicate ? t("common.yes") : t("common.no")}
                          </span>
                        }
                      />
                    </div>
                  ) : (
                    <p className="text-sm leading-6 text-neutral-600">{t("supplierCabinet.noSmsResult")}</p>
                  )}
                  <p className="text-xs leading-5 text-neutral-500">{t("supplierCabinet.smsSafetyNote")}</p>
                </div>
              </Card>
            </section>
          )}

          {tab === "payouts" && (
            <section className="mt-6 grid gap-4 xl:grid-cols-[0.75fr_1.45fr]">
              <Card title={t("supplierCabinet.createPayout")} description={t("supplierCabinet.payoutDesc")}>
                <form className="grid gap-3" onSubmit={submitPayout}>
                  <label className="grid gap-1 text-sm">
                    {t("common.amount")}
                    <input className="field" value={payoutAmount} onChange={(event) => setPayoutAmount(event.target.value)} inputMode="decimal" />
                  </label>
                  <label className="grid gap-1 text-sm">
                    {t("supplierCabinet.payoutMethod")}
                    <input className="field" value={payoutMethod} onChange={(event) => setPayoutMethod(event.target.value)} />
                  </label>
                  <label className="grid gap-1 text-sm">
                    {t("supplierCabinet.payoutAddress")}
                    <input className="field" value={payoutAddress} onChange={(event) => setPayoutAddress(event.target.value)} />
                  </label>
                  <button className="btn btn-primary justify-self-start" type="submit">{t("supplierCabinet.createPayout")}</button>
                </form>
              </Card>
              <Card title={t("supplierCabinet.payouts")} description={t("supplierCabinet.payoutDesc")}>
                <DataTable
                  rows={payouts as unknown as Record<string, unknown>[]}
                  emptyTitle={t("supplierCabinet.noPayouts")}
                  columns={[
                    {key: "public_id", header: t("common.id"), render: (row) => truncate(row.public_id, 18)},
                    {key: "amount", header: t("common.amount"), render: (row) => money(row.amount, String(row.currency || profile?.currency || "USD"))},
                    {key: "status", header: t("common.status"), render: (row) => <StatusBadge status={String(row.status)} />},
                    {key: "payout_method", header: t("supplierCabinet.payoutMethod"), render: (row) => row.payout_method ? String(row.payout_method) : "-"},
                    {key: "requested_at", header: t("supplierCabinet.requestedAt"), render: (row) => dateTime(row.requested_at || row.created_at)},
                    {key: "updated_at", header: t("supplierCabinet.updatedAt"), render: (row) => dateTime(row.updated_at)}
                  ]}
                />
              </Card>
            </section>
          )}

          {tab === "transactions" && (
            <section className="mt-6">
              <Card title={t("supplierCabinet.transactions")} description={t("supplierCabinet.transactionsDesc")}>
                <DataTable
                  rows={transactions as unknown as Record<string, unknown>[]}
                  emptyTitle={t("supplierCabinet.noTransactions")}
                  columns={[
                    {key: "type", header: t("common.type"), render: (row) => <StatusBadge status={String(row.type)} />},
                    {key: "amount", header: t("common.amount"), render: (row) => money(row.amount, String(row.currency || profile?.currency || "USD"))},
                    {key: "status", header: t("common.status"), render: (row) => <StatusBadge status={String(row.status)} />},
                    {key: "reference", header: t("common.reference"), render: (row) => row.reference ? truncate(row.reference, 24) : "-"},
                    {key: "order_public_id", header: t("common.order"), render: (row) => row.order_public_id ? truncate(row.order_public_id, 18) : "-"},
                    {key: "created_at", header: t("common.createdAt"), render: (row) => dateTime(row.created_at)}
                  ]}
                />
                {transactionsHasMore && (
                  <div className="mt-4">
                    <button className="btn btn-secondary" onClick={loadMoreTransactions} disabled={transactionsLoadingMore}>
                      {transactionsLoadingMore ? t("common.loading") : t("supplierCabinet.loadMoreTransactions")}
                    </button>
                  </div>
                )}
              </Card>
            </section>
          )}
        </>
      )}
    </PageShell>
  );
}

function Detail({label, value}: {label: string; value: React.ReactNode}) {
  return (
    <div className="rounded-md border border-line bg-panel p-3">
      <p className="text-xs uppercase text-neutral-500">{label}</p>
      <div className="mt-1 font-medium">{value}</div>
    </div>
  );
}

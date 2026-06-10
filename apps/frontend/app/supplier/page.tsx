"use client";

import {useEffect, useState} from "react";
import {DataTable} from "@/components/shared/data-table";
import {Alert, Card, MetricCard, PageHeader, PageShell, StatusBadge, Toast} from "@/components/shared/ui";
import {createSupplierPayoutRequest, getSupplierInventory, getSupplierPayoutRequests, supplierMe, updateSupplierInventory} from "@/lib/supplier/api";
import {dateTime, money, percent, truncate} from "@/lib/shared/format";
import type {SupplierInventoryRow, SupplierPayoutRequest, SupplierProfile} from "@/lib/shared/types";
import {useTranslation} from "@/lib/i18n";

type SupplierTab = "profile" | "inventory" | "payouts";

const storageKey = "smsbridge_supplier_api_key";

export default function SupplierPage() {
  const {t} = useTranslation();
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [profile, setProfile] = useState<SupplierProfile | null>(null);
  const [inventory, setInventory] = useState<SupplierInventoryRow[]>([]);
  const [payouts, setPayouts] = useState<SupplierPayoutRequest[]>([]);
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

  const [payoutAmount, setPayoutAmount] = useState("");
  const [payoutMethod, setPayoutMethod] = useState("");
  const [payoutAddress, setPayoutAddress] = useState("");

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
      const [profileData, inventoryData, payoutData] = await Promise.all([
        supplierMe(key),
        getSupplierInventory(key),
        getSupplierPayoutRequests(key)
      ]);
      setProfile(profileData);
      setInventory(inventoryData);
      setPayouts(payoutData);
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
    setPayouts([]);
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
      const [profileData, payoutData] = await Promise.all([supplierMe(apiKey), getSupplierPayoutRequests(apiKey)]);
      setProfile(profileData);
      setPayouts(payoutData);
      setPayoutAmount("");
      setPayoutMethod("");
      setPayoutAddress("");
      setToast({type: "success", message: t("supplierCabinet.payoutCreated")});
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("supplierCabinet.payoutFailed")});
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
            {error && <div className="mt-4"><Alert type="error">{error}</Alert></div>}
          </Card>
        </section>
      ) : (
        <>
          {error && <div className="mt-4"><Alert type="error">{error}</Alert></div>}
          <div className="mt-6 flex flex-wrap gap-2">
            {(["profile", "inventory", "payouts"] as SupplierTab[]).map((item) => (
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

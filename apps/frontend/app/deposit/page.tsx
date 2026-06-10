"use client";

import {useState} from "react";
import Link from "next/link";
import {Alert, Card, CopyButton, MetricCard, PageHeader, PageShell, StatusBadge, Toast} from "@/components/shared/ui";
import {createPaymentIntent, getPaymentIntent} from "@/lib/client/api";
import {dateTime, money} from "@/lib/shared/format";
import type {PaymentIntent} from "@/lib/shared/types";
import {useTranslation} from "@/lib/i18n";

function makeIdempotencyKey() {
  const cryptoApi = typeof crypto !== "undefined" ? crypto : undefined;
  if (cryptoApi?.randomUUID) return `deposit-${cryptoApi.randomUUID()}`;
  return `deposit-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export default function DepositPage() {
  const {t} = useTranslation();
  const [amount, setAmount] = useState("10.00");
  const [currency, setCurrency] = useState("USD");
  const [provider, setProvider] = useState("manual_test");
  const [lookupPublicId, setLookupPublicId] = useState("");
  const [intent, setIntent] = useState<PaymentIntent | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<{type: "success" | "error"; message: string}>({type: "success", message: ""});

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const numericAmount = Number(amount);
    if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
      setError(t("deposit.invalidAmount"));
      return;
    }
    setLoading(true);
    setError("");
    setToast({type: "success", message: ""});
    try {
      const key = makeIdempotencyKey();
      const created = await createPaymentIntent({
        amount: amount.trim(),
        currency: currency.trim().toUpperCase() || "USD",
        provider
      }, key);
      setIdempotencyKey(key);
      setIntent(created);
      setLookupPublicId(created.public_id);
      setToast({type: "success", message: t("deposit.created")});
    } catch (err) {
      setError(err instanceof Error ? err.message : t("deposit.createFailed"));
    } finally {
      setLoading(false);
    }
  }

  async function lookup() {
    const publicId = lookupPublicId.trim();
    if (!publicId) {
      setError(t("deposit.publicIdRequired"));
      return;
    }
    setLoading(true);
    setError("");
    try {
      setIntent(await getPaymentIntent(publicId));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("deposit.lookupFailed"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <PageShell>
      <Toast type={toast.type} message={toast.message} />
      <PageHeader
        title={t("deposit.title")}
        description={t("deposit.description")}
        actions={<Link className="btn btn-secondary" href="/dashboard">{t("nav.dashboard")}</Link>}
      />

      {error && <div className="mt-4"><Alert type="error">{error}</Alert></div>}

      <section className="mt-6 grid gap-4 lg:grid-cols-[0.85fr_1.15fr]">
        <Card title={t("deposit.createTitle")} description={t("deposit.createDesc")}>
          <form className="grid gap-3" onSubmit={submit}>
            <label className="grid gap-1 text-sm">
              {t("common.amount")}
              <input className="field" value={amount} onChange={(event) => setAmount(event.target.value)} inputMode="decimal" />
            </label>
            <label className="grid gap-1 text-sm">
              {t("common.currency")}
              <input className="field" value={currency} onChange={(event) => setCurrency(event.target.value)} maxLength={3} />
            </label>
            <label className="grid gap-1 text-sm">
              {t("common.provider")}
              <select className="field" value={provider} onChange={(event) => setProvider(event.target.value)}>
                <option value="manual_test">manual_test</option>
              </select>
            </label>
            <button className="btn btn-primary justify-self-start" disabled={loading} type="submit">
              {loading ? t("common.saving") : t("deposit.createButton")}
            </button>
          </form>
          <Alert type="info">
            {t("deposit.manualOnly")}
          </Alert>
        </Card>

        <Card title={t("deposit.intentTitle")} description={t("deposit.intentDesc")}>
          <div className="mb-4 grid gap-3 md:grid-cols-[1fr_auto]">
            <input className="field" value={lookupPublicId} onChange={(event) => setLookupPublicId(event.target.value)} placeholder="pi_..." />
            <button className="btn btn-secondary" onClick={lookup} disabled={loading}>{t("common.refresh")}</button>
          </div>
          {intent ? (
            <div className="grid gap-4">
              <div className="grid gap-3 md:grid-cols-3">
                <MetricCard label={t("common.amount")} value={money(intent.amount, intent.currency)} />
                <MetricCard label={t("common.status")} value={<StatusBadge status={intent.status} />} />
                <MetricCard label={t("common.provider")} value={intent.provider} />
              </div>
              <div className="grid gap-3 rounded-md border border-line bg-panel p-4 text-sm md:grid-cols-2">
                <Detail label="public_id" value={<span className="flex items-center gap-2"><code className="break-all">{intent.public_id}</code><CopyButton value={intent.public_id} /></span>} />
                <Detail label={t("common.currency")} value={intent.currency} />
                <Detail label={t("common.created")} value={dateTime(intent.created_at)} />
                <Detail label={t("common.expiresAt")} value={dateTime(intent.expires_at)} />
                <Detail label="Idempotency-Key" value={idempotencyKey ? <span className="flex items-center gap-2"><code className="break-all">{idempotencyKey}</code><CopyButton value={idempotencyKey} /></span> : "-"} />
              </div>
              <Alert type="info">{t("deposit.adminCompleteHint")}</Alert>
            </div>
          ) : (
            <p className="text-sm text-neutral-600">{t("deposit.noIntent")}</p>
          )}
        </Card>
      </section>
    </PageShell>
  );
}

function Detail({label, value}: {label: string; value: React.ReactNode}) {
  return (
    <div>
      <p className="text-xs uppercase text-neutral-500">{label}</p>
      <div className="mt-1 font-medium">{value}</div>
    </div>
  );
}

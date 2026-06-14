"use client";

import Link from "next/link";
import {useEffect, useMemo, useState} from "react";
import {SmsMarketplace} from "@/components/buyer/SmsMarketplace";
import {DataTable} from "@/components/shared/data-table";
import {Alert, Card, CopyButton, PageHeader, PageShell, StatusBadge, Toast} from "@/components/shared/ui";
import {cancelOrder, finishOrder, listOrders} from "@/lib/client/api";
import {countdown, dateTime, money} from "@/lib/shared/format";
import type {Order} from "@/lib/shared/types";
import {useTranslation} from "@/lib/i18n";

const activeStatuses = new Set(["created", "reserved", "waiting_sms", "sms_received"]);

export default function OrdersPage() {
  const {t} = useTranslation();
  const [status, setStatus] = useState("");
  const [service, setService] = useState("");
  const [country, setCountry] = useState("");
  const [orders, setOrders] = useState<Order[]>([]);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<{type: "success" | "error"; message: string}>({type: "success", message: ""});
  const [busyOrder, setBusyOrder] = useState("");

  async function load() {
    try {
      setOrders(await listOrders({status, service, country}));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("orders.couldNotLoad"));
    }
  }

  useEffect(() => {
    load();
  }, [status, service, country]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      if (orders.some((order) => activeStatuses.has(order.status))) load();
    }, 5000);
    return () => window.clearInterval(interval);
  }, [orders, status, service, country]);

  async function action(publicId: string, kind: "finish" | "cancel") {
    setBusyOrder(publicId);
    setToast({type: "success", message: ""});
    try {
      await (kind === "finish" ? finishOrder(publicId) : cancelOrder(publicId));
      setToast({type: "success", message: kind === "finish" ? t("orders.finishedToast") : t("orders.cancelledToast")});
      await load();
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("orders.actionFailed")});
    } finally {
      setBusyOrder("");
    }
  }

  const serviceOptions = useMemo(() => Array.from(new Set(orders.map((order) => order.service_code))).sort(), [orders]);
  const countryOptions = useMemo(() => Array.from(new Set(orders.map((order) => order.country_iso2))).sort(), [orders]);

  return (
    <SmsMarketplace>
    <PageShell wide>
      <Toast type={toast.type} message={toast.message} />
      <PageHeader
        title={t("orders.title")}
        description={t("orders.description")}
        actions={<Link className="btn btn-primary" href="/buy">{t("orders.newOrder")}</Link>}
      />
      <Card className="mt-6" title={t("orders.filters")} description={t("orders.filtersDesc")}>
        <div className="grid gap-3 md:grid-cols-4">
          <select className="field" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">{t("orders.allStatuses")}</option>
            {["waiting_sms", "sms_received", "completed", "cancelled", "expired", "refunded", "failed"].map((item) => <option key={item} value={item}>{t(`status.${item}`)}</option>)}
          </select>
          <input className="field" value={service} onChange={(e) => setService(e.target.value)} placeholder={t("orders.serviceCode")} list="services" />
          <datalist id="services">{serviceOptions.map((item) => <option key={item} value={item} />)}</datalist>
          <input className="field" value={country} onChange={(e) => setCountry(e.target.value)} placeholder={t("orders.countryIso")} list="countries" />
          <datalist id="countries">{countryOptions.map((item) => <option key={item} value={item} />)}</datalist>
          <button className="btn btn-secondary" onClick={() => { setStatus(""); setService(""); setCountry(""); }}>{t("common.clearFilters")}</button>
        </div>
      </Card>

      <Card className="mt-6" title={t("orders.statusGuide")} description={t("orders.statusGuideDesc")}>
        <div className="grid gap-2 text-sm text-neutral-700 md:grid-cols-2 lg:grid-cols-4">
          <p><StatusBadge status="waiting_sms" /> {t("orders.waitingGuide")}</p>
          <p><StatusBadge status="sms_received" /> {t("orders.receivedGuide")}</p>
          <p><StatusBadge status="completed" /> {t("orders.completedGuide")}</p>
          <p><StatusBadge status="cancelled" /> {t("orders.cancelledGuide")}</p>
          <p><StatusBadge status="expired" /> {t("orders.expiredGuide")}</p>
          <p><StatusBadge status="refunded" /> {t("orders.refundedGuide")}</p>
          <p><StatusBadge status="failed" /> {t("orders.failedGuide")}</p>
        </div>
      </Card>

      {error && <div className="mt-4"><Alert type="error">{error}</Alert></div>}
      <section className="mt-6">
        <DataTable
          rows={orders as unknown as Record<string, unknown>[]}
          emptyTitle={t("orders.noOrders")}
          emptyDescription={t("orders.noOrdersDesc")}
          columns={[
            {key: "public_id", header: t("common.order"), render: (row) => <Link className="text-accent" href={`/orders/${row.public_id}`}>{String(row.public_id).slice(0, 8)}</Link>},
            {key: "service_code", header: t("common.service")},
            {key: "country_iso2", header: t("common.country")},
            {key: "phone_number", header: t("common.phone"), render: (row) => <div className="flex items-center gap-2"><span>{String(row.phone_number || "-")}</span><CopyButton value={row.phone_number ? String(row.phone_number) : null} /></div>},
            {key: "status", header: t("common.status"), render: (row) => <StatusBadge status={String(row.status)} />},
            {key: "price", header: t("common.price"), render: (row) => money(row.price)},
            {key: "sms_code", header: t("common.smsCode"), render: (row) => <div className="flex items-center gap-2"><span>{String(row.sms_code || "-")}</span><CopyButton value={row.sms_code ? String(row.sms_code) : null} /></div>},
            {key: "expires_at", header: t("common.countdown"), render: (row) => activeStatuses.has(String(row.status)) ? countdown(row.expires_at) : "-"},
            {key: "created_at", header: t("common.created"), render: (row) => dateTime(row.created_at)},
            {key: "actions", header: t("common.actions"), render: (row) => (
              <div className="flex flex-wrap gap-2">
                <Link className="btn btn-secondary px-2 py-1 text-xs" href={`/orders/${row.public_id}`}>{t("orders.view")}</Link>
                <button className="btn btn-primary px-2 py-1 text-xs" disabled={busyOrder === row.public_id || row.status !== "sms_received"} onClick={() => action(String(row.public_id), "finish")}>{t("orders.finish")}</button>
                <button className="btn btn-secondary px-2 py-1 text-xs" disabled={busyOrder === row.public_id || !["created", "reserved", "waiting_sms", "sms_received"].includes(String(row.status))} onClick={() => action(String(row.public_id), "cancel")}>{t("orders.cancel")}</button>
              </div>
            )}
          ]}
        />
      </section>
    </PageShell>
    </SmsMarketplace>
  );
}

"use client";

import {useEffect, useMemo, useState} from "react";
import Link from "next/link";
import {SmsMarketplace} from "@/components/buyer/SmsMarketplace";
import {Alert, Card, CopyButton, PageHeader, PageShell, StatusBadge, Toast} from "@/components/shared/ui";
import {cancelOrder, finishOrder, getBalance, getOrder} from "@/lib/client/api";
import {countdown, dateTime, money} from "@/lib/shared/format";
import type {Order, Wallet} from "@/lib/shared/types";
import {useTranslation} from "@/lib/i18n";

export default function OrderPage({params}: {params: {public_id: string}}) {
  const {t} = useTranslation();
  const [order, setOrder] = useState<Order | null>(null);
  const [balance, setBalance] = useState<Wallet | null>(null);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<{type: "success" | "error"; message: string}>({type: "success", message: ""});
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(Date.now());
  const active = useMemo(() => order ? ["created", "reserved", "waiting_sms", "sms_received"].includes(order.status) : false, [order]);

  async function load() {
    try {
      const [orderData, wallet] = await Promise.all([getOrder(params.public_id), getBalance()]);
      setOrder(orderData);
      setBalance(wallet);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("orderDetail.loadFailed"));
    }
  }

  useEffect(() => {
    load();
    const poll = window.setInterval(() => {
      if (active) load();
    }, 5000);
    const tick = window.setInterval(() => setNow(Date.now()), 1000);
    return () => {
      window.clearInterval(poll);
      window.clearInterval(tick);
    };
  }, [params.public_id, active]);

  async function action(kind: "cancel" | "finish") {
    setBusy(true);
    setToast({type: "success", message: ""});
    setError("");
    try {
      const updated = kind === "finish" ? await finishOrder(params.public_id) : await cancelOrder(params.public_id);
      setOrder(updated);
      setBalance(await getBalance());
      setToast({type: "success", message: kind === "finish" ? t("orderDetail.finishedToast") : t("orderDetail.cancelledToast")});
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("orderDetail.actionFailed")});
    } finally {
      setBusy(false);
    }
  }

  const secondsLabel = order?.expires_at ? countdown(order.expires_at) : "-";
  void now;

  return (
    <SmsMarketplace>
    <PageShell>
      <Toast type={toast.type} message={toast.message} />
      <PageHeader
        title={t("orderDetail.title")}
        description={t("orderDetail.description")}
        actions={<Link className="btn btn-secondary" href="/orders">{t("orderDetail.back")}</Link>}
      />
      {error && <div className="mt-4"><Alert type="error">{error}</Alert></div>}

      <section className="mt-6 grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <Card title={t("orderDetail.numberTitle")}>
          <div className="grid gap-4">
            <div>
              <p className="text-sm text-neutral-500">{t("orderDetail.phoneNumber")}</p>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <p className="text-2xl font-semibold">{order?.phone_number || "-"}</p>
                <CopyButton value={order?.phone_number} label={t("orderDetail.copyNumber")} />
              </div>
            </div>
            <div>
              <p className="text-sm text-neutral-500">{t("common.smsCode")}</p>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <p className="text-2xl font-semibold">{order?.sms_code || "-"}</p>
                <CopyButton value={order?.sms_code} label={t("orderDetail.copySms")} />
              </div>
              {order?.sms_text && <p className="mt-2 rounded-md bg-panel p-3 text-sm">{order.sms_text}</p>}
            </div>
          </div>
        </Card>

        <Card title={t("orderDetail.walletAfterRefresh")}>
          <p className="text-sm text-neutral-500">{t("orderDetail.available")}</p>
          <p className="mt-1 text-xl font-semibold">{money(balance?.balance, balance?.currency)}</p>
          <p className="mt-4 text-sm text-neutral-500">{t("orderDetail.held")}</p>
          <p className="mt-1 text-xl font-semibold">{money(balance?.held_balance, balance?.currency)}</p>
        </Card>
      </section>

      <Card className="mt-6" title={t("orderDetail.info")}>
        <div className="grid gap-3 text-sm md:grid-cols-2">
          <Info label="public_id" value={order?.public_id} />
          <p><span className="text-neutral-500">{t("common.status")}:</span> {order?.status ? <StatusBadge status={order.status} /> : "-"}</p>
          <Info label={t("common.service")} value={order?.service_code} />
          <Info label={t("common.country")} value={order?.country_iso2} />
          <Info label={t("common.operator")} value={order?.operator || t("common.any")} />
          <Info label={t("common.price")} value={money(order?.price)} />
          <Info label={t("common.created")} value={dateTime(order?.created_at)} />
          <Info label={t("common.expires")} value={dateTime(order?.expires_at)} />
          <Info label={t("common.countdown")} value={active ? secondsLabel : "-"} />
        </div>
        <div className="mt-6 rounded-lg border border-line bg-panel p-4">
          <h3 className="text-sm font-semibold">{t("orderDetail.timeline")}</h3>
          <div className="mt-3 grid gap-2 text-sm text-neutral-600 md:grid-cols-4">
            {[t("orderDetail.createdStep"), t("orderDetail.waitingStep"), t("orderDetail.receivedStep"), t("orderDetail.finalStep")].map((item, index) => (
              <div className="flex items-center gap-2" key={item}>
                <span className="grid h-6 w-6 place-items-center rounded-full bg-white text-xs font-semibold text-accent ring-1 ring-line">{index + 1}</span>
                {item}
              </div>
            ))}
          </div>
        </div>
        <div className="mt-5 flex flex-wrap gap-3">
          <button className="btn btn-secondary" disabled={busy || !active} onClick={() => action("cancel")}>{t("orders.cancel")}</button>
          <button className="btn btn-primary" disabled={busy || order?.status !== "sms_received"} onClick={() => action("finish")}>{t("orders.finish")}</button>
        </div>
      </Card>
    </PageShell>
    </SmsMarketplace>
  );
}

function Info({label, value}: {label: string; value: React.ReactNode}) {
  return <p><span className="text-neutral-500">{label}:</span> <strong>{value || "-"}</strong></p>;
}

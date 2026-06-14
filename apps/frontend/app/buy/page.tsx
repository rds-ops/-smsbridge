"use client";

import {useEffect, useMemo, useRef, useState} from "react";
import {useRouter} from "next/navigation";
import {Alert, Card, PageHeader, PageShell, Toast} from "@/components/shared/ui";
import {createOrder, getBalance, getCountries, getPrices, getServices} from "@/lib/client/api";
import {money, percent} from "@/lib/shared/format";
import type {Country, Price, Service, Wallet} from "@/lib/shared/types";
import {useTranslation} from "@/lib/i18n";

export default function BuyPage() {
  const router = useRouter();
  const {t, locale} = useTranslation();
  const [services, setServices] = useState<Service[]>([]);
  const [countries, setCountries] = useState<Country[]>([]);
  const [prices, setPrices] = useState<Price[]>([]);
  const [balance, setBalance] = useState<Wallet | null>(null);
  const [service, setService] = useState("telegram");
  const [country, setCountry] = useState("ID");
  const [operator, setOperator] = useState("");
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [buying, setBuying] = useState(false);
  const pendingOrderKeyRef = useRef<string | null>(null);

  async function load() {
    setError("");
    try {
      const [serviceRows, countryRows, priceRows, wallet] = await Promise.all([
        getServices(),
        getCountries(),
        getPrices(),
        getBalance()
      ]);
      setServices(serviceRows);
      setCountries(countryRows);
      setPrices(priceRows);
      setBalance(wallet);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("buy.loadFailed"));
    }
  }

  useEffect(() => {
    load();
  }, []);

  const selected = useMemo(() => prices.find((p) => p.service_code === service && p.country_iso2 === country), [prices, service, country]);
  const availableBalance = Number(balance?.balance || 0);
  const requiredPrice = Number(selected?.final_price || 0);
  const hasPrice = Boolean(selected);
  const hasFunds = hasPrice && availableBalance >= requiredPrice;

  function createOrderIdempotencyKey() {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) return `order-${crypto.randomUUID()}`;
    return `order-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }

  async function buy() {
    if (!hasFunds || buying || pendingOrderKeyRef.current) return;
    const idempotencyKey = createOrderIdempotencyKey();
    pendingOrderKeyRef.current = idempotencyKey;
    setBuying(true);
    setError("");
    setToast("");
    try {
      const order = await createOrder({service_code: service, country_iso2: country, operator: operator || null}, idempotencyKey);
      setToast(t("buy.success"));
      await getBalance().then(setBalance).catch(() => null);
      router.push(`/orders/${order.public_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("buy.orderFailed"));
    } finally {
      pendingOrderKeyRef.current = null;
      setBuying(false);
    }
  }

  return (
    <PageShell>
      <Toast type="success" message={toast} />
      <PageHeader
        title={t("buy.title")}
        description={t("buy.description")}
      />
      {error && <div className="mt-4"><Alert type="error">{error}</Alert></div>}

      <section className="mt-6 grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <Card title={t("buy.selectTitle")} description={t("buy.selectDesc")}>
          <div className="grid gap-4">
            <label className="grid gap-2 text-sm font-medium">
              {t("common.service")}
              <select className="field" value={service} onChange={(e) => setService(e.target.value)}>
                {services.map((item) => <option key={item.code} value={item.code}>{locale === "ru" ? item.name_ru : item.name_en} · {item.code}</option>)}
              </select>
            </label>
            <label className="grid gap-2 text-sm font-medium">
              {t("common.country")}
              <select className="field" value={country} onChange={(e) => setCountry(e.target.value)}>
                {countries.map((item) => <option key={item.iso2} value={item.iso2}>{locale === "ru" ? item.name_ru : item.name_en} · {item.iso2}</option>)}
              </select>
            </label>
            <label className="grid gap-2 text-sm font-medium">
              {t("common.operator")} <span className="font-normal text-neutral-500">{t("common.optional")}</span>
              <input className="field" value={operator} onChange={(e) => setOperator(e.target.value)} placeholder={t("buy.leaveEmpty")} />
            </label>
          </div>
        </Card>

        <Card title={t("buy.selectedPrice")} description={t("buy.priceDesc")}>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-md border border-line bg-panel p-3">
              <p className="text-xs text-neutral-500">{t("common.availableBalance")}</p>
              <p className="mt-1 text-xl font-semibold">{money(balance?.balance, balance?.currency)}</p>
              <p className="mt-1 text-xs text-neutral-500">{t("buy.fundsAvailable")}</p>
            </div>
            <div className="rounded-md border border-line bg-panel p-3">
              <p className="text-xs text-neutral-500">{t("buy.requiredPrice")}</p>
              <p className="mt-1 text-xl font-semibold">{hasPrice ? money(selected?.final_price) : "-"}</p>
              <p className="mt-1 text-xs text-neutral-500">{t("buy.heldWhenBuy")}</p>
            </div>
          </div>
          <div className="mt-4 grid gap-2 text-sm">
            <p><span className="text-neutral-500">{t("common.service")}:</span> <strong>{service}</strong></p>
            <p><span className="text-neutral-500">{t("common.country")}:</span> <strong>{country}</strong></p>
            <p><span className="text-neutral-500">{t("common.operator")}:</span> <strong>{operator || t("common.any")}</strong></p>
            <p><span className="text-neutral-500">{t("common.availability")}:</span> <strong>{selected?.available_count ?? "-"}</strong></p>
            <p><span className="text-neutral-500">{t("common.deliveryRate")}:</span> <strong>{selected ? percent(selected.delivery_rate) : "-"}</strong></p>
            <p><span className="text-neutral-500">{t("common.provider")}:</span> <strong>{selected?.provider_name || selected?.provider_code || "MockProvider"}</strong></p>
            <p><span className="text-neutral-500">{t("buy.timeout")}:</span> <strong>{t("buy.timeoutValue")}</strong></p>
          </div>
          {!hasPrice && <div className="mt-4"><Alert type="error">{t("buy.noPrice")}</Alert></div>}
          {hasPrice && !hasFunds && (
            <div className="mt-4">
              <Alert type="error">{t("buy.insufficient")}</Alert>
            </div>
          )}
          <button className="btn btn-primary mt-5 w-full" onClick={buy} disabled={!hasFunds || buying}>
            {buying ? t("buy.creating") : t("buy.buyButton")}
          </button>
        </Card>
      </section>
    </PageShell>
  );
}

"use client";

import {useEffect, useMemo, useRef, useState} from "react";
import Link from "next/link";
import {ArrowRight, Code2, Loader2, Search, ShieldCheck, Wallet} from "lucide-react";
import {Alert, CopyButton, EmptyState, StatusBadge, Toast} from "@/components/shared/ui";
import {Button} from "@/components/ui/button";
import {Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle} from "@/components/ui/dialog";
import {Input} from "@/components/ui/input";
import {Tabs, TabsList, TabsTrigger} from "@/components/ui/tabs";
import {cancelOrder, createOrder, finishOrder, getBalance, getCountries, getOrder, getPrices, getServices} from "@/lib/client/api";
import {auth, currentUser, getToken} from "@/lib/shared/api";
import {countdown, money, percent} from "@/lib/shared/format";
import type {Country, Order, Price, Service, User, Wallet as WalletType} from "@/lib/shared/types";
import {useTranslation} from "@/lib/i18n";
import type {Locale} from "@/lib/i18n";

const selectionStorageKey = "smsbridge_marketplace_selection";
const visibleLimit = 7;

const previewServices: Service[] = [
  {code: "telegram", name_en: "Telegram", name_ru: "Telegram", category: "messaging", is_active: true},
  {code: "whatsapp", name_en: "WhatsApp", name_ru: "WhatsApp", category: "messaging", is_active: true},
  {code: "google", name_en: "Google", name_ru: "Google", category: "identity", is_active: true},
  {code: "facebook", name_en: "Facebook", name_ru: "Facebook", category: "social", is_active: true},
  {code: "amazon", name_en: "Amazon", name_ru: "Amazon", category: "commerce", is_active: true},
  {code: "openai", name_en: "OpenAI", name_ru: "OpenAI", category: "developer", is_active: true}
];

const previewCountries: Country[] = [
  {iso2: "ID", name_en: "Indonesia", name_ru: "Индонезия", is_active: true},
  {iso2: "IN", name_en: "India", name_ru: "Индия", is_active: true},
  {iso2: "BR", name_en: "Brazil", name_ru: "Бразилия", is_active: true},
  {iso2: "KZ", name_en: "Kazakhstan", name_ru: "Казахстан", is_active: true},
  {iso2: "PH", name_en: "Philippines", name_ru: "Филиппины", is_active: true},
  {iso2: "UZ", name_en: "Uzbekistan", name_ru: "Узбекистан", is_active: true},
  {iso2: "MX", name_en: "Mexico", name_ru: "Мексика", is_active: true}
];

const previewPrices: Price[] = previewServices.flatMap((service, serviceIndex) => (
  previewCountries.map((country, countryIndex) => ({
    service_code: service.code,
    country_iso2: country.iso2,
    operator: null,
    final_price: (0.18 + serviceIndex * 0.015 + countryIndex * 0.01).toFixed(4),
    available_count: 120 + serviceIndex * 24 + countryIndex * 13,
    delivery_rate: (92 + ((serviceIndex + countryIndex) % 6)).toFixed(2),
    provider_code: "preview",
    provider_name: "Preview catalog"
  }))
));

type Selection = {
  service: string;
  country: string;
  operator: string;
};

type PickerRow = {
  code: string;
  name: string;
  badge: string;
  count: number;
  price?: string | null;
};

export function SmsMarketplace({children}: {children?: React.ReactNode}) {
  const {t, locale, setLocale} = useTranslation();
  const [user, setUser] = useState<User | null>(null);
  const [services, setServices] = useState<Service[]>(previewServices);
  const [countries, setCountries] = useState<Country[]>(previewCountries);
  const [prices, setPrices] = useState<Price[]>(previewPrices);
  const [balance, setBalance] = useState<WalletType | null>(null);
  const [service, setService] = useState("telegram");
  const [country, setCountry] = useState("ID");
  const [operator, setOperator] = useState("");
  const [serviceSearch, setServiceSearch] = useState("");
  const [countrySearch, setCountrySearch] = useState("");
  const [showAllServices, setShowAllServices] = useState(false);
  const [showAllCountries, setShowAllCountries] = useState(false);
  const [loading, setLoading] = useState(true);
  const [buying, setBuying] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<{type: "success" | "error"; message: string}>({type: "success", message: ""});
  const [authOpen, setAuthOpen] = useState(false);
  const [order, setOrder] = useState<Order | null>(null);
  const [orderBusy, setOrderBusy] = useState(false);
  const pendingOrderKeyRef = useRef<string | null>(null);

  useEffect(() => {
    const saved = restoreSelection();
    if (saved) {
      setService(saved.service);
      setCountry(saved.country);
      setOperator(saved.operator);
    }
    loadCatalog();
  }, []);

  useEffect(() => {
    saveSelection({service, country, operator});
  }, [country, operator, service]);

  useEffect(() => {
    if (!order || !["created", "reserved", "waiting_sms", "sms_received"].includes(order.status)) return;
    const timer = window.setInterval(() => {
      getOrder(order.public_id).then(setOrder).catch(() => null);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [order?.public_id, order?.status]);

  async function loadCatalog() {
    setLoading(true);
    setError("");
    if (!getToken()) {
      setUser(null);
      setBalance(null);
      setServices(previewServices);
      setCountries(previewCountries);
      setPrices(previewPrices);
      setLoading(false);
      return;
    }
    try {
      const [me, serviceRows, countryRows, priceRows, wallet] = await Promise.all([
        currentUser(),
        getServices(),
        getCountries(),
        getPrices(),
        getBalance()
      ]);
      setUser(me as User);
      setServices(serviceRows);
      setCountries(countryRows);
      setPrices(priceRows);
      setBalance(wallet);
      if (serviceRows.length && !serviceRows.some((item) => item.code === service)) setService(serviceRows[0].code);
      if (countryRows.length && !countryRows.some((item) => item.iso2 === country)) setCountry(countryRows[0].iso2);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("buy.loadFailed"));
    } finally {
      setLoading(false);
    }
  }

  const serviceRows = useMemo(() => services.map((item) => {
    const rows = prices.filter((price) => price.service_code === item.code);
    return {
      code: item.code,
      name: locale === "ru" ? item.name_ru : item.name_en,
      badge: serviceBadge(item.code),
      count: sumAvailable(rows),
      price: minPrice(rows)
    };
  }), [locale, prices, services]);

  const countryRows = useMemo(() => countries.map((item) => {
    const rows = prices.filter((price) => price.country_iso2 === item.iso2 && price.service_code === service);
    return {
      code: item.iso2,
      name: locale === "ru" ? item.name_ru : item.name_en,
      badge: item.iso2,
      count: sumAvailable(rows),
      price: minPrice(rows)
    };
  }), [countries, locale, prices, service]);

  const selectedPrices = useMemo(() => prices.filter((price) => price.service_code === service && price.country_iso2 === country), [country, prices, service]);
  const selected = useMemo(() => {
    const requestedOperator = operator.trim().toLowerCase();
    if (requestedOperator) {
      const exact = selectedPrices.find((price) => String(price.operator || "").toLowerCase() === requestedOperator);
      if (exact) return exact;
    }
    return selectedPrices.find((price) => !price.operator || price.operator === "any") || selectedPrices[0];
  }, [operator, selectedPrices]);

  const serviceName = nameForService(services, service, locale);
  const countryName = nameForCountry(countries, country, locale);
  const hasPrice = Boolean(selected);
  const availableBalance = Number(balance?.balance || 0);
  const requiredPrice = Number(selected?.final_price || 0);
  const hasFunds = Boolean(!user || (hasPrice && availableBalance >= requiredPrice));
  const canBuy = Boolean(hasPrice && hasFunds && !buying && !loading);
  const filteredServices = filterRows(serviceRows, serviceSearch);
  const filteredCountries = filterRows(countryRows, countrySearch);

  async function buy() {
    if (!user) {
      saveSelection({service, country, operator});
      setAuthOpen(true);
      return;
    }
    if (!canBuy || pendingOrderKeyRef.current) return;
    const idempotencyKey = createOrderIdempotencyKey();
    pendingOrderKeyRef.current = idempotencyKey;
    setBuying(true);
    setError("");
    setToast({type: "success", message: ""});
    try {
      const created = await createOrder({service_code: service, country_iso2: country, operator: operator.trim() || null}, idempotencyKey);
      setOrder(created);
      setToast({type: "success", message: t("buy.successInline")});
      await getBalance().then(setBalance).catch(() => null);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("buy.orderFailed"));
    } finally {
      pendingOrderKeyRef.current = null;
      setBuying(false);
    }
  }

  async function orderAction(kind: "cancel" | "finish") {
    if (!order) return;
    setOrderBusy(true);
    try {
      const updated = kind === "finish" ? await finishOrder(order.public_id) : await cancelOrder(order.public_id);
      setOrder(updated);
      setBalance(await getBalance());
      setToast({type: "success", message: kind === "finish" ? t("orders.finishedToast") : t("orders.cancelledToast")});
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("orderDetail.actionFailed")});
    } finally {
      setOrderBusy(false);
    }
  }

  async function handleAuthSuccess(nextUser: User) {
    setUser(nextUser);
    setAuthOpen(false);
    setToast({type: "success", message: t("buy.authSuccess")});
    await loadCatalog();
  }

  return (
    <div className="min-h-screen bg-background">
      <Toast type={toast.type} message={toast.message} />
      <div className="mx-auto grid max-w-7xl gap-5 px-4 py-6 lg:grid-cols-[320px_minmax(0,1fr)] lg:px-6">
        <MarketplaceStorefront
          balance={balance}
          buying={buying}
          canBuy={canBuy}
          country={country}
          countryRows={showAllCountries ? filteredCountries : filteredCountries.slice(0, visibleLimit)}
          countrySearch={countrySearch}
          filteredCountryCount={filteredCountries.length}
          filteredServiceCount={filteredServices.length}
          hasFunds={hasFunds}
          hasPrice={hasPrice}
          loading={loading}
          onBuy={buy}
          onCountrySearch={setCountrySearch}
          onSelectCountry={setCountry}
          onSelectService={setService}
          onServiceSearch={setServiceSearch}
          onShowAllCountries={() => setShowAllCountries(true)}
          onShowAllServices={() => setShowAllServices(true)}
          operator={operator}
          price={selected}
          service={service}
          serviceRows={showAllServices ? filteredServices : filteredServices.slice(0, visibleLimit)}
          serviceSearch={serviceSearch}
          setOperator={setOperator}
          showAllCountries={showAllCountries}
          showAllServices={showAllServices}
          user={user}
        />
        <section className="grid gap-5">
          {error && <Alert type="error">{error}</Alert>}
          {order ? (
            <OrderStatusPanel
              busy={orderBusy}
              onAction={orderAction}
              order={order}
              onBackToMarket={() => setOrder(null)}
            />
          ) : children ? (
            <div className="min-w-0">{children}</div>
          ) : (
            <MarketplaceHomeContent
              canBuy={canBuy}
              countryName={countryName}
              hasFunds={hasFunds}
              hasPrice={hasPrice}
              onBuy={buy}
              price={selected}
              serviceName={serviceName}
              user={user}
            />
          )}
        </section>
      </div>
      {authOpen && (
        <AuthGateModal
          locale={locale}
          onClose={() => setAuthOpen(false)}
          onLocaleChange={setLocale}
          onSuccess={handleAuthSuccess}
        />
      )}
    </div>
  );
}

function MarketplaceStorefront({
  balance,
  buying,
  canBuy,
  country,
  countryRows,
  countrySearch,
  filteredCountryCount,
  filteredServiceCount,
  hasFunds,
  hasPrice,
  loading,
  onBuy,
  onCountrySearch,
  onSelectCountry,
  onSelectService,
  onServiceSearch,
  onShowAllCountries,
  onShowAllServices,
  operator,
  price,
  service,
  serviceRows,
  serviceSearch,
  setOperator,
  showAllCountries,
  showAllServices,
  user
}: {
  balance: WalletType | null;
  buying: boolean;
  canBuy: boolean;
  country: string;
  countryRows: PickerRow[];
  countrySearch: string;
  filteredCountryCount: number;
  filteredServiceCount: number;
  hasFunds: boolean;
  hasPrice: boolean;
  loading: boolean;
  onBuy: () => void;
  onCountrySearch: (value: string) => void;
  onSelectCountry: (value: string) => void;
  onSelectService: (value: string) => void;
  onServiceSearch: (value: string) => void;
  onShowAllCountries: () => void;
  onShowAllServices: () => void;
  operator: string;
  price?: Price;
  service: string;
  serviceRows: PickerRow[];
  serviceSearch: string;
  setOperator: (value: string) => void;
  showAllCountries: boolean;
  showAllServices: boolean;
  user: User | null;
}) {
  const {t} = useTranslation();
  return (
    <aside className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:sticky lg:top-24 lg:max-h-[calc(100vh-7rem)] lg:overflow-y-auto">
      <div className="rounded-2xl bg-blue-50 px-4 py-3 text-center text-sm font-semibold text-accent ring-1 ring-blue-100">
        {t("buy.activations")}
      </div>
      <PickerBlock
        count={filteredServiceCount}
        heading={t("buy.serviceHeading")}
        loading={loading}
        onSearch={onServiceSearch}
        onSelect={onSelectService}
        onShowAll={onShowAllServices}
        placeholder={t("buy.searchService")}
        rows={serviceRows}
        search={serviceSearch}
        selected={service}
        showAll={showAllServices}
        showAllLabel={t("buy.showAllServices")}
      />
      <PickerBlock
        count={filteredCountryCount}
        heading={t("buy.countryHeading")}
        loading={loading}
        onSearch={onCountrySearch}
        onSelect={onSelectCountry}
        onShowAll={onShowAllCountries}
        placeholder={t("buy.searchCountry")}
        rows={countryRows}
        search={countrySearch}
        selected={country}
        showAll={showAllCountries}
        showAllLabel={t("buy.showAllCountries")}
      />
      <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
        <label className="grid gap-1 text-sm font-medium">
          {t("common.operator")} <span className="font-normal text-neutral-500">{t("common.optional")}</span>
          <input className="field" value={operator} onChange={(event) => setOperator(event.target.value)} placeholder={t("buy.leaveEmpty")} />
        </label>
      </div>
      <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <SummaryRow label={t("common.price")} value={hasPrice ? money(price?.final_price) : "-"} strong />
        <SummaryRow label={t("common.availability")} value={price?.available_count ?? "-"} />
        <SummaryRow label={t("common.deliveryRate")} value={price ? percent(price.delivery_rate) : "-"} />
        {user && <SummaryRow label={t("common.availableBalance")} value={money(balance?.balance, balance?.currency)} />}
        {!hasPrice && <p className="mt-3 text-xs leading-5 text-red-700">{t("buy.noPrice")}</p>}
        {user && hasPrice && !hasFunds && <p className="mt-3 text-xs leading-5 text-red-700">{t("buy.insufficient")}</p>}
        {!user && <p className="mt-3 text-xs leading-5 text-neutral-500">{t("buy.previewNotice")}</p>}
        <button className="btn btn-primary mt-4 w-full" disabled={user ? !canBuy : !hasPrice} onClick={onBuy}>
          {buying ? <Loader2 size={16} className="animate-spin" /> : null}
          {!user ? t("buy.signInToBuy") : buying ? t("buy.creating") : t("buy.buyButton")}
        </button>
      </div>
    </aside>
  );
}

function PickerBlock({
  count,
  heading,
  loading,
  onSearch,
  onSelect,
  onShowAll,
  placeholder,
  rows,
  search,
  selected,
  showAll,
  showAllLabel
}: {
  count: number;
  heading: string;
  loading: boolean;
  onSearch: (value: string) => void;
  onSelect: (value: string) => void;
  onShowAll: () => void;
  placeholder: string;
  rows: PickerRow[];
  search: string;
  selected: string;
  showAll: boolean;
  showAllLabel: string;
}) {
  const {t} = useTranslation();
  return (
    <div className="mt-5">
      <h2 className="text-sm font-semibold text-slate-950">{heading}</h2>
      <label className="relative mt-3 block">
        <Search className="pointer-events-none absolute left-3 top-2.5 text-neutral-400" size={15} />
        <input className="field pl-9" value={search} onChange={(event) => onSearch(event.target.value)} placeholder={placeholder} />
      </label>
      <div className="mt-2 grid gap-1.5">
        {loading ? (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-neutral-500">{t("common.loading")}</div>
        ) : rows.length ? rows.map((row) => (
          <button
            className={`flex items-center gap-3 rounded-xl border px-3 py-2 text-left transition ${
              selected === row.code ? "border-blue-300 bg-blue-50 text-slate-950 shadow-sm" : "border-transparent bg-white hover:border-slate-200 hover:bg-slate-50"
            }`}
            key={row.code}
            onClick={() => onSelect(row.code)}
            type="button"
          >
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-slate-100 text-xs font-semibold text-slate-700">{row.badge}</span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-semibold">{row.name}</span>
              <span className="block text-xs text-neutral-500">{row.count.toLocaleString()} {t("buy.availableShort")}</span>
            </span>
            <span className="text-xs font-semibold text-accent">{row.price ? t("buy.fromPrice", {price: money(row.price)}) : row.code}</span>
          </button>
        )) : (
          <EmptyState title={t("common.noRowsFound")} />
        )}
      </div>
      {!showAll && count > rows.length && (
        <button className="btn btn-secondary mt-3 w-full" onClick={onShowAll} type="button">
          {showAllLabel}
        </button>
      )}
    </div>
  );
}

function MarketplaceHomeContent({
  canBuy,
  countryName,
  hasFunds,
  hasPrice,
  onBuy,
  price,
  serviceName,
  user
}: {
  canBuy: boolean;
  countryName: string;
  hasFunds: boolean;
  hasPrice: boolean;
  onBuy: () => void;
  price?: Price;
  serviceName: string;
  user: User | null;
}) {
  const {t} = useTranslation();
  return (
    <>
      <section className="rounded-3xl border border-blue-100 bg-[linear-gradient(135deg,#ffffff_0%,#eef5ff_58%,#f7fbff_100%)] p-6 shadow-sm md:p-9">
        <div className="max-w-3xl">
          <p className="text-sm font-semibold text-blue-700">{t("buy.marketplaceEyebrow")}</p>
          <h1 className="mt-4 text-4xl font-semibold tracking-normal text-slate-950 md:text-6xl">{t("buy.marketplaceTitle")}</h1>
          <p className="mt-5 text-base leading-7 text-slate-700">{t("buy.marketplaceSubtitle")}</p>
          <div className="mt-7 flex flex-wrap gap-3">
            <button className="btn btn-primary px-5" disabled={user ? !canBuy : !hasPrice} onClick={onBuy}>
              {!user ? t("buy.signInToBuy") : t("buy.buyButton")}
              <ArrowRight size={16} />
            </button>
            <Link className="btn btn-secondary" href="/api-docs">{t("landing.apiDocs")}</Link>
          </div>
          {user && hasPrice && !hasFunds && <div className="mt-5"><Alert type="error">{t("buy.insufficient")}</Alert></div>}
        </div>
      </section>
      <section className="grid gap-5 lg:grid-cols-[1fr_300px]">
        <SelectedOfferCard countryName={countryName} price={price} serviceName={serviceName} />
        <div className="grid gap-3">
          <InfoCard icon={<ShieldCheck size={18} />} label={t("buy.refundPolicy")} value={t("buy.refundPolicyValue")} />
          <InfoCard icon={<Wallet size={18} />} label={t("buy.marketplaceMode")} value={t("buy.marketplaceModeValue")} />
          <InfoCard icon={<Code2 size={18} />} label={t("buy.developerHint")} value={t("buy.developerHintValue")} />
        </div>
      </section>
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-lg font-semibold">{t("buy.howItWorks")}</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-4">
          {[t("buy.stepChoose"), t("buy.stepBuy"), t("buy.stepReceive"), t("buy.stepFinish")].map((step, index) => (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3" key={step}>
              <span className="grid h-7 w-7 place-items-center rounded-full bg-white text-xs font-semibold text-accent ring-1 ring-slate-200">{index + 1}</span>
              <p className="mt-3 text-sm font-medium text-slate-900">{step}</p>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

function SelectedOfferCard({countryName, price, serviceName}: {countryName: string; price?: Price; serviceName: string}) {
  const {t} = useTranslation();
  const rows = [
    [t("common.service"), serviceName],
    [t("common.country"), countryName],
    [t("common.operator"), price?.operator || t("common.any")],
    [t("common.price"), price ? money(price.final_price) : "-"],
    [t("common.availability"), price?.available_count ?? "-"],
    [t("common.deliveryRate"), price ? percent(price.delivery_rate) : "-"]
  ];
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold">{t("buy.offerTitle")}</h2>
      <p className="mt-1 text-sm leading-6 text-neutral-600">{t("buy.offerDesc")}</p>
      <div className="mt-5 grid gap-3 md:grid-cols-2">
        {rows.map(([label, value]) => (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3" key={label}>
            <p className="text-xs uppercase text-neutral-500">{label}</p>
            <p className="mt-1 font-semibold text-slate-950">{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function OrderStatusPanel({busy, onAction, onBackToMarket, order}: {busy: boolean; onAction: (kind: "cancel" | "finish") => void; onBackToMarket: () => void; order: Order}) {
  const {t} = useTranslation();
  const active = ["created", "reserved", "waiting_sms", "sms_received"].includes(order.status);
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm md:p-8">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-sm font-semibold text-blue-700">{t("buy.orderCreated")}</p>
          <h1 className="mt-2 text-3xl font-semibold text-slate-950">{t("orderDetail.title")}</h1>
          <p className="mt-2 text-sm text-neutral-600">{t("buy.orderStatusDesc")}</p>
        </div>
        <StatusBadge status={order.status} />
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
          <p className="text-sm text-neutral-500">{t("orderDetail.phoneNumber")}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <p className="text-2xl font-semibold">{order.phone_number || "-"}</p>
            <CopyButton value={order.phone_number} />
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
          <p className="text-sm text-neutral-500">{t("common.smsCode")}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <p className="text-2xl font-semibold">{order.sms_code || "-"}</p>
            <CopyButton value={order.sms_code} />
          </div>
          {order.sms_text && <p className="mt-3 rounded-lg bg-white p-3 text-sm">{order.sms_text}</p>}
        </div>
      </div>
      <div className="mt-5 grid gap-3 text-sm md:grid-cols-3">
        <SummaryBox label={t("common.service")} value={order.service_code} />
        <SummaryBox label={t("common.country")} value={order.country_iso2} />
        <SummaryBox label={t("common.price")} value={money(order.price)} />
        <SummaryBox label={t("common.countdown")} value={active ? countdown(order.expires_at) : "-"} />
        <SummaryBox label={t("common.order")} value={order.public_id} />
        <SummaryBox label={t("common.status")} value={<StatusBadge status={order.status} />} />
      </div>
      <div className="mt-6 flex flex-wrap gap-3">
        <button className="btn btn-secondary" disabled={busy || !active} onClick={() => onAction("cancel")}>{t("orders.cancel")}</button>
        <button className="btn btn-primary" disabled={busy || order.status !== "sms_received"} onClick={() => onAction("finish")}>{t("orders.finish")}</button>
        <Link className="btn btn-secondary" href={`/orders/${order.public_id}`}>{t("orders.view")}</Link>
        <button className="btn btn-secondary" onClick={onBackToMarket}>{t("buy.backToMarketplace")}</button>
      </div>
    </section>
  );
}

function AuthGateModal({locale, onClose, onLocaleChange, onSuccess}: {locale: Locale; onClose: () => void; onLocaleChange: (locale: Locale) => void; onSuccess: (user: User) => void}) {
  const {t} = useTranslation();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("user@smsbridge.local");
  const [password, setPassword] = useState("change-me");
  const [selectedLocale, setSelectedLocale] = useState<Locale>(locale);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (mode === "register") onLocaleChange(selectedLocale);
      const session = await auth(mode === "login" ? "/auth/login" : "/auth/register", mode === "login" ? {email, password} : {email, password, locale: selectedLocale});
      onSuccess(session.user as User);
    } catch (err) {
      setError(err instanceof Error ? err.message : mode === "login" ? t("auth.loginFailed") : t("auth.registrationFailed"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open>
      <DialogContent>
        <div className="flex items-start justify-between gap-4">
          <DialogHeader>
            <DialogTitle>{t("buy.authGateTitle")}</DialogTitle>
            <DialogDescription>{t("buy.authGateDesc")}</DialogDescription>
          </DialogHeader>
          <Button onClick={onClose} size="sm" type="button" variant="secondary">×</Button>
        </div>
        <Tabs className="mt-5">
          <TabsList className="grid grid-cols-2">
            <TabsTrigger active={mode === "login"} onClick={() => setMode("login")} type="button">{t("nav.login")}</TabsTrigger>
            <TabsTrigger active={mode === "register"} onClick={() => setMode("register")} type="button">{t("nav.register")}</TabsTrigger>
          </TabsList>
        </Tabs>
        <form className="mt-5 grid gap-3" onSubmit={submit}>
          <Input value={email} onChange={(event) => setEmail(event.target.value)} placeholder={t("common.email")} />
          <Input value={password} onChange={(event) => setPassword(event.target.value)} placeholder={mode === "login" ? t("auth.password") : t("auth.passwordHint")} type="password" />
          {mode === "register" && (
            <select className="field" value={selectedLocale} onChange={(event) => setSelectedLocale(event.target.value as Locale)}>
              <option value="en">{t("common.english")}</option>
              <option value="ru">{t("common.russian")}</option>
            </select>
          )}
          {error && <Alert type="error">{error}</Alert>}
          <Button disabled={loading} type="submit">
            {loading ? <Loader2 size={16} className="animate-spin" /> : null}
            {mode === "login" ? t("auth.signIn") : t("auth.signUp")}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function SummaryRow({label, strong = false, value}: {label: string; strong?: boolean; value: React.ReactNode}) {
  return (
    <div className="mt-3 flex items-center justify-between gap-3">
      <span className="text-sm text-neutral-500">{label}</span>
      <span className={strong ? "text-lg font-semibold" : "text-sm font-semibold"}>{value}</span>
    </div>
  );
}

function SummaryBox({label, value}: {label: string; value: React.ReactNode}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs uppercase text-neutral-500">{label}</p>
      <div className="mt-1 break-all font-semibold text-slate-950">{value}</div>
    </div>
  );
}

function InfoCard({icon, label, value}: {icon: React.ReactNode; label: string; value: string}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-blue-50 text-blue-700">{icon}</span>
        <div>
          <p className="text-sm text-neutral-500">{label}</p>
          <p className="mt-1 font-semibold text-slate-950">{value}</p>
        </div>
      </div>
    </div>
  );
}

function createOrderIdempotencyKey() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return `order-${crypto.randomUUID()}`;
  return `order-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function saveSelection(selection: Selection) {
  if (typeof window === "undefined") return;
  localStorage.setItem(selectionStorageKey, JSON.stringify(selection));
}

function restoreSelection(): Selection | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(selectionStorageKey);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<Selection>;
    if (!parsed.service || !parsed.country) return null;
    return {service: parsed.service, country: parsed.country, operator: parsed.operator || ""};
  } catch {
    return null;
  }
}

function filterRows(rows: PickerRow[], query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return rows;
  return rows.filter((row) => row.name.toLowerCase().includes(normalized) || row.code.toLowerCase().includes(normalized));
}

function sumAvailable(rows: Price[]) {
  return rows.reduce((sum, row) => sum + Math.max(0, Number(row.available_count || 0)), 0);
}

function minPrice(rows: Price[]) {
  const values = rows.map((row) => Number(row.final_price)).filter((value) => Number.isFinite(value) && value > 0);
  if (!values.length) return null;
  return Math.min(...values).toFixed(4);
}

function nameForService(services: Service[], code: string, locale: Locale) {
  const item = services.find((service) => service.code === code);
  return item ? (locale === "ru" ? item.name_ru : item.name_en) : code;
}

function nameForCountry(countries: Country[], iso2: string, locale: Locale) {
  const item = countries.find((country) => country.iso2 === iso2);
  return item ? (locale === "ru" ? item.name_ru : item.name_en) : iso2;
}

function serviceBadge(code: string) {
  const map: Record<string, string> = {
    amazon: "AM",
    facebook: "FB",
    google: "G",
    openai: "AI",
    telegram: "TG",
    whatsapp: "WA"
  };
  return map[code] || code.slice(0, 2).toUpperCase();
}

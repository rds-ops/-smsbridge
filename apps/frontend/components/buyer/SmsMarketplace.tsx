"use client";

import {useEffect, useMemo, useRef, useState} from "react";
import Link from "next/link";
import {ArrowDown, ArrowRight, CheckCircle2, Code2, Loader2, MapPin, Radio, RotateCcw, Search, ShieldCheck, Sparkles, Wallet} from "lucide-react";
import {AuthModal} from "@/components/shared/auth-modal";
import {Alert, CopyButton, EmptyState, StatusBadge, Toast} from "@/components/shared/ui";
import {cancelOrder, createOrder, finishOrder, getBalance, getCountries, getOrder, getPrices, getServices} from "@/lib/client/api";
import {currentUser, getToken} from "@/lib/shared/api";
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
  {code: "openai", name_en: "OpenAI", name_ru: "OpenAI", category: "developer", is_active: true},
  {code: "instagram", name_en: "Instagram", name_ru: "Instagram", category: "social", is_active: true},
  {code: "tiktok", name_en: "TikTok", name_ru: "TikTok", category: "social", is_active: true},
  {code: "discord", name_en: "Discord", name_ru: "Discord", category: "developer", is_active: true},
  {code: "apple", name_en: "Apple", name_ru: "Apple", category: "identity", is_active: true},
  {code: "microsoft", name_en: "Microsoft", name_ru: "Microsoft", category: "identity", is_active: true},
  {code: "steam", name_en: "Steam", name_ru: "Steam", category: "gaming", is_active: true},
  {code: "uber", name_en: "Uber", name_ru: "Uber", category: "mobility", is_active: true},
  {code: "binance", name_en: "Binance", name_ru: "Binance", category: "finance", is_active: true},
  {code: "netflix", name_en: "Netflix", name_ru: "Netflix", category: "media", is_active: true}
];

const previewCountries: Country[] = [
  {iso2: "ID", name_en: "Indonesia", name_ru: "Индонезия", is_active: true},
  {iso2: "IN", name_en: "India", name_ru: "Индия", is_active: true},
  {iso2: "BR", name_en: "Brazil", name_ru: "Бразилия", is_active: true},
  {iso2: "KZ", name_en: "Kazakhstan", name_ru: "Казахстан", is_active: true},
  {iso2: "PH", name_en: "Philippines", name_ru: "Филиппины", is_active: true},
  {iso2: "UZ", name_en: "Uzbekistan", name_ru: "Узбекистан", is_active: true},
  {iso2: "MX", name_en: "Mexico", name_ru: "Мексика", is_active: true},
  {iso2: "US", name_en: "United States", name_ru: "США", is_active: true},
  {iso2: "CA", name_en: "Canada", name_ru: "Канада", is_active: true},
  {iso2: "DE", name_en: "Germany", name_ru: "Германия", is_active: true},
  {iso2: "FR", name_en: "France", name_ru: "Франция", is_active: true},
  {iso2: "GB", name_en: "United Kingdom", name_ru: "Великобритания", is_active: true},
  {iso2: "TR", name_en: "Turkey", name_ru: "Турция", is_active: true},
  {iso2: "VN", name_en: "Vietnam", name_ru: "Вьетнам", is_active: true},
  {iso2: "TH", name_en: "Thailand", name_ru: "Таиланд", is_active: true},
  {iso2: "MY", name_en: "Malaysia", name_ru: "Малайзия", is_active: true}
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

type FunnelStep = "service" | "country" | "offer" | "review";

export function SmsMarketplace({children}: {children?: React.ReactNode}) {
  const {t, locale} = useTranslation();
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
  const [openStep, setOpenStep] = useState<FunnelStep>("service");
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

  const hasPrice = Boolean(selected);
  const availableBalance = Number(balance?.balance || 0);
  const requiredPrice = Number(selected?.final_price || 0);
  const hasFunds = Boolean(!user || (hasPrice && availableBalance >= requiredPrice));
  const canBuy = Boolean(hasPrice && hasFunds && !buying && !loading);
  const filteredServices = filterRows(serviceRows, serviceSearch);
  const filteredCountries = filterRows(countryRows, countrySearch);
  const selectedServiceRow = serviceRows.find((row) => row.code === service) || serviceRows[0];
  const selectedCountryRow = countryRows.find((row) => row.code === country) || countryRows[0];
  const offerOptions = selectedPrices.length ? selectedPrices : selected ? [selected] : [];
  const selectedOfferId = offerId(selected);

  function selectService(code: string) {
    setService(code);
    setServiceSearch("");
    setOpenStep("country");
  }

  function selectCountry(code: string) {
    setCountry(code);
    setCountrySearch("");
    setOpenStep("offer");
  }

  function selectOffer(priceRow: Price) {
    setOperator(priceRow.operator && priceRow.operator !== "any" ? priceRow.operator : "");
    setOpenStep("review");
  }

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
          onOpenStep={setOpenStep}
          onSelectCountry={selectCountry}
          onSelectOffer={selectOffer}
          onSelectService={selectService}
          onServiceSearch={setServiceSearch}
          onShowAllCountries={() => setShowAllCountries(true)}
          onShowAllServices={() => setShowAllServices(true)}
          openStep={openStep}
          operator={operator}
          offerOptions={offerOptions}
          price={selected}
          service={service}
          selectedCountryRow={selectedCountryRow}
          selectedOfferId={selectedOfferId}
          selectedServiceRow={selectedServiceRow}
          serviceRows={showAllServices ? filteredServices : filteredServices.slice(0, visibleLimit)}
          serviceSearch={serviceSearch}
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
              canBuy={canBuy && openStep === "review"}
              hasFunds={hasFunds}
              hasPrice={hasPrice}
              onBuy={buy}
              user={user}
            />
          )}
        </section>
      </div>
      <AuthModal
        initialMode="login"
        onClose={() => setAuthOpen(false)}
        onSuccess={handleAuthSuccess}
        open={authOpen}
      />
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
  onOpenStep,
  onSelectCountry,
  onSelectOffer,
  onSelectService,
  onServiceSearch,
  onShowAllCountries,
  onShowAllServices,
  openStep,
  operator,
  offerOptions,
  price,
  service,
  selectedCountryRow,
  selectedOfferId,
  selectedServiceRow,
  serviceRows,
  serviceSearch,
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
  onOpenStep: (step: FunnelStep) => void;
  onSelectCountry: (value: string) => void;
  onSelectOffer: (price: Price) => void;
  onSelectService: (value: string) => void;
  onServiceSearch: (value: string) => void;
  onShowAllCountries: () => void;
  onShowAllServices: () => void;
  openStep: FunnelStep;
  operator: string;
  offerOptions: Price[];
  price?: Price;
  service: string;
  selectedCountryRow?: PickerRow;
  selectedOfferId: string;
  selectedServiceRow?: PickerRow;
  serviceRows: PickerRow[];
  serviceSearch: string;
  showAllCountries: boolean;
  showAllServices: boolean;
  user: User | null;
}) {
  const {t} = useTranslation();
  return (
    <aside className="rounded-2xl border border-slate-200/80 bg-white/90 p-4 shadow-[0_18px_50px_rgba(15,23,42,0.08)] backdrop-blur transition-all duration-300 lg:sticky lg:top-24 lg:max-h-[calc(100vh-7rem)] lg:overflow-y-auto">
      <div className="rounded-2xl bg-gradient-to-r from-blue-50 via-cyan-50 to-sky-50 px-4 py-3 text-center text-sm font-semibold text-accent ring-1 ring-cyan-100">
        {t("buy.activations")}
      </div>
      <StepPanel active={openStep === "service"} done={openStep !== "service"} number={1} title={t("buy.serviceStepTitle")}>
        {openStep === "service" ? (
          <PickerBlock
            count={filteredServiceCount}
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
        ) : selectedServiceRow ? (
          <SelectedPickerRow onChange={() => onOpenStep("service")} row={selectedServiceRow} />
        ) : null}
      </StepPanel>

      <StepPanel active={openStep === "country"} done={["offer", "review"].includes(openStep)} number={2} title={t("buy.countryStepTitle")}>
        {openStep === "service" ? (
          <p className="rounded-xl border border-dashed border-slate-200 p-3 text-xs text-neutral-500">{t("buy.completePreviousStep")}</p>
        ) : openStep === "country" ? (
          <PickerBlock
            count={filteredCountryCount}
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
        ) : selectedCountryRow ? (
          <SelectedPickerRow onChange={() => onOpenStep("country")} row={selectedCountryRow} />
        ) : (
          <p className="rounded-xl border border-dashed border-slate-200 p-3 text-xs text-neutral-500">{t("buy.completePreviousStep")}</p>
        )}
      </StepPanel>

      <StepPanel active={openStep === "offer"} done={openStep === "review"} number={3} title={t("buy.offerStepTitle")}>
        {["service", "country"].includes(openStep) ? (
          <p className="rounded-xl border border-dashed border-slate-200 p-3 text-xs text-neutral-500">{t("buy.completePreviousStep")}</p>
        ) : openStep === "offer" ? (
          <OfferPicker
            loading={loading}
            onSelect={onSelectOffer}
            options={offerOptions}
            selectedOfferId={selectedOfferId}
          />
        ) : price ? (
          <SelectedOfferRow onChange={() => onOpenStep("offer")} price={price} />
        ) : (
          <p className="rounded-xl border border-dashed border-slate-200 p-3 text-xs text-neutral-500">{t("buy.noPrice")}</p>
        )}
      </StepPanel>

      <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-cyan-200 hover:shadow-lg hover:shadow-cyan-100/60">
        <div className="mb-3 flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-full bg-cyan-50 text-xs font-semibold text-accent ring-1 ring-cyan-100">4</span>
          <h2 className="text-sm font-semibold text-slate-950">{t("buy.reviewStepTitle")}</h2>
        </div>
        <SummaryRow label={t("common.service")} value={selectedServiceRow?.name || service} />
        <SummaryRow label={t("common.country")} value={selectedCountryRow?.name || country} />
        <SummaryRow label={t("common.operator")} value={operator || price?.operator || t("common.any")} />
        <SummaryRow label={t("common.price")} value={hasPrice ? money(price?.final_price) : "-"} strong />
        <SummaryRow label={t("common.availability")} value={price?.available_count ?? "-"} />
        <SummaryRow label={t("common.deliveryRate")} value={price ? percent(price.delivery_rate) : "-"} />
        {user && <SummaryRow label={t("common.availableBalance")} value={money(balance?.balance, balance?.currency)} />}
        <p className="mt-3 rounded-xl bg-slate-50 p-3 text-xs leading-5 text-neutral-600">{t("buy.refundNote")}</p>
        {!hasPrice && <p className="mt-3 text-xs leading-5 text-red-700">{t("buy.noPrice")}</p>}
        {user && hasPrice && !hasFunds && <p className="mt-3 text-xs leading-5 text-red-700">{t("buy.insufficient")}</p>}
        {!user && <p className="mt-3 text-xs leading-5 text-neutral-500">{t("buy.previewNotice")}</p>}
        <button className="btn btn-primary mt-4 w-full" disabled={user ? !canBuy : !hasPrice || openStep !== "review"} onClick={onBuy}>
          {buying ? <Loader2 size={16} className="animate-spin" /> : null}
          {!user ? t("buy.signInToBuy") : buying ? t("buy.creating") : t("buy.buyButton")}
        </button>
      </div>
    </aside>
  );
}

function StepPanel({active, children, done, number, title}: {active: boolean; children: React.ReactNode; done: boolean; number: number; title: string}) {
  return (
    <section className={`mt-4 rounded-2xl border p-3 transition-all duration-200 ${
      active
        ? "border-cyan-200 bg-white shadow-md shadow-cyan-100/50 ring-1 ring-cyan-100"
        : done
          ? "border-slate-200 bg-slate-50/80"
          : "border-slate-200 bg-white"
    }`}>
      <div className="mb-3 flex items-center gap-2">
        <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-semibold ${
          done ? "bg-cyan-50 text-accent ring-1 ring-cyan-100" : active ? "bg-accent text-white" : "bg-slate-100 text-slate-600"
        }`}>{done ? <CheckCircle2 size={14} /> : number}</span>
        <h2 className="min-w-0 truncate text-sm font-semibold text-slate-950">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function PickerBlock({
  count,
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
    <div>
      <label className="relative block">
        <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" size={16} />
        <input className="field min-h-10 pl-10" value={search} onChange={(event) => onSearch(event.target.value)} placeholder={placeholder} />
      </label>
      <div className="mt-2 grid gap-1.5">
        {loading ? (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-neutral-500">{t("common.loading")}</div>
        ) : rows.length ? rows.map((row) => (
          <button
            className={`group flex min-h-[3.35rem] items-center gap-3 rounded-xl border px-3 py-2 text-left transition-all duration-200 ${
              selected === row.code
                ? "border-cyan-200 bg-gradient-to-r from-blue-50 via-cyan-50 to-white text-slate-950 shadow-md shadow-cyan-100/70 ring-1 ring-cyan-100 dark:from-slate-800 dark:via-cyan-950/40 dark:to-slate-900"
                : "border-transparent bg-white hover:-translate-y-0.5 hover:border-slate-200 hover:bg-slate-50 hover:shadow-md hover:shadow-slate-200/70"
            }`}
            key={row.code}
            onClick={() => onSelect(row.code)}
            type="button"
          >
            <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg text-xs font-semibold transition-all duration-200 ${
              selected === row.code ? "bg-white text-accent shadow-sm ring-1 ring-cyan-100" : "bg-slate-100 text-slate-700 group-hover:bg-white group-hover:text-accent"
            }`}>{row.badge}</span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-semibold">{row.name}</span>
              <span className="block text-xs text-neutral-500">{row.count.toLocaleString()} {t("buy.availableShort")}</span>
            </span>
            <span className="min-w-[5.5rem] text-right text-xs font-semibold text-accent transition-colors group-hover:text-blue-700">{row.price ? t("buy.fromPrice", {price: money(row.price)}) : row.code}</span>
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

function SelectedPickerRow({onChange, row}: {onChange: () => void; row: PickerRow}) {
  const {t} = useTranslation();
  return (
    <button
      className="group flex min-h-[3.35rem] w-full items-center gap-3 rounded-xl border border-cyan-200 bg-gradient-to-r from-blue-50 via-cyan-50 to-white px-3 py-2 text-left shadow-sm ring-1 ring-cyan-100 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md hover:shadow-cyan-100/70 dark:from-slate-800 dark:via-cyan-950/40 dark:to-slate-900"
      onClick={onChange}
      type="button"
    >
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white text-xs font-semibold text-accent shadow-sm ring-1 ring-cyan-100">{row.badge}</span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold text-slate-950">{row.name}</span>
        <span className="block truncate text-xs text-neutral-500">{row.count.toLocaleString()} {t("buy.availableShort")} · {row.price ? t("buy.fromPrice", {price: money(row.price)}) : row.code}</span>
      </span>
      <span className="shrink-0 rounded-lg border border-cyan-100 bg-white px-2 py-1 text-xs font-semibold text-accent transition-colors group-hover:bg-cyan-50">
        {t("buy.change")}
      </span>
    </button>
  );
}

function OfferPicker({loading, onSelect, options, selectedOfferId}: {loading: boolean; onSelect: (price: Price) => void; options: Price[]; selectedOfferId: string}) {
  const {t} = useTranslation();
  if (loading) return <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-neutral-500">{t("common.loading")}</div>;
  if (!options.length) return <EmptyState title={t("buy.noPrice")} />;
  return (
    <div className="grid gap-2">
      {options.map((option) => {
        const id = offerId(option);
        const selected = id === selectedOfferId;
        return (
          <button
            className={`rounded-xl border p-3 text-left transition-all duration-200 ${
              selected
                ? "border-cyan-200 bg-gradient-to-r from-blue-50 via-cyan-50 to-white shadow-sm ring-1 ring-cyan-100 dark:from-slate-800 dark:via-cyan-950/40 dark:to-slate-900"
                : "border-slate-200 bg-white hover:-translate-y-0.5 hover:border-cyan-200 hover:bg-slate-50 hover:shadow-md"
            }`}
            key={id}
            onClick={() => onSelect(option)}
            type="button"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="flex min-w-0 items-center gap-2">
                <Radio size={15} className="shrink-0 text-accent" />
                <span className="truncate text-sm font-semibold text-slate-950">{option.operator || t("buy.anyOperator")}</span>
              </span>
              <span className="shrink-0 text-sm font-semibold text-accent">{money(option.final_price)}</span>
            </div>
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-neutral-500">
              <span>{option.available_count} {t("buy.availableShort")}</span>
              <span>{percent(option.delivery_rate)}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

function SelectedOfferRow({onChange, price}: {onChange: () => void; price: Price}) {
  const {t} = useTranslation();
  return (
    <button
      className="group w-full rounded-xl border border-cyan-200 bg-gradient-to-r from-blue-50 via-cyan-50 to-white p-3 text-left shadow-sm ring-1 ring-cyan-100 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md hover:shadow-cyan-100/70 dark:from-slate-800 dark:via-cyan-950/40 dark:to-slate-900"
      onClick={onChange}
      type="button"
    >
      <div className="flex items-center justify-between gap-3">
        <span className="flex min-w-0 items-center gap-2">
          <Radio size={15} className="shrink-0 text-accent" />
          <span className="truncate text-sm font-semibold text-slate-950">{price.operator || t("buy.anyOperator")}</span>
        </span>
        <span className="shrink-0 rounded-lg border border-cyan-100 bg-white px-2 py-1 text-xs font-semibold text-accent">{t("buy.change")}</span>
      </div>
      <p className="mt-2 text-xs text-neutral-500">{money(price.final_price)} · {price.available_count} {t("buy.availableShort")} · {percent(price.delivery_rate)}</p>
    </button>
  );
}

function MarketplaceHomeContent({
  canBuy,
  hasFunds,
  hasPrice,
  onBuy,
  user
}: {
  canBuy: boolean;
  hasFunds: boolean;
  hasPrice: boolean;
  onBuy: () => void;
  user: User | null;
}) {
  const {t} = useTranslation();
  return (
    <>
      <section className="relative overflow-hidden rounded-3xl border border-blue-100/80 bg-[linear-gradient(135deg,rgba(255,255,255,0.96)_0%,rgba(239,246,255,0.9)_46%,rgba(236,254,255,0.72)_100%)] p-6 shadow-[0_22px_70px_rgba(14,116,144,0.12)] backdrop-blur transition-all duration-300 dark:border-cyan-900/40 dark:bg-[linear-gradient(135deg,rgba(15,23,42,0.96)_0%,rgba(8,47,73,0.88)_52%,rgba(2,6,23,0.96)_100%)] dark:shadow-cyan-950/30 md:p-9">
        <div className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-cyan-200/30 blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 right-10 h-40 w-40 rounded-full bg-blue-300/20 blur-2xl" />
        <div className="relative max-w-3xl">
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
      <PrinciplesRow />
      <PurchaseRoadmap />
    </>
  );
}

function PrinciplesRow() {
  const {t} = useTranslation();
  const items = [
    {icon: <Sparkles size={16} />, label: t("buy.principleFast")},
    {icon: <RotateCcw size={16} />, label: t("buy.principleRefund")},
    {icon: <Code2 size={16} />, label: t("buy.principleApi")},
    {icon: <Wallet size={16} />, label: t("buy.principleSupplier")},
    {icon: <ShieldCheck size={16} />, label: t("buy.principleCompliance")}
  ];
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap gap-2">
        {items.map((item) => (
          <div className="flex min-h-11 flex-1 basis-[10rem] items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-950 transition-all duration-200 hover:-translate-y-0.5 hover:border-cyan-200 hover:bg-white hover:shadow-md hover:shadow-cyan-100/50" key={item.label}>
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-cyan-50 text-accent ring-1 ring-cyan-100">{item.icon}</span>
            <span className="min-w-0 truncate">{item.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function PurchaseRoadmap() {
  const {t} = useTranslation();
  const steps = [
    {icon: <Sparkles size={17} />, title: t("buy.roadmapService"), desc: t("buy.roadmapServiceDesc")},
    {icon: <MapPin size={17} />, title: t("buy.roadmapCountry"), desc: t("buy.roadmapCountryDesc")},
    {icon: <Radio size={17} />, title: t("buy.roadmapOperator"), desc: t("buy.roadmapOperatorDesc")},
    {icon: <Wallet size={17} />, title: t("buy.roadmapBuy"), desc: t("buy.roadmapBuyDesc")},
    {icon: <Loader2 size={17} />, title: t("buy.roadmapWait"), desc: t("buy.roadmapWaitDesc")},
    {icon: <CheckCircle2 size={17} />, title: t("buy.roadmapFinish"), desc: t("buy.roadmapFinishDesc")}
  ];
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-blue-700">{t("buy.roadmapEyebrow")}</p>
          <h2 className="mt-1 text-xl font-semibold text-slate-950">{t("buy.roadmapTitle")}</h2>
        </div>
        <p className="max-w-md text-sm leading-6 text-neutral-600">{t("buy.roadmapDesc")}</p>
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-3">
        {steps.map((step, index) => (
          <RoadmapStep desc={step.desc} icon={step.icon} index={index} key={step.title} title={step.title} />
        ))}
      </div>
    </section>
  );
}

function RoadmapStep({desc, icon, index, title}: {desc: string; icon: React.ReactNode; index: number; title: string}) {
  const showRightArrow = index !== 2 && index !== 5;
  const showDownArrow = index === 2;
  return (
    <div className="relative rounded-2xl border border-slate-200 bg-slate-50 p-4 transition-all duration-200 hover:-translate-y-0.5 hover:border-cyan-200 hover:bg-white hover:shadow-md hover:shadow-cyan-100/50">
      <div className="flex items-start gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white text-accent shadow-sm ring-1 ring-slate-200">{icon}</span>
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase text-neutral-500">{String(index + 1).padStart(2, "0")}</p>
          <h3 className="mt-1 text-sm font-semibold text-slate-950">{title}</h3>
          <p className="mt-2 text-xs leading-5 text-neutral-600">{desc}</p>
        </div>
      </div>
      {showRightArrow && <ArrowRight className="absolute -right-4 top-1/2 hidden -translate-y-1/2 text-cyan-500 md:block" size={20} />}
      {showDownArrow && <ArrowDown className="absolute -bottom-5 left-1/2 hidden -translate-x-1/2 text-cyan-500 md:block" size={20} />}
    </div>
  );
}

function OrderStatusPanel({busy, onAction, onBackToMarket, order}: {busy: boolean; onAction: (kind: "cancel" | "finish") => void; onBackToMarket: () => void; order: Order}) {
  const {t} = useTranslation();
  const active = ["created", "reserved", "waiting_sms", "sms_received"].includes(order.status);
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)] transition-all duration-200 md:p-8">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-sm font-semibold text-blue-700">{t("buy.orderCreated")}</p>
          <h1 className="mt-2 text-3xl font-semibold text-slate-950">{t("orderDetail.title")}</h1>
          <p className="mt-2 text-sm text-neutral-600">{t("buy.orderStatusDesc")}</p>
        </div>
        <StatusBadge status={order.status} />
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5 transition-all duration-200 hover:border-cyan-200 hover:bg-white hover:shadow-md hover:shadow-cyan-100/50">
          <p className="text-sm text-neutral-500">{t("orderDetail.phoneNumber")}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <p className="text-2xl font-semibold">{order.phone_number || "-"}</p>
            <CopyButton value={order.phone_number} />
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5 transition-all duration-200 hover:border-cyan-200 hover:bg-white hover:shadow-md hover:shadow-cyan-100/50">
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
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 transition-all duration-200 hover:border-cyan-200 hover:bg-white">
      <p className="text-xs uppercase text-neutral-500">{label}</p>
      <div className="mt-1 break-all font-semibold text-slate-950">{value}</div>
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

function offerId(price?: Price) {
  return price?.operator || "any";
}

function serviceBadge(code: string) {
  const map: Record<string, string> = {
    amazon: "AM",
    apple: "AP",
    binance: "BN",
    discord: "DC",
    facebook: "FB",
    google: "G",
    instagram: "IG",
    microsoft: "MS",
    netflix: "NF",
    openai: "AI",
    steam: "ST",
    tiktok: "TT",
    telegram: "TG",
    uber: "UB",
    whatsapp: "WA"
  };
  return map[code] || code.slice(0, 2).toUpperCase();
}

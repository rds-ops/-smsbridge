"use client";

import {useEffect, useMemo, useRef, useState} from "react";
import Link from "next/link";
import {ArrowDown, ArrowLeft, ArrowRight, CheckCircle2, Code2, Loader2, Radio, RotateCcw, Search, Sparkles, Wallet} from "lucide-react";
import {AuthModal} from "@/components/shared/auth-modal";
import {Alert, CopyButton, EmptyState, StatusBadge, Toast} from "@/components/shared/ui";
import {cancelOrder, createOrder, finishOrder, getBalance, getCountries, getOrder, getPrices, getServices} from "@/lib/client/api";
import {currentUser, getToken} from "@/lib/shared/api";
import {countdown, money, percent} from "@/lib/shared/format";
import type {Country, Order, Price, Service, User, Wallet as WalletType} from "@/lib/shared/types";
import {useTranslation} from "@/lib/i18n";
import type {Locale} from "@/lib/i18n";

const selectionStorageKey = "smsbridge_marketplace_selection_v2";
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
  const [service, setService] = useState("");
  const [country, setCountry] = useState("");
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
      if (service && serviceRows.length && !serviceRows.some((item) => item.code === service)) setService("");
      if (country && countryRows.length && !countryRows.some((item) => item.iso2 === country)) setCountry("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("buy.loadFailed"));
    } finally {
      setLoading(false);
    }
  }

  const serviceRows = useMemo(() => services.map((item) => {
    const rows = prices.filter((price) => price.service_code === item.code && (!country || price.country_iso2 === country));
    return {
      code: item.code,
      name: locale === "ru" ? item.name_ru : item.name_en,
      badge: serviceBadge(item.code),
      count: sumAvailable(rows),
      price: minPrice(rows)
    };
  }), [country, locale, prices, services]);

  const countryRows = useMemo(() => countries.map((item) => {
    const rows = prices.filter((price) => price.country_iso2 === item.iso2 && (!service || price.service_code === service));
    return {
      code: item.iso2,
      name: locale === "ru" ? item.name_ru : item.name_en,
      badge: item.iso2,
      count: sumAvailable(rows),
      price: minPrice(rows)
    };
  }), [countries, locale, prices, service]);

  const selectedPrices = useMemo(() => {
    if (!service || !country) return [];
    return prices.filter((price) => price.service_code === service && price.country_iso2 === country);
  }, [country, prices, service]);
  const selected = useMemo(() => {
    const requestedOperator = operator.trim().toLowerCase();
    if (requestedOperator) {
      const exact = selectedPrices.find((price) => String(price.operator || "").toLowerCase() === requestedOperator);
      if (exact) return exact;
    }
    return selectedPrices.find((price) => !price.operator || price.operator === "any") || selectedPrices[0];
  }, [operator, selectedPrices]);

  const hasRequiredSelection = Boolean(service && country);
  const hasPrice = Boolean(hasRequiredSelection && selected);
  const availableBalance = Number(balance?.balance || 0);
  const requiredPrice = Number(selected?.final_price || 0);
  const hasFunds = Boolean(!user || (hasPrice && availableBalance >= requiredPrice));
  const canBuy = Boolean(hasRequiredSelection && hasPrice && hasFunds && !buying && !loading);
  const filteredServices = filterRows(serviceRows, serviceSearch);
  const filteredCountries = filterRows(countryRows, countrySearch);
  const selectedServiceRow = serviceRows.find((row) => row.code === service);
  const selectedCountryRow = countryRows.find((row) => row.code === country);
  const offerOptions = selectedPrices.length ? selectedPrices : selected ? [selected] : [];
  const selectedOfferId = offerId(selected);

  function selectService(code: string) {
    setService(code);
    setOperator("");
    setServiceSearch("");
    setOpenStep(country ? "offer" : "country");
  }

  function selectCountry(code: string) {
    setCountry(code);
    setOperator("");
    setCountrySearch("");
    setOpenStep(service ? "offer" : "service");
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
      <div className="mx-auto grid max-w-7xl gap-4 px-4 py-4 lg:grid-cols-[320px_minmax(0,1fr)] lg:px-6 lg:py-5">
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
          hasRequiredSelection={hasRequiredSelection}
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
        <section className="grid gap-4">
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
  hasRequiredSelection,
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
  hasRequiredSelection: boolean;
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
    <aside className="rounded-2xl border border-slate-200/80 bg-white/90 p-3 shadow-[0_18px_50px_rgba(15,23,42,0.08)] backdrop-blur transition-all duration-300 lg:sticky lg:top-24 lg:max-h-[calc(100vh-7rem)] lg:overflow-y-auto">
      <StepPanel active={openStep === "service" || !selectedServiceRow} done={Boolean(selectedServiceRow && openStep !== "service")} number={1} title={t("buy.serviceStepTitle")}>
        {openStep === "service" || !selectedServiceRow ? (
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

      <StepPanel active={openStep === "country" || !selectedCountryRow} done={Boolean(selectedCountryRow && !["country"].includes(openStep))} number={2} title={t("buy.countryStepTitle")}>
        {openStep === "country" || !selectedCountryRow ? (
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
        ) : (
          <SelectedPickerRow onChange={() => onOpenStep("country")} row={selectedCountryRow} />
        )}
      </StepPanel>

      <StepPanel active={openStep === "offer" && hasRequiredSelection} done={openStep === "review"} number={3} title={t("buy.offerStepTitle")}>
        {!hasRequiredSelection ? (
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

      <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-lg hover:shadow-blue-100/50">
        <div className="mb-3 flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-full bg-blue-50 text-xs font-semibold text-accent ring-1 ring-blue-100">4</span>
          <h2 className="text-sm font-semibold text-slate-950">{t("buy.reviewStepTitle")}</h2>
        </div>
        <SummaryRow label={t("common.service")} value={selectedServiceRow?.name || "-"} />
        <SummaryRow label={t("common.country")} value={selectedCountryRow?.name || "-"} />
        <SummaryRow label={t("common.operator")} value={operator || price?.operator || t("common.any")} />
        <SummaryRow label={t("common.price")} value={hasPrice ? money(price?.final_price) : "-"} strong />
        <SummaryRow label={t("common.availability")} value={price?.available_count ?? "-"} />
        <SummaryRow label={t("common.deliveryRate")} value={price ? percent(price.delivery_rate) : "-"} />
        {user && <SummaryRow label={t("common.availableBalance")} value={money(balance?.balance, balance?.currency)} />}
        <p className="mt-3 rounded-xl bg-slate-50 p-3 text-xs leading-5 text-neutral-600">{t("buy.refundNote")}</p>
        {!hasPrice && <p className="mt-3 text-xs leading-5 text-red-700">{t("buy.noPrice")}</p>}
        {user && hasPrice && !hasFunds && <p className="mt-3 text-xs leading-5 text-red-700">{t("buy.insufficient")}</p>}
        {!user && <p className="mt-3 text-xs leading-5 text-neutral-500">{t("buy.previewNotice")}</p>}
        <button className="btn btn-primary mt-4 w-full" disabled={user ? !canBuy || openStep !== "review" : !hasRequiredSelection || !hasPrice || openStep !== "review"} onClick={onBuy}>
          {buying ? <Loader2 size={16} className="animate-spin" /> : null}
          {!user ? t("buy.signInToBuy") : buying ? t("buy.creating") : t("buy.buyButton")}
        </button>
      </div>
    </aside>
  );
}

function StepPanel({active, children, done, number, title}: {active: boolean; children: React.ReactNode; done: boolean; number: number; title: string}) {
  return (
    <section className={`mt-3 rounded-2xl border p-3 transition-all duration-200 first:mt-0 ${
      active
        ? "border-blue-200 bg-white shadow-md shadow-blue-100/50 ring-1 ring-blue-100"
        : done
          ? "border-slate-200 bg-slate-50/80"
          : "border-slate-200 bg-white"
    }`}>
      <div className="mb-3 flex items-center gap-2">
        <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-semibold ${
          done ? "bg-blue-50 text-accent ring-1 ring-blue-100" : active ? "bg-accent text-white" : "bg-slate-100 text-slate-600"
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
        <span className="pointer-events-none absolute inset-y-0 left-0 flex w-10 items-center justify-center text-neutral-400">
          <Search size={16} />
        </span>
        <input className="field min-h-10 !pl-11" value={search} onChange={(event) => onSearch(event.target.value)} placeholder={placeholder} />
      </label>
      <div className="mt-2 grid gap-1.5">
        {loading ? (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-neutral-500">{t("common.loading")}</div>
        ) : rows.length ? rows.map((row) => (
          <button
            className={`group flex min-h-[3.35rem] items-center gap-3 rounded-xl border px-3 py-2 text-left transition-all duration-200 ${
              selected === row.code
                ? "border-blue-300 bg-gradient-to-r from-blue-50 via-sky-50 to-white text-slate-950 shadow-sm ring-1 ring-blue-100 dark:from-slate-800 dark:via-blue-950/40 dark:to-slate-900"
                : "border-transparent bg-white hover:-translate-y-0.5 hover:border-slate-200 hover:bg-slate-50 hover:shadow-md hover:shadow-slate-200/70"
            }`}
            key={row.code}
            onClick={() => onSelect(row.code)}
            type="button"
          >
            <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg text-xs font-semibold transition-all duration-200 ${
              selected === row.code ? "bg-white text-accent shadow-sm ring-1 ring-blue-100" : "bg-slate-100 text-slate-700 group-hover:bg-white group-hover:text-accent"
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
      className="group flex min-h-[3.35rem] w-full items-center gap-3 rounded-xl border border-blue-300 bg-gradient-to-r from-blue-50 via-sky-50 to-white px-3 py-2 text-left shadow-sm ring-1 ring-blue-100 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md hover:shadow-blue-100/60 dark:from-slate-800 dark:via-blue-950/40 dark:to-slate-900"
      onClick={onChange}
      type="button"
    >
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white text-xs font-semibold text-accent shadow-sm ring-1 ring-blue-100">{row.badge}</span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold text-slate-950">{row.name}</span>
        <span className="block truncate text-xs text-neutral-500">{row.count.toLocaleString()} {t("buy.availableShort")} · {row.price ? t("buy.fromPrice", {price: money(row.price)}) : row.code}</span>
      </span>
      <span className="shrink-0 rounded-lg border border-blue-100 bg-white px-2 py-1 text-xs font-semibold text-accent transition-colors group-hover:bg-blue-50">
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
                ? "border-blue-300 bg-gradient-to-r from-blue-50 via-sky-50 to-white shadow-sm ring-1 ring-blue-100 dark:from-slate-800 dark:via-blue-950/40 dark:to-slate-900"
                : "border-slate-200 bg-white hover:-translate-y-0.5 hover:border-blue-200 hover:bg-slate-50 hover:shadow-md hover:shadow-blue-100/40"
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
      className="group w-full rounded-xl border border-blue-300 bg-gradient-to-r from-blue-50 via-sky-50 to-white p-3 text-left shadow-sm ring-1 ring-blue-100 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md hover:shadow-blue-100/60 dark:from-slate-800 dark:via-blue-950/40 dark:to-slate-900"
      onClick={onChange}
      type="button"
    >
      <div className="flex items-center justify-between gap-3">
        <span className="flex min-w-0 items-center gap-2">
          <Radio size={15} className="shrink-0 text-accent" />
          <span className="truncate text-sm font-semibold text-slate-950">{price.operator || t("buy.anyOperator")}</span>
        </span>
        <span className="shrink-0 rounded-lg border border-blue-100 bg-white px-2 py-1 text-xs font-semibold text-accent">{t("buy.change")}</span>
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
      <section className="relative overflow-hidden rounded-3xl border border-blue-100/80 bg-[linear-gradient(135deg,rgba(255,255,255,0.97)_0%,rgba(239,246,255,0.9)_54%,rgba(236,254,255,0.70)_100%)] p-4 shadow-[0_16px_44px_rgba(37,99,235,0.10)] backdrop-blur transition-all duration-300 dark:border-cyan-900/40 dark:bg-[linear-gradient(135deg,rgba(15,23,42,0.96)_0%,rgba(8,47,73,0.82)_52%,rgba(2,6,23,0.96)_100%)] dark:shadow-cyan-950/25 md:p-5">
        <div className="pointer-events-none absolute -right-24 -top-28 h-64 w-64 rounded-full bg-blue-300/20 blur-3xl dark:bg-cyan-500/10" />
        <div className="relative max-w-3xl">
          <h1 className="text-3xl font-semibold tracking-normal text-slate-950 md:text-4xl">{t("buy.marketplaceTitle")}</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-700 md:text-base">{t("buy.marketplaceSubtitle")}</p>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button className="btn btn-primary px-4" disabled={user ? !canBuy : !hasPrice} onClick={onBuy} type="button">
              {!user ? t("buy.signInToBuy") : t("buy.buyButton")}
              <ArrowRight size={16} />
            </button>
            <Link className="btn btn-secondary px-4" href="/api-docs">{t("landing.apiDocs")}</Link>
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
    {icon: <Wallet size={16} />, label: t("buy.principleSupplier")}
  ];
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm md:p-5">
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {items.map((item) => (
          <div className="flex min-h-10 items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-950 transition-all duration-200 hover:-translate-y-0.5 hover:border-blue-200 hover:bg-white hover:shadow-md hover:shadow-blue-100/40" key={item.label}>
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-blue-50 text-accent ring-1 ring-blue-100">{item.icon}</span>
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
    {number: 1, title: t("buy.roadmapService")},
    {number: 2, title: t("buy.roadmapCountry")},
    {number: 3, title: t("buy.roadmapOperator")},
    {number: 6, title: t("buy.roadmapFinish")},
    {number: 5, title: t("buy.roadmapWait")},
    {number: 4, title: t("buy.roadmapBuy")}
  ];
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm md:p-5">
      <h2 className="text-base font-semibold text-slate-950">{t("buy.roadmapTitle")}</h2>
      <div className="mt-2 grid gap-2 md:grid-cols-3 md:gap-x-5 md:gap-y-2">
        {steps.map((step, index) => (
          <RoadmapStep index={index} key={`${step.number}-${step.title}`} number={step.number} title={step.title} />
        ))}
      </div>
    </section>
  );
}

function RoadmapStep({index, number, title}: {index: number; number: number; title: string}) {
  const showTopRightArrow = index === 0 || index === 1;
  const showBottomLeftArrow = index === 4 || index === 5;
  const showDownArrow = index === 2;
  return (
    <div className="relative flex min-h-14 items-center gap-2.5 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 transition-all duration-200 hover:-translate-y-0.5 hover:border-blue-200 hover:bg-white hover:shadow-md hover:shadow-blue-100/40">
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white text-sm font-semibold text-accent shadow-sm ring-1 ring-slate-200">{number}</span>
      <h3 className="min-w-0 text-sm font-semibold leading-5 text-slate-950">{title}</h3>
      {showTopRightArrow && <ArrowRight className="absolute -right-7 top-1/2 hidden -translate-y-1/2 text-blue-600 drop-shadow-sm dark:text-cyan-300 md:block" size={34} strokeWidth={1.9} />}
      {showBottomLeftArrow && <ArrowLeft className="absolute -left-7 top-1/2 hidden -translate-y-1/2 text-blue-600 drop-shadow-sm dark:text-cyan-300 md:block" size={34} strokeWidth={1.9} />}
      {showDownArrow && <ArrowDown className="absolute -bottom-6 left-1/2 hidden -translate-x-1/2 text-blue-600 drop-shadow-sm dark:text-cyan-300 md:block" size={34} strokeWidth={1.9} />}
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
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5 transition-all duration-200 hover:border-blue-200 hover:bg-white hover:shadow-md hover:shadow-blue-100/50">
          <p className="text-sm text-neutral-500">{t("orderDetail.phoneNumber")}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <p className="text-2xl font-semibold">{order.phone_number || "-"}</p>
            <CopyButton value={order.phone_number} />
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5 transition-all duration-200 hover:border-blue-200 hover:bg-white hover:shadow-md hover:shadow-blue-100/50">
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
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 transition-all duration-200 hover:border-blue-200 hover:bg-white">
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
    if (!parsed.service && !parsed.country) return null;
    return {service: parsed.service || "", country: parsed.country || "", operator: parsed.operator || ""};
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

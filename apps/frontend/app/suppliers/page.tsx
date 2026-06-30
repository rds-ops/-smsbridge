"use client";

import Link from "next/link";
import {useState} from "react";
import type {FormEvent} from "react";
import {ArrowRight, CheckCircle2, ShieldCheck, Truck, Wallet} from "lucide-react";
import {SmsMarketplace} from "@/components/buyer/SmsMarketplace";
import {Alert, Card, PageHeader, PageShell, Toast} from "@/components/shared/ui";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog";
import {useTranslation} from "@/lib/i18n";
import {submitSupplierApplication} from "@/lib/shared/api";
import type {SupplierApplicationCreate, SupplierApplicationReceived} from "@/lib/shared/types";

const supplierSections = [
  ["inventoryTitle", "inventoryText", Truck],
  ["routingTitle", "routingText", ArrowRight],
  ["rewardsTitle", "rewardsText", Wallet],
  ["qualityTitle", "qualityText", ShieldCheck]
];

const initialApplication: SupplierApplicationCreate = {
  contact_name: "",
  email: "",
  contact_handle: "",
  country_market: "",
  number_type: "real_sim",
  estimated_daily_volume: 0,
  estimated_monthly_volume: 0,
  integration_availability: "needs_discussion",
  inventory_description: "",
  api_url: null,
  equipment_details: null,
  website: null
};

export default function SuppliersPage() {
  const {t} = useTranslation();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<SupplierApplicationCreate>(initialApplication);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<SupplierApplicationReceived | null>(null);

  function update<K extends keyof SupplierApplicationCreate>(key: K, value: SupplierApplicationCreate[K]) {
    setForm((current) => ({...current, [key]: value}));
  }

  function validate() {
    if (!form.contact_name.trim() || !form.email.trim() || !form.contact_handle.trim() || !form.country_market.trim()) {
      return t("suppliersPage.requiredFields");
    }
    if (!form.email.includes("@")) return t("suppliersPage.invalidEmail");
    if (form.estimated_daily_volume < 0 || form.estimated_monthly_volume < 0) return t("suppliersPage.invalidVolume");
    if (form.inventory_description.trim().length < 20) return t("suppliersPage.inventoryTooShort");
    for (const field of ["api_url", "website"] as const) {
      const value = form[field]?.trim();
      if (value && !value.startsWith("http://") && !value.startsWith("https://")) return t("suppliersPage.invalidUrl");
    }
    return "";
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setResult(null);
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }
    setLoading(true);
    try {
      const response = await submitSupplierApplication({
        ...form,
        contact_name: form.contact_name.trim(),
        email: form.email.trim().toLowerCase(),
        contact_handle: form.contact_handle.trim(),
        country_market: form.country_market.trim(),
        inventory_description: form.inventory_description.trim(),
        api_url: form.api_url?.trim() || null,
        equipment_details: form.equipment_details?.trim() || null,
        website: form.website?.trim() || null
      });
      setResult(response);
      setForm(initialApplication);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("suppliersPage.submitFailed"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <SmsMarketplace>
      <Toast type="success" message={result ? t("suppliersPage.submittedToast") : ""} />
      <PageShell>
        <PageHeader
          title={t("suppliersPage.title")}
          description={t("suppliersPage.description")}
          actions={
            <div className="flex flex-wrap gap-2">
              <button className="btn btn-primary" onClick={() => { setResult(null); setOpen(true); }}>
                {t("suppliersPage.apply")}
              </button>
              <Link className="btn btn-secondary" href="/supplier">{t("suppliersPage.openCabinet")}</Link>
            </div>
          }
        />

        <Card className="mt-6 bg-gradient-to-br from-blue-50 via-white to-cyan-50" title={t("suppliersPage.centerTitle")} description={t("suppliersPage.centerText")}>
          <div className="grid gap-4 md:grid-cols-3">
            {["applyStep", "reviewStep", "accessStep"].map((key) => (
              <div className="rounded-xl border border-blue-100 bg-white/80 p-4 shadow-sm" key={key}>
                <CheckCircle2 className="mb-3 text-accent" size={18} />
                <p className="text-sm font-semibold">{t(`suppliersPage.${key}Title`)}</p>
                <p className="mt-2 text-sm leading-6 text-neutral-600">{t(`suppliersPage.${key}Text`)}</p>
              </div>
            ))}
          </div>
        </Card>

        <section className="mt-6 grid gap-4 md:grid-cols-2">
          {supplierSections.map(([titleKey, textKey, Icon]) => (
            <Card key={String(titleKey)} title={t(`suppliersPage.${titleKey}`)}>
              <div className="flex gap-3">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-blue-50 text-accent ring-1 ring-blue-100">
                  <Icon size={18} />
                </span>
                <p className="text-sm leading-7 text-neutral-700">{t(`suppliersPage.${textKey}`)}</p>
              </div>
            </Card>
          ))}
        </section>

        <Card className="mt-6" title={t("suppliersPage.cabinetTitle")} description={t("suppliersPage.cabinetText")}>
          <div className="flex flex-wrap gap-3">
            <button className="btn btn-primary" onClick={() => { setResult(null); setOpen(true); }}>{t("suppliersPage.apply")}</button>
            <Link className="btn btn-secondary" href="/supplier">{t("suppliersPage.openCabinet")}</Link>
            <Link className="btn btn-secondary" href="/abuse">{t("suppliersPage.contactTeam")}</Link>
          </div>
          <p className="mt-4 text-sm leading-7 text-neutral-500">{t("suppliersPage.contactPlaceholder")}</p>
        </Card>

        <Dialog open={open} onOpenChange={setOpen}>
          <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-3xl">
            <DialogHeader>
              <DialogTitle>{t("suppliersPage.applicationTitle")}</DialogTitle>
              <DialogDescription>{t("suppliersPage.applicationDesc")}</DialogDescription>
            </DialogHeader>
            {result ? (
              <Alert type="success">
                <div className="grid gap-2">
                  <strong>{t("suppliersPage.applicationReceived")}</strong>
                  <span>{t("suppliersPage.applicationId", {id: result.public_id})}</span>
                  <span>{t("suppliersPage.noAutoAccess")}</span>
                </div>
              </Alert>
            ) : (
              <form className="grid gap-4" onSubmit={submit}>
                <div className="grid gap-3 md:grid-cols-2">
                  <SupplierField label={t("suppliersPage.contactName")} value={form.contact_name} onChange={(value) => update("contact_name", value)} />
                  <SupplierField label={t("common.email")} value={form.email} onChange={(value) => update("email", value)} type="email" />
                  <SupplierField label={t("suppliersPage.contactHandle")} value={form.contact_handle} onChange={(value) => update("contact_handle", value)} placeholder="@telegram, email or phone" />
                  <SupplierField label={t("suppliersPage.countryMarket")} value={form.country_market} onChange={(value) => update("country_market", value)} />
                  <label className="grid gap-1 text-sm">
                    {t("suppliersPage.numberType")}
                    <select className="field" value={form.number_type} onChange={(event) => update("number_type", event.target.value as SupplierApplicationCreate["number_type"])}>
                      <option value="real_sim">{t("suppliersPage.numberTypeRealSim")}</option>
                      <option value="virtual_numbers">{t("suppliersPage.numberTypeVirtual")}</option>
                      <option value="other">{t("suppliersPage.numberTypeOther")}</option>
                    </select>
                  </label>
                  <label className="grid gap-1 text-sm">
                    {t("suppliersPage.integrationAvailability")}
                    <select className="field" value={form.integration_availability} onChange={(event) => update("integration_availability", event.target.value as SupplierApplicationCreate["integration_availability"])}>
                      <option value="yes">{t("suppliersPage.integrationYes")}</option>
                      <option value="no">{t("suppliersPage.integrationNo")}</option>
                      <option value="needs_discussion">{t("suppliersPage.integrationDiscuss")}</option>
                    </select>
                  </label>
                  <SupplierField
                    label={t("suppliersPage.dailyVolume")}
                    value={String(form.estimated_daily_volume)}
                    onChange={(value) => update("estimated_daily_volume", Math.max(0, Number(value) || 0))}
                    type="number"
                  />
                  <SupplierField
                    label={t("suppliersPage.monthlyVolume")}
                    value={String(form.estimated_monthly_volume)}
                    onChange={(value) => update("estimated_monthly_volume", Math.max(0, Number(value) || 0))}
                    type="number"
                  />
                  <SupplierField label="api_url optional" value={form.api_url || ""} onChange={(value) => update("api_url", value || null)} />
                  <SupplierField label="website optional" value={form.website || ""} onChange={(value) => update("website", value || null)} />
                </div>
                <label className="grid gap-1 text-sm">
                  {t("suppliersPage.inventoryDescription")}
                  <textarea className="field min-h-28" value={form.inventory_description} onChange={(event) => update("inventory_description", event.target.value)} />
                </label>
                <label className="grid gap-1 text-sm">
                  {t("suppliersPage.equipmentDetails")} {t("common.optional")}
                  <textarea className="field min-h-20" value={form.equipment_details || ""} onChange={(event) => update("equipment_details", event.target.value || null)} />
                </label>
                <p className="rounded-xl border border-line bg-panel p-3 text-sm leading-6 text-neutral-600">{t("suppliersPage.safetyNote")}</p>
                {error && <Alert type="error">{error}</Alert>}
                <div className="flex flex-wrap justify-end gap-2">
                  <button className="btn btn-secondary" type="button" onClick={() => setOpen(false)}>{t("common.cancel")}</button>
                  <button className="btn btn-primary" type="submit" disabled={loading}>{loading ? t("common.saving") : t("suppliersPage.submitApplication")}</button>
                </div>
              </form>
            )}
          </DialogContent>
        </Dialog>
      </PageShell>
    </SmsMarketplace>
  );
}

function SupplierField({
  label,
  value,
  onChange,
  type = "text",
  placeholder
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
}) {
  return (
    <label className="grid gap-1 text-sm">
      {label}
      <input className="field" value={value} onChange={(event) => onChange(event.target.value)} type={type} placeholder={placeholder} />
    </label>
  );
}

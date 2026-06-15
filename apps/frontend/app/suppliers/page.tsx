"use client";

import Link from "next/link";
import {ArrowRight, ShieldCheck, Truck, Wallet} from "lucide-react";
import {SmsMarketplace} from "@/components/buyer/SmsMarketplace";
import {Card, PageHeader, PageShell} from "@/components/shared/ui";
import {useTranslation} from "@/lib/i18n";

const supplierSections = [
  ["inventoryTitle", "inventoryText", Truck],
  ["routingTitle", "routingText", ArrowRight],
  ["rewardsTitle", "rewardsText", Wallet],
  ["qualityTitle", "qualityText", ShieldCheck]
];

export default function SuppliersPage() {
  const {t} = useTranslation();

  return (
    <SmsMarketplace>
      <PageShell>
        <PageHeader title={t("suppliersPage.title")} description={t("suppliersPage.description")} />

        <section className="mt-6 grid gap-4 md:grid-cols-2">
          {supplierSections.map(([titleKey, textKey, Icon]) => (
            <Card key={String(titleKey)} title={t(`suppliersPage.${titleKey}`)}>
              <div className="flex gap-3">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-cyan-50 text-accent ring-1 ring-cyan-100">
                  <Icon size={18} />
                </span>
                <p className="text-sm leading-7 text-neutral-700">{t(`suppliersPage.${textKey}`)}</p>
              </div>
            </Card>
          ))}
        </section>

        <Card className="mt-6" title={t("suppliersPage.cabinetTitle")} description={t("suppliersPage.cabinetText")}>
          <div className="flex flex-wrap gap-3">
            <Link className="btn btn-primary" href="/supplier">{t("suppliersPage.openCabinet")}</Link>
            <Link className="btn btn-secondary" href="/abuse">{t("suppliersPage.contactTeam")}</Link>
          </div>
          <p className="mt-4 text-sm leading-7 text-neutral-500">{t("suppliersPage.contactPlaceholder")}</p>
        </Card>
      </PageShell>
    </SmsMarketplace>
  );
}

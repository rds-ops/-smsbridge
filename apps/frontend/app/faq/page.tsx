"use client";

import {SmsMarketplace} from "@/components/buyer/SmsMarketplace";
import {Card, PageHeader, PageShell} from "@/components/shared/ui";
import {useTranslation} from "@/lib/i18n";

const questionKeys = [
  ["whatTitle", "whatText"],
  ["activationTitle", "activationText"],
  ["buyTitle", "buyText"],
  ["noSmsTitle", "noSmsText"],
  ["apiTitle", "apiText"],
  ["suppliersTitle", "suppliersText"],
  ["abuseTitle", "abuseText"],
  ["refundsTitle", "refundsText"]
];

export default function FaqPage() {
  const {t} = useTranslation();

  return (
    <SmsMarketplace>
      <PageShell>
        <PageHeader title={t("faq.title")} description={t("faq.description")} />

        <section className="mt-6 grid gap-4">
          {questionKeys.map(([titleKey, textKey]) => (
            <Card key={titleKey} title={t(`faq.${titleKey}`)}>
              <p className="text-sm leading-7 text-neutral-700">{t(`faq.${textKey}`)}</p>
            </Card>
          ))}
        </section>

        <Card className="mt-6" title={t("faq.contactTitle")}>
          <div className="grid gap-3 text-sm leading-7 text-neutral-700">
            <p>{t("faq.supportPlaceholder")}</p>
            <p>{t("faq.abusePlaceholder")}</p>
            <p className="text-neutral-500">{t("faq.contactNote")}</p>
          </div>
        </Card>
      </PageShell>
    </SmsMarketplace>
  );
}

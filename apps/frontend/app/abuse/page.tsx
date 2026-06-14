"use client";

import {SmsMarketplace} from "@/components/buyer/SmsMarketplace";
import {Card, PageShell} from "@/components/shared/ui";
import {useTranslation} from "@/lib/i18n";

export default function AbusePage() {
  const {t} = useTranslation();
  return (
    <SmsMarketplace>
    <PageShell>
      <Card title={t("legal.abuse")}>
        <p className="leading-7 text-neutral-700">{t("legal.abuseText")}</p>
      </Card>
    </PageShell>
    </SmsMarketplace>
  );
}

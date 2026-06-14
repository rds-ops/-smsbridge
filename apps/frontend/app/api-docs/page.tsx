"use client";

import {useEffect, useState} from "react";
import {SmsMarketplace} from "@/components/buyer/SmsMarketplace";
import {Alert, Card, CopyButton, PageHeader, PageShell, StatusBadge, Toast} from "@/components/shared/ui";
import {createApiKey, getApiKeyUsage, listApiKeys, regenerateApiKey, revokeApiKey} from "@/lib/client/api";
import {dateTime} from "@/lib/shared/format";
import type {BuyerApiKey, BuyerApiKeyCreated, BuyerApiKeyUsage} from "@/lib/shared/types";
import {useTranslation} from "@/lib/i18n";

const defaultScopes = ["read", "wallet:read", "orders:create", "orders:read", "orders:cancel", "orders:finish", "payments:create", "payments:read"];

const examples = {
  balance: `curl -H "Authorization: Bearer $SMSBRIDGE_API_KEY" \\
  http://localhost:8000/api/v1/balance`,
  prices: `curl -H "Authorization: Bearer $SMSBRIDGE_API_KEY" \\
  "http://localhost:8000/api/v1/prices?service_code=telegram&country_iso2=ID"`,
  create: `curl -X POST http://localhost:8000/api/v1/orders \\
  -H "Authorization: Bearer $SMSBRIDGE_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"service_code":"telegram","country_iso2":"ID"}'`,
  getOrder: `curl -H "Authorization: Bearer $SMSBRIDGE_API_KEY" \\
  http://localhost:8000/api/v1/orders/$ORDER_PUBLIC_ID`,
  cancel: `curl -X POST -H "Authorization: Bearer $SMSBRIDGE_API_KEY" \\
  http://localhost:8000/api/v1/orders/$ORDER_PUBLIC_ID/cancel`,
  finish: `curl -X POST -H "Authorization: Bearer $SMSBRIDGE_API_KEY" \\
  http://localhost:8000/api/v1/orders/$ORDER_PUBLIC_ID/finish`
};

export default function ApiDocsPage() {
  const {t} = useTranslation();
  const [apiKey, setApiKey] = useState("");
  const [managedKeys, setManagedKeys] = useState<BuyerApiKey[]>([]);
  const [createdKey, setCreatedKey] = useState<BuyerApiKeyCreated | null>(null);
  const [selectedUsageKey, setSelectedUsageKey] = useState("");
  const [usage, setUsage] = useState<BuyerApiKeyUsage | null>(null);
  const [keyName, setKeyName] = useState("Default integration key");
  const [scopes, setScopes] = useState<string[]>(defaultScopes);
  const [toast, setToast] = useState<{type: "success" | "error"; message: string}>({type: "success", message: ""});

  async function loadKeys() {
    try {
      const rows = await listApiKeys();
      setManagedKeys(rows);
      if (!selectedUsageKey && rows[0]) setSelectedUsageKey(rows[0].public_id);
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("api.loadKeysFailed")});
    }
  }

  useEffect(() => {
    loadKeys();
  }, []);

  useEffect(() => {
    if (!selectedUsageKey) {
      setUsage(null);
      return;
    }
    getApiKeyUsage(selectedUsageKey)
      .then(setUsage)
      .catch((err) => setToast({type: "error", message: err instanceof Error ? err.message : t("api.loadUsageFailed")}));
  }, [selectedUsageKey]);

  async function regenerate() {
    setToast({type: "success", message: ""});
    try {
      const response = await regenerateApiKey();
      setApiKey(response.api_key);
      setToast({type: "success", message: t("api.generatedToast")});
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("api.generateFailed")});
    }
  }

  async function createManagedKey() {
    setToast({type: "success", message: ""});
    try {
      const created = await createApiKey({name: keyName.trim() || null, scopes});
      setCreatedKey(created);
      setSelectedUsageKey(created.public_id);
      setToast({type: "success", message: t("api.managedKeyCreated")});
      await loadKeys();
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("api.createKeyFailed")});
    }
  }

  async function revokeManagedKey(publicId: string) {
    if (!window.confirm(t("api.confirmRevoke"))) return;
    try {
      await revokeApiKey(publicId);
      setToast({type: "success", message: t("api.keyRevoked")});
      await loadKeys();
      if (selectedUsageKey === publicId) setUsage(await getApiKeyUsage(publicId));
    } catch (err) {
      setToast({type: "error", message: err instanceof Error ? err.message : t("api.revokeFailed")});
    }
  }

  function toggleScope(scope: string) {
    setScopes((current) => current.includes(scope) ? current.filter((item) => item !== scope) : [...current, scope]);
  }

  return (
    <SmsMarketplace>
    <PageShell>
      <Toast type={toast.type} message={toast.message} />
      <PageHeader
        title={t("api.title")}
        description={t("api.description")}
      />

      <section className="mt-6 grid gap-4 lg:grid-cols-[0.85fr_1.15fr]">
        <Card title={t("api.managedKeys")} description={t("api.managedKeysDesc")}>
          <div className="grid gap-3">
            <label className="grid gap-1 text-sm">
              {t("common.name")}
              <input className="field" value={keyName} onChange={(event) => setKeyName(event.target.value)} maxLength={120} />
            </label>
            <div className="grid gap-2">
              <p className="text-sm font-medium">{t("api.scopes")}</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {defaultScopes.map((scope) => (
                  <label className="flex items-center gap-2 text-sm" key={scope}>
                    <input type="checkbox" checked={scopes.includes(scope)} onChange={() => toggleScope(scope)} />
                    <span>{scope}</span>
                  </label>
                ))}
              </div>
            </div>
            <button className="btn btn-primary" onClick={createManagedKey}>{t("api.createManagedKey")}</button>
          </div>
          {createdKey && (
            <Alert type="success">
              <div className="grid gap-2">
                <strong>{t("api.rawKeyShownOnce")}</strong>
                <code className="break-all rounded-md bg-white p-2 text-xs">{createdKey.api_key}</code>
                <CopyButton value={createdKey.api_key} />
              </div>
            </Alert>
          )}
        </Card>

        <Card title={t("api.keyList")} description={t("api.keyListDesc")}>
          {!managedKeys.length ? <p className="text-sm text-neutral-600">{t("api.noManagedKeys")}</p> : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-line text-sm">
                <thead className="bg-panel text-left text-xs uppercase tracking-wide text-neutral-500">
                  <tr>
                    <th className="px-3 py-2">{t("common.name")}</th>
                    <th className="px-3 py-2">{t("api.prefix")}</th>
                    <th className="px-3 py-2">{t("common.status")}</th>
                    <th className="px-3 py-2">{t("api.scopes")}</th>
                    <th className="px-3 py-2">{t("api.lastUsed")}</th>
                    <th className="px-3 py-2">{t("common.created")}</th>
                    <th className="px-3 py-2">{t("common.actions")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {managedKeys.map((key) => (
                    <tr className={selectedUsageKey === key.public_id ? "bg-blue-50" : ""} key={key.public_id}>
                      <td className="px-3 py-2">{key.name || "-"}</td>
                      <td className="px-3 py-2"><code>{key.key_prefix}</code></td>
                      <td className="px-3 py-2"><StatusBadge status={key.status} /></td>
                      <td className="max-w-xs px-3 py-2 text-xs text-neutral-600">{(key.scopes || []).join(", ") || "-"}</td>
                      <td className="px-3 py-2">{dateTime(key.last_used_at)}</td>
                      <td className="px-3 py-2">{dateTime(key.created_at)}</td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap gap-2">
                          <button className="btn btn-secondary px-2 py-1 text-xs" onClick={() => setSelectedUsageKey(key.public_id)}>{t("api.viewUsage")}</button>
                          <button className="btn btn-secondary px-2 py-1 text-xs" onClick={() => revokeManagedKey(key.public_id)} disabled={key.status === "revoked"}>{t("api.revoke")}</button>
                        </div>
                        {key.revoked_at && <p className="mt-1 text-xs text-neutral-500">{t("api.revokedAt")}: {dateTime(key.revoked_at)}</p>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </section>

      <section className="mt-6">
        <Card title={t("api.usageTitle")} description={usage ? `${usage.key_prefix} · ${usage.status}` : t("api.usageDesc")}>
          {!usage ? <p className="text-sm text-neutral-600">{t("api.selectKeyUsage")}</p> : (
            <div className="grid gap-4">
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-md border border-line bg-panel p-3">
                  <p className="text-sm text-neutral-500">{t("api.totalRequests")}</p>
                  <p className="mt-1 text-2xl font-semibold">{usage.total_requests}</p>
                </div>
                <div className="rounded-md border border-line bg-panel p-3">
                  <p className="text-sm text-neutral-500">{t("api.lastUsed")}</p>
                  <p className="mt-1 text-lg font-semibold">{dateTime(usage.last_used_at)}</p>
                </div>
              </div>
              {!usage.recent.length ? <p className="text-sm text-neutral-600">{t("api.noUsage")}</p> : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-line text-sm">
                    <thead className="bg-panel text-left text-xs uppercase tracking-wide text-neutral-500">
                      <tr>
                        <th className="px-3 py-2">{t("common.method")}</th>
                        <th className="px-3 py-2">{t("common.endpoint")}</th>
                        <th className="px-3 py-2">{t("common.status")}</th>
                        <th className="px-3 py-2">{t("api.requests")}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {usage.recent.map((row) => (
                        <tr key={`${row.method}-${row.endpoint}-${row.status_code}`}>
                          <td className="px-3 py-2">{row.method}</td>
                          <td className="px-3 py-2">{row.endpoint}</td>
                          <td className="px-3 py-2">{row.status_code}</td>
                          <td className="px-3 py-2">{row.count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </Card>
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
        <Card title={t("api.legacyKeyStatus")} description={t("api.legacyKeyStatusDesc")}>
          <button className="btn btn-primary" onClick={regenerate}>{t("api.regenerate")}</button>
          {apiKey ? (
            <div className="mt-4 rounded-md border border-line bg-panel p-3">
              <p className="text-sm font-medium">{t("api.shownOnce")}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <code className="break-all text-sm">{apiKey}</code>
                <CopyButton value={apiKey} />
              </div>
            </div>
          ) : (
            <div className="mt-4"><Alert>{t("api.generateReady")}</Alert></div>
          )}
        </Card>
        <Card title={t("api.authTitle")} description={t("api.authDesc")}>
          <pre className="overflow-auto rounded-md bg-neutral-950 p-4 text-sm text-white">Authorization: Bearer $SMSBRIDGE_API_KEY</pre>
        </Card>
      </section>

      <section className="mt-6 grid gap-4">
        {[
          ["exampleBalance", examples.balance],
          ["examplePrices", examples.prices],
          ["exampleCreate", examples.create],
          ["exampleGetOrder", examples.getOrder],
          ["exampleCancel", examples.cancel],
          ["exampleFinish", examples.finish]
        ].map(([name, code]) => (
          <Card key={name} title={t(`api.${name}`)}>
            <div className="mb-2 flex justify-end"><CopyButton value={code} /></div>
            <pre className="overflow-auto rounded-md bg-neutral-950 p-4 text-sm text-white">{code}</pre>
          </Card>
        ))}
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card title={t("api.nodeExample")}>
          <pre className="overflow-auto rounded-md bg-neutral-950 p-4 text-sm text-white">{`const res = await fetch("http://localhost:8000/api/v1/prices?service_code=telegram", {
  headers: { Authorization: \`Bearer \${process.env.SMSBRIDGE_API_KEY}\` }
});
console.log(await res.json());`}</pre>
        </Card>
        <Card title={t("api.pythonExample")}>
          <pre className="overflow-auto rounded-md bg-neutral-950 p-4 text-sm text-white">{`import os
import requests

headers = {"Authorization": f"Bearer {os.environ['SMSBRIDGE_API_KEY']}"}
order = requests.post(
    "http://localhost:8000/api/v1/orders",
    json={"service_code": "telegram", "country_iso2": "ID"},
    headers=headers,
)
print(order.json())`}</pre>
        </Card>
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card title={t("api.balanceResponse")}>
          <pre className="overflow-auto rounded-md bg-panel p-4 text-sm">{`{
  "balance": "25.0000",
  "held_balance": "0.0000",
  "currency": "USD"
}`}</pre>
        </Card>
        <Card title={t("api.orderResponse")}>
          <pre className="overflow-auto rounded-md bg-panel p-4 text-sm">{`{
  "public_id": "order-uuid",
  "service_code": "telegram",
  "country_iso2": "ID",
  "phone_number": "+628123456789",
  "status": "waiting_sms",
  "price": "0.5625"
}`}</pre>
        </Card>
      </section>
    </PageShell>
    </SmsMarketplace>
  );
}

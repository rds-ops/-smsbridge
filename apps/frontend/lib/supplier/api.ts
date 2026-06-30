import type {
  SupplierActivationHistoryRow,
  SupplierInventoryRow,
  SupplierInventoryUpdateItem,
  SupplierPayoutRequest,
  SupplierProfile,
  SupplierSmsPushRequest,
  SupplierSmsPushResponse,
  SupplierTransactionHistoryRow
} from "@/lib/shared/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

class SupplierApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "SupplierApiError";
    this.status = status;
  }
}

async function supplierFetch<T>(apiKey: string, path: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  headers.set("Authorization", `Bearer ${apiKey}`);
  const response = await fetch(`${API_BASE}${path}`, {...options, headers, cache: "no-store"});
  if (!response.ok) {
    let message = response.statusText || `Request failed with ${response.status}`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") message = payload.detail;
    } catch {
      // Keep the status text fallback.
    }
    throw new SupplierApiError(message, response.status);
  }
  return response.json() as Promise<T>;
}

export function supplierMe(apiKey: string) {
  return supplierFetch<SupplierProfile>(apiKey, "/supplier/v1/me");
}

export function getSupplierInventory(apiKey: string) {
  return supplierFetch<SupplierInventoryRow[]>(apiKey, "/supplier/v1/inventory");
}

export function updateSupplierInventory(apiKey: string, items: SupplierInventoryUpdateItem[]) {
  return supplierFetch<{updated: number}>(apiKey, "/supplier/v1/inventory/update", {
    method: "POST",
    body: JSON.stringify({items})
  });
}

export function getSupplierPayoutRequests(apiKey: string) {
  return supplierFetch<SupplierPayoutRequest[]>(apiKey, "/supplier/v1/payout-requests");
}

export function getSupplierActivations(
  apiKey: string,
  params: {limit?: number; offset?: number; status?: string; service?: string; country?: string; phone?: string} = {}
) {
  const query = new URLSearchParams();
  query.set("limit", String(params.limit ?? 50));
  query.set("offset", String(params.offset ?? 0));
  if (params.status) query.set("status", params.status);
  if (params.service) query.set("service", params.service);
  if (params.country) query.set("country", params.country);
  if (params.phone) query.set("phone", params.phone);
  return supplierFetch<SupplierActivationHistoryRow[]>(apiKey, `/supplier/v1/activations?${query.toString()}`);
}

export function getSupplierTransactions(
  apiKey: string,
  params: {limit?: number; offset?: number; type?: string; status?: string} = {}
) {
  const query = new URLSearchParams();
  query.set("limit", String(params.limit ?? 50));
  query.set("offset", String(params.offset ?? 0));
  if (params.type) query.set("type", params.type);
  if (params.status) query.set("status", params.status);
  return supplierFetch<SupplierTransactionHistoryRow[]>(apiKey, `/supplier/v1/transactions?${query.toString()}`);
}

export function createSupplierPayoutRequest(apiKey: string, body: {amount: string; payout_method?: string | null; payout_address?: string | null}) {
  return supplierFetch<SupplierPayoutRequest>(apiKey, "/supplier/v1/payout-requests", {
    method: "POST",
    body: JSON.stringify(body)
  });
}

export function pushSupplierSms(apiKey: string, body: SupplierSmsPushRequest) {
  return supplierFetch<SupplierSmsPushResponse>(apiKey, "/supplier/v1/sms", {
    method: "POST",
    body: JSON.stringify(body)
  });
}

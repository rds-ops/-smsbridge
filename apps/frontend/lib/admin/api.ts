import {apiFetch} from "@/lib/shared/api";
import type {
  AdminOpsSummary,
  AdminRiskAction,
  AdminRiskActionCreate,
  AdminRiskUserSummary,
  Metrics,
  Order,
  Provider,
  Supplier,
  SupplierActivation,
  SupplierInventory,
  SupplierSms,
  SupplierTransaction,
  User,
  Wallet
} from "@/lib/shared/types";

export function getAdminOpsSummary() {
  return apiFetch<AdminOpsSummary>("/admin/ops/summary");
}

export function getAdminRiskUsers(filters: {risk_level?: string; user_id?: number} = {}) {
  const params = new URLSearchParams();
  if (filters.risk_level) params.set("risk_level", filters.risk_level);
  if (filters.user_id) params.set("user_id", String(filters.user_id));
  const query = params.toString();
  return apiFetch<AdminRiskUserSummary[]>(`/admin/risk/users${query ? `?${query}` : ""}`);
}

export function getAdminRiskUser(userId: number) {
  return apiFetch<AdminRiskUserSummary>(`/admin/risk/users/${userId}`);
}

export function getAdminRiskActions(userId: number) {
  return apiFetch<AdminRiskAction[]>(`/admin/risk/users/${userId}/actions`);
}

export function createAdminRiskAction(userId: number, body: AdminRiskActionCreate) {
  return apiFetch<AdminRiskAction>(`/admin/risk/users/${userId}/actions`, {method: "POST", body: JSON.stringify(body)});
}

export function getAdminMetrics() {
  return apiFetch<Metrics>("/admin/metrics");
}

export function getAdminUsers() {
  return apiFetch<User[]>("/admin/users");
}

export function getAdminOrders() {
  return apiFetch<Order[]>("/admin/orders");
}

export function getProviders() {
  return apiFetch<Provider[]>("/admin/providers");
}

export function getSuppliers() {
  return apiFetch<Supplier[]>("/admin/suppliers");
}

export function createSupplier(payload: {
  name: string;
  email?: string | null;
  status: string;
  reward_percent: string;
  notes?: string | null;
}) {
  return apiFetch<Supplier>("/admin/suppliers", {method: "POST", body: JSON.stringify(payload)});
}

export function updateSupplier(supplierId: number, payload: Partial<{
  name: string;
  email: string | null;
  status: string;
  reward_percent: string;
  notes: string | null;
}>) {
  return apiFetch<Supplier>(`/admin/suppliers/${supplierId}`, {method: "PATCH", body: JSON.stringify(payload)});
}

export function regenerateSupplierApiKey(supplierId: number) {
  return apiFetch<{api_key: string; message: string}>(`/admin/suppliers/${supplierId}/api-key/regenerate`, {method: "POST"});
}

export function getSupplierInventory(supplierId: number) {
  return apiFetch<SupplierInventory[]>(`/admin/suppliers/${supplierId}/inventory`);
}

export function getSupplierActivations(supplierId: number) {
  return apiFetch<SupplierActivation[]>(`/admin/suppliers/${supplierId}/activations`);
}

export function getSupplierSms(supplierId: number) {
  return apiFetch<SupplierSms[]>(`/admin/suppliers/${supplierId}/sms`);
}

export function getSupplierTransactions(supplierId: number) {
  return apiFetch<SupplierTransaction[]>(`/admin/suppliers/${supplierId}/transactions`);
}

export function getAuditLogs() {
  return apiFetch<Array<Record<string, unknown>>>("/admin/audit-logs");
}

export function getApiRequestLogs() {
  return apiFetch<Array<Record<string, unknown>>>("/admin/api-request-logs");
}

export function manualDeposit(payload: {user_id: number; amount: string; reference?: string | null}) {
  return apiFetch<Wallet>("/admin/wallets/deposit", {method: "POST", body: JSON.stringify(payload)});
}

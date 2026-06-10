import {apiFetch} from "@/lib/shared/api";
import type {
  AdminOpsSummary,
  AdminApiRequestLog,
  AdminPaymentIntent,
  AdminPaymentIntentFilters,
  AdminRiskAction,
  AdminRiskActionCreate,
  AdminRiskUserSummary,
  AdminSupplierPayoutAction,
  AdminSupplierPayoutRequest,
  AdminSupplierPayoutRequestFilters,
  Metrics,
  Order,
  OperationalCleanupDryRun,
  PaymentCreditReconciliation,
  Provider,
  Supplier,
  SupplierActivation,
  SupplierInventory,
  SupplierPayoutReconciliation,
  SupplierReleaseRetry,
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

export function getAdminPaymentIntents(filters: AdminPaymentIntentFilters = {}) {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.provider) params.set("provider", filters.provider);
  if (filters.user_id) params.set("user_id", String(filters.user_id));
  const query = params.toString();
  return apiFetch<AdminPaymentIntent[]>(`/admin/payment-intents${query ? `?${query}` : ""}`);
}

export function getAdminPaymentIntent(id: number) {
  return apiFetch<AdminPaymentIntent>(`/admin/payment-intents/${id}`);
}

export function manualCompletePaymentIntent(id: number) {
  return apiFetch<AdminPaymentIntent>(`/admin/payment-intents/${id}/manual-complete`, {method: "POST"});
}

export function getAdminSupplierPayoutRequests(filters: AdminSupplierPayoutRequestFilters = {}) {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.supplier_id) params.set("supplier_id", String(filters.supplier_id));
  const query = params.toString();
  return apiFetch<AdminSupplierPayoutRequest[]>(`/admin/supplier-payout-requests${query ? `?${query}` : ""}`);
}

export function getAdminSupplierPayoutRequest(id: number) {
  return apiFetch<AdminSupplierPayoutRequest>(`/admin/supplier-payout-requests/${id}`);
}

export function approveSupplierPayoutRequest(id: number, body: AdminSupplierPayoutAction = {}) {
  return apiFetch<AdminSupplierPayoutRequest>(`/admin/supplier-payout-requests/${id}/approve`, {method: "POST", body: JSON.stringify(body)});
}

export function rejectSupplierPayoutRequest(id: number, body: AdminSupplierPayoutAction = {}) {
  return apiFetch<AdminSupplierPayoutRequest>(`/admin/supplier-payout-requests/${id}/reject`, {method: "POST", body: JSON.stringify(body)});
}

export function markSupplierPayoutPaid(id: number, body: AdminSupplierPayoutAction = {}) {
  return apiFetch<AdminSupplierPayoutRequest>(`/admin/supplier-payout-requests/${id}/mark-paid`, {method: "POST", body: JSON.stringify(body)});
}

export function getSupplierReleaseRetries() {
  return apiFetch<SupplierReleaseRetry[]>("/admin/supplier-release-retries");
}

export function getPaymentReconciliation() {
  return apiFetch<PaymentCreditReconciliation>("/admin/payment-intents/reconciliation");
}

export function getSupplierPayoutReconciliation() {
  return apiFetch<SupplierPayoutReconciliation>("/admin/supplier-payout-requests/reconciliation");
}

export function getOperationalCleanupDryRun() {
  return apiFetch<OperationalCleanupDryRun>("/admin/ops/cleanup/dry-run", {method: "POST"});
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
  return apiFetch<AdminApiRequestLog[]>("/admin/api-request-logs");
}

export function manualDeposit(payload: {user_id: number; amount: string; reference?: string | null}) {
  return apiFetch<Wallet>("/admin/wallets/deposit", {method: "POST", body: JSON.stringify(payload)});
}

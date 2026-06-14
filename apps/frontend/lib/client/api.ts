import {apiFetch} from "@/lib/shared/api";
import type {BuyerApiKey, BuyerApiKeyCreated, BuyerApiKeyUsage, Country, CreatePaymentIntentRequest, Order, PaymentIntent, Price, Service, UserLimit, Wallet, WalletTransaction} from "@/lib/shared/types";

export function getBalance() {
  return apiFetch<Wallet>("/api/v1/balance");
}

export function getWalletTransactions(limit = 10, offset = 0) {
  return apiFetch<WalletTransaction[]>(`/api/v1/wallet/transactions?limit=${limit}&offset=${offset}`);
}

export function createPaymentIntent(payload: CreatePaymentIntentRequest, idempotencyKey?: string) {
  const headers = idempotencyKey ? {"Idempotency-Key": idempotencyKey} : undefined;
  return apiFetch<PaymentIntent>("/api/v1/payment-intents", {method: "POST", body: JSON.stringify(payload), headers});
}

export function getPaymentIntent(publicId: string) {
  return apiFetch<PaymentIntent>(`/api/v1/payment-intents/${publicId}`);
}

export function listPaymentIntents(params: {limit?: number; offset?: number} = {}) {
  const query = new URLSearchParams();
  query.set("limit", String(params.limit ?? 50));
  query.set("offset", String(params.offset ?? 0));
  return apiFetch<PaymentIntent[]>(`/api/v1/payment-intents?${query}`);
}

export function getLimits() {
  return apiFetch<UserLimit>("/api/v1/limits");
}

export function getServices() {
  return apiFetch<Service[]>("/api/v1/services");
}

export function getCountries() {
  return apiFetch<Country[]>("/api/v1/countries");
}

export function getPrices(serviceCode?: string, countryIso2?: string) {
  const query = new URLSearchParams();
  if (serviceCode) query.set("service_code", serviceCode);
  if (countryIso2) query.set("country_iso2", countryIso2);
  return apiFetch<Price[]>(`/api/v1/prices?${query}`);
}

export function listOrders(filters: {status?: string; service?: string; country?: string} = {}) {
  const query = new URLSearchParams();
  if (filters.status) query.set("status", filters.status);
  if (filters.service) query.set("service", filters.service);
  if (filters.country) query.set("country", filters.country);
  return apiFetch<Order[]>(`/api/v1/orders?${query}`);
}

export function getOrder(publicId: string) {
  return apiFetch<Order>(`/api/v1/orders/${publicId}`);
}

export function createOrder(payload: {service_code: string; country_iso2: string; operator?: string | null}) {
  return apiFetch<Order>("/api/v1/orders", {method: "POST", body: JSON.stringify(payload)});
}

export function cancelOrder(publicId: string) {
  return apiFetch<Order>(`/api/v1/orders/${publicId}/cancel`, {method: "POST"});
}

export function finishOrder(publicId: string) {
  return apiFetch<Order>(`/api/v1/orders/${publicId}/finish`, {method: "POST"});
}

export function regenerateApiKey() {
  return apiFetch<{api_key: string; message: string}>("/api/v1/api-key/regenerate", {method: "POST"});
}

export function createApiKey(payload: {name?: string | null; scopes?: string[] | null}) {
  return apiFetch<BuyerApiKeyCreated>("/api/v1/api-keys", {method: "POST", body: JSON.stringify(payload)});
}

export function listApiKeys() {
  return apiFetch<BuyerApiKey[]>("/api/v1/api-keys");
}

export function revokeApiKey(publicId: string) {
  return apiFetch<BuyerApiKey>(`/api/v1/api-keys/${publicId}/revoke`, {method: "POST"});
}

export function getApiKeyUsage(publicId: string) {
  return apiFetch<BuyerApiKeyUsage>(`/api/v1/api-keys/${publicId}/usage`);
}

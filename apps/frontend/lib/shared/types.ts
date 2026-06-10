export type User = {
  id: number;
  email: string;
  role: "user" | "admin";
  status: string;
  tier: string;
  locale: "en" | "ru";
  api_key_enabled?: boolean;
  created_at?: string;
  wallet?: Wallet | null;
  limit?: UserLimit | null;
};

export type Wallet = {
  balance: string;
  held_balance: string;
  currency: string;
};

export type WalletTransaction = {
  id: number;
  type: string;
  amount: string;
  status: string;
  order_public_id?: string | null;
  reference?: string | null;
  created_at: string;
};

export type UserLimit = {
  max_orders_per_minute: number;
  max_orders_per_day: number;
  max_active_orders: number;
  max_daily_spend: string;
};

export type Service = {
  code: string;
  name_ru: string;
  name_en: string;
  category?: string | null;
  is_active: boolean;
};

export type Country = {
  iso2: string;
  name_ru: string;
  name_en: string;
  is_active: boolean;
};

export type Price = {
  service_code: string;
  country_iso2: string;
  operator: string | null;
  final_price: string;
  available_count: number;
  delivery_rate: string;
  provider_code?: string;
  provider_name?: string;
};

export type Order = {
  id?: number;
  public_id: string;
  user_id?: number;
  provider_id?: number;
  provider_order_id?: string | null;
  service_code: string;
  country_iso2: string;
  operator: string | null;
  phone_number: string | null;
  status: string;
  price: string;
  provider_cost?: string;
  sms_code: string | null;
  sms_text: string | null;
  expires_at: string;
  created_at: string;
  updated_at: string;
};

export type Provider = {
  id: number;
  name: string;
  code: string;
  type: string;
  status: string;
  priority: number;
  default_markup_percent: string;
};

export type Supplier = {
  id: number;
  name: string;
  email?: string | null;
  status: string;
  reward_percent: string;
  balance: string;
  held_balance: string;
  currency: string;
  notes?: string | null;
  inventory_count?: number;
  created_at: string;
  updated_at: string;
};

export type SupplierInventory = {
  id: number;
  supplier_id: number;
  service_code: string;
  country_iso2: string;
  operator?: string | null;
  available_count: number;
  success_rate?: string | null;
  avg_sms_time_seconds?: number | null;
  status: string;
  last_sync_at: string;
  created_at: string;
  updated_at: string;
};

export type SupplierActivation = {
  id: number;
  supplier_id: number;
  order_id?: number | null;
  supplier_activation_id?: string | null;
  phone_number: string;
  service_code: string;
  country_iso2: string;
  operator?: string | null;
  status: string;
  client_price: string;
  supplier_reward: string;
  sms_text?: string | null;
  sms_code?: string | null;
  created_at: string;
  updated_at: string;
};

export type SupplierSms = {
  id: number;
  supplier_id: number;
  activation_id?: number | null;
  order_id?: number | null;
  supplier_sms_id: string;
  phone_number: string;
  phone_from?: string | null;
  text: string;
  status: string;
  created_at: string;
};

export type SupplierTransaction = {
  id: number;
  supplier_id: number;
  activation_id?: number | null;
  order_id?: number | null;
  type: string;
  amount: string;
  status: string;
  reference?: string | null;
  tx_metadata: Record<string, unknown>;
  created_at: string;
};

export type Metrics = Record<string, unknown>;

export type AdminOpsSummary = {
  status: string;
  high_risk_users_count: number;
  watchlisted_users_count: number;
  pending_supplier_release_retries_count: number;
  dead_supplier_release_retries_count: number;
  payment_reconciliation_issue_counts: Record<string, number>;
  supplier_payout_reconciliation_issue_counts: Record<string, number>;
  pending_payment_intents_count: number;
  pending_supplier_payout_requests_count: number;
  active_waiting_sms_orders_count: number;
  recent_5xx_request_count: number;
  recent_rate_limit_429_count: number;
};

export type RiskLevel = "low" | "medium" | "high";

export type AdminRiskUserSummary = {
  user_id: number;
  email: string;
  status: string;
  tier: string;
  risk_level: RiskLevel;
  risk_score: number;
  total_orders: number;
  active_orders: number;
  cancelled_orders: number;
  expired_orders: number;
  failed_orders: number;
  completed_orders: number;
  cancellation_rate: number;
  expiration_rate: number;
  failed_rate: number;
  orders_last_1h: number;
  orders_last_24h: number;
  api_requests_last_1h: number;
  managed_api_key_count: number;
  revoked_api_key_count: number;
  last_order_at?: string | null;
  last_api_request_at?: string | null;
  watchlisted: boolean;
  last_reviewed_at?: string | null;
  latest_note?: string | null;
};

export type AdminRiskActionType = "watch" | "note" | "clear_watch" | "mark_reviewed";

export type AdminRiskAction = {
  id: number;
  user_id: number;
  actor_user_id?: number | null;
  action: AdminRiskActionType;
  note?: string | null;
  created_at: string;
};

export type AdminRiskActionCreate = {
  action: AdminRiskActionType;
  note?: string | null;
};

export type AdminPaymentIntent = {
  id: number;
  public_id: string;
  user_id: number;
  provider: string;
  currency: string;
  amount: string;
  status: string;
  provider_reference?: string | null;
  idempotency_key?: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  expires_at?: string | null;
  succeeded_at?: string | null;
  failed_at?: string | null;
  cancelled_at?: string | null;
  last_webhook_at?: string | null;
  last_webhook_event_id?: string | null;
  last_webhook_status?: string | null;
  last_webhook_error?: string | null;
  failed_reason?: string | null;
};

export type AdminPaymentIntentFilters = {
  status?: string;
  provider?: string;
  user_id?: number;
};

export type BuyerApiKey = {
  id: number;
  public_id: string;
  name?: string | null;
  key_prefix: string;
  status: string;
  scopes?: string[] | null;
  last_used_at?: string | null;
  created_at: string;
  revoked_at?: string | null;
};

export type BuyerApiKeyCreated = BuyerApiKey & {
  api_key: string;
  message: string;
};

export type BuyerApiKeyUsageRow = {
  endpoint: string;
  method: string;
  status_code: number;
  count: number;
};

export type BuyerApiKeyUsage = {
  public_id: string;
  key_prefix: string;
  status: string;
  total_requests: number;
  last_used_at?: string | null;
  recent: BuyerApiKeyUsageRow[];
};

export type SupplierPayoutStatus = "requested" | "approved" | "rejected" | "cancelled" | "paid" | "failed";

export type AdminSupplierPayoutRequest = {
  id: number;
  public_id: string;
  supplier_id: number;
  amount: string;
  currency: string;
  status: SupplierPayoutStatus | string;
  payout_method?: string | null;
  payout_address?: string | null;
  admin_note?: string | null;
  failure_reason?: string | null;
  requested_at: string;
  approved_at?: string | null;
  rejected_at?: string | null;
  cancelled_at?: string | null;
  paid_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type AdminSupplierPayoutRequestFilters = {
  status?: string;
  supplier_id?: number;
};

export type AdminSupplierPayoutAction = {
  admin_note?: string | null;
  reason?: string | null;
};

export type AdminApiRequestLog = {
  id: number;
  user_id?: number | null;
  supplier_id?: number | null;
  buyer_api_key_id?: number | null;
  endpoint?: string | null;
  path?: string | null;
  method: string;
  ip_address?: string | null;
  ip?: string | null;
  status_code: number;
  request_id?: string | null;
  duration_ms?: number | null;
  created_at: string;
};

export type SupplierProfile = {
  id: number;
  name: string;
  email?: string | null;
  status: string;
  reward_percent: string;
  balance: string;
  held_balance: string;
  currency: string;
};

export type SupplierInventoryRow = {
  id: number;
  supplier_id: number;
  service_code: string;
  country_iso2: string;
  operator?: string | null;
  available_count: number;
  success_rate?: string | null;
  avg_sms_time_seconds?: number | null;
  status: string;
  last_sync_at: string;
  created_at: string;
  updated_at: string;
};

export type SupplierInventoryUpdateItem = {
  service_code: string;
  country_iso2: string;
  operator?: string | null;
  available_count: number;
  success_rate?: string | null;
  avg_sms_time_seconds?: number | null;
  status: string;
};

export type SupplierPayoutRequest = {
  id: number;
  public_id: string;
  supplier_id: number;
  amount: string;
  currency: string;
  status: string;
  payout_method?: string | null;
  payout_address?: string | null;
  admin_note?: string | null;
  failure_reason?: string | null;
  requested_at: string;
  approved_at?: string | null;
  rejected_at?: string | null;
  cancelled_at?: string | null;
  paid_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type SupplierReleaseRetry = {
  id: number;
  supplier_activation_id: number;
  supplier_id: number;
  order_id: number;
  retry_type: string;
  status: string;
  reason: string;
  attempt_count: number;
  next_retry_at: string;
  last_error?: string | null;
  last_attempt_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type PaymentCreditIssue = {
  issue_type: string;
  payment_intent_id?: number | null;
  payment_intent_public_id?: string | null;
  user_id?: number | null;
  provider?: string | null;
  amount?: string | null;
  status?: string | null;
  wallet_transaction_id?: number | null;
  created_at?: string | null;
};

export type PaymentCreditReconciliation = {
  counts: Record<string, number>;
  issues: PaymentCreditIssue[];
};

export type SupplierPayoutReconciliationIssue = {
  issue_type: string;
  payout_id?: number | null;
  payout_public_id?: string | null;
  supplier_id: number;
  status?: string | null;
  amount?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type SupplierPayoutReconciliation = {
  counts: Record<string, number>;
  issues: SupplierPayoutReconciliationIssue[];
};

export type OperationalCleanupDryRun = {
  api_request_logs: number;
  payment_webhook_events: number;
  supplier_release_retries: number;
  total: number;
  dry_run: boolean;
};

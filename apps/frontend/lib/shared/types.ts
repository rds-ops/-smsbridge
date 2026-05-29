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

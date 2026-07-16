export interface UserPublic {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export interface Account {
  id: string;
  name: string;
  institution_name: string | null;
  account_type: string;
  account_subtype: string | null;
  currency: string;
  current_balance: string;
  available_balance: string | null;
  mask: string | null;
  source: string;
  is_active: boolean;
  created_at: string;
}

export interface Transaction {
  id: string;
  account_id: string;
  posted_at: string;
  amount: string;
  currency: string;
  merchant_raw: string | null;
  merchant_normalized: string | null;
  description: string | null;
  category: string | null;
  transaction_type: string;
  is_transfer: boolean;
  is_duplicate_of: string | null;
  import_source: string;
  created_at: string;
}

export interface TransactionListResponse {
  items: Transaction[];
  total: number;
  page: number;
  page_size: number;
}

export interface NetWorthResponse {
  net_worth: string;
  assets_total: string;
  liabilities_total: string;
  by_account_type: Record<string, string>;
  methodology: string;
}

export interface CashFlowMonth {
  month: string;
  income: string;
  expenses: string;
  net: string;
  transaction_count: number;
}

export interface CashFlowResponse {
  months: CashFlowMonth[];
  total_income: string;
  total_expenses: string;
  net: string;
  period_start: string;
  period_end: string;
  methodology: string;
}

export interface BurnRateResponse {
  average_monthly_burn: string;
  is_burning: boolean;
  months_considered: number;
  period_start: string;
  period_end: string;
  methodology: string;
}

export type CategoryTrendDirection = "rising" | "falling" | "steady" | "new";

export interface CategoryTrend {
  category: string;
  latest_month_total: string;
  prior_average: string;
  change_pct: string | null;
  trend: CategoryTrendDirection;
}

export interface ExpenseTrendsResponse {
  categories: CategoryTrend[];
  period_start: string;
  period_end: string;
  methodology: string;
}

export type SubscriptionCadence = "weekly" | "monthly" | "annual";

export interface DetectedSubscription {
  merchant: string;
  cadence: SubscriptionCadence;
  average_amount: string;
  occurrences: number;
  last_charge_date: string;
  next_expected_date: string;
}

export interface SubscriptionsResponse {
  subscriptions: DetectedSubscription[];
  estimated_monthly_total: string;
  period_start: string;
  period_end: string;
  methodology: string;
}

export type EmergencyFundHealthTier = "unknown" | "critical" | "low" | "adequate" | "strong";

export interface EmergencyFundResponse {
  liquid_assets: string;
  average_monthly_expenses: string;
  months_of_coverage: string | null;
  health_tier: EmergencyFundHealthTier;
  methodology: string;
}

export interface DebtAccountProjection {
  account_id: string;
  account_name: string;
  current_balance: string;
  net_monthly_paydown: string;
  months_to_payoff: string | null;
  on_track: boolean;
}

export interface DebtPayoffResponse {
  accounts: DebtAccountProjection[];
  months_considered: number;
  methodology: string;
}

export interface RatiosResponse {
  savings_rate: string | null;
  expense_to_income_ratio: string | null;
  liquidity_ratio_months: string | null;
  debt_to_annual_income: string | null;
  months_considered: number;
  methodology: string;
}

export interface CsvImportResult {
  imported_count: number;
  duplicate_count: number;
  error_count: number;
  errors: string[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface RecommendationItem {
  title: string;
  explanation: string;
  category: string;
  confidence: number;
  metrics_used: string[];
  sources_used: string[];
}

export interface FinancialAdviceResponse {
  reasoning_summary: string;
  recommendations: RecommendationItem[];
}

export interface AIRecommendation {
  id: string;
  agent_name: string;
  title: string;
  explanation: string;
  category: string | null;
  confidence: string;
  citations: Record<string, unknown>;
  status: string;
  created_at: string;
}

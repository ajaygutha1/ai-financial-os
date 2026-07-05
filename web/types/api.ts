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

export const queryKeys = {
  me: ["auth", "me"] as const,
  accounts: ["accounts"] as const,
  account: (id: string) => ["accounts", id] as const,
  transactions: (filters: Record<string, unknown>) => ["transactions", filters] as const,
  netWorth: ["analytics", "net-worth"] as const,
};

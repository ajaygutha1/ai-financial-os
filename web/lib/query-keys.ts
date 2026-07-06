export const queryKeys = {
  me: ["auth", "me"] as const,
  accounts: ["accounts"] as const,
  account: (id: string) => ["accounts", id] as const,
  transactions: (filters: Record<string, unknown>) => ["transactions", filters] as const,
  netWorth: ["analytics", "net-worth"] as const,
  cashFlow: (months: number) => ["analytics", "cash-flow", months] as const,
  burnRate: (months: number) => ["analytics", "burn-rate", months] as const,
  expenseTrends: (months: number) => ["analytics", "expense-trends", months] as const,
  subscriptions: (months: number) => ["analytics", "subscriptions", months] as const,
  emergencyFund: (months: number) => ["analytics", "emergency-fund", months] as const,
  debtPayoff: (months: number) => ["analytics", "debt-payoff", months] as const,
  ratios: (months: number) => ["analytics", "ratios", months] as const,
};

"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { DebtPayoffResponse } from "@/types/api";

export function useDebtPayoff(months = 6) {
  return useQuery({
    queryKey: queryKeys.debtPayoff(months),
    queryFn: () => apiFetch<DebtPayoffResponse>(`/api/v1/analytics/debt-payoff?months=${months}`),
  });
}

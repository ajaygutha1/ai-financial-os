"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { CashFlowResponse } from "@/types/api";

export function useCashFlow(months = 6) {
  return useQuery({
    queryKey: queryKeys.cashFlow(months),
    queryFn: () => apiFetch<CashFlowResponse>(`/api/v1/analytics/cash-flow?months=${months}`),
  });
}

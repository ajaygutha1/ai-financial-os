"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { ExpenseTrendsResponse } from "@/types/api";

export function useExpenseTrends(months = 4) {
  return useQuery({
    queryKey: queryKeys.expenseTrends(months),
    queryFn: () =>
      apiFetch<ExpenseTrendsResponse>(`/api/v1/analytics/expense-trends?months=${months}`),
  });
}

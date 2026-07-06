"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { BurnRateResponse } from "@/types/api";

export function useBurnRate(months = 3) {
  return useQuery({
    queryKey: queryKeys.burnRate(months),
    queryFn: () => apiFetch<BurnRateResponse>(`/api/v1/analytics/burn-rate?months=${months}`),
  });
}

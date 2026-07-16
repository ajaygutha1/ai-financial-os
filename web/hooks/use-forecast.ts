"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { ForecastResponse } from "@/types/api";

export function useForecast(months = 6) {
  return useQuery({
    queryKey: queryKeys.forecast(months),
    queryFn: () => apiFetch<ForecastResponse>(`/api/v1/analytics/forecast?months=${months}`),
  });
}

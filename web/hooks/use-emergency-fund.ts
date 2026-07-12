"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { EmergencyFundResponse } from "@/types/api";

export function useEmergencyFund(months = 3) {
  return useQuery({
    queryKey: queryKeys.emergencyFund(months),
    queryFn: () =>
      apiFetch<EmergencyFundResponse>(`/api/v1/analytics/emergency-fund?months=${months}`),
  });
}

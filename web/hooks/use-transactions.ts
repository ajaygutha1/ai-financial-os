"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { TransactionListResponse } from "@/types/api";

export interface TransactionFilters {
  accountId?: string;
  page?: number;
  pageSize?: number;
}

export function useTransactions(filters: TransactionFilters = {}) {
  const { accountId, page = 1, pageSize = 50 } = filters;

  return useQuery({
    queryKey: queryKeys.transactions({ accountId, page, pageSize }),
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });
      if (accountId) params.set("account_id", accountId);
      return apiFetch<TransactionListResponse>(`/api/v1/transactions?${params.toString()}`);
    },
    placeholderData: keepPreviousData,
  });
}

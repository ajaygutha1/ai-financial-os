"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { Account } from "@/types/api";

interface LinkTokenResponse {
  link_token: string;
}

interface ExchangePublicTokenInput {
  public_token: string;
  institution_name: string | null;
}

interface ExchangePublicTokenResponse {
  accounts: Account[];
}

export function useCreatePlaidLinkToken() {
  return useMutation({
    mutationFn: () =>
      apiFetch<LinkTokenResponse>("/api/v1/connectors/plaid/link-token", { method: "POST" }),
  });
}

export function useExchangePlaidPublicToken() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ExchangePublicTokenInput) =>
      apiFetch<ExchangePublicTokenResponse>("/api/v1/connectors/plaid/exchange", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.accounts });
      void queryClient.invalidateQueries({ queryKey: queryKeys.netWorth });
    },
  });
}

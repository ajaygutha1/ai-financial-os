"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { CsvImportResult } from "@/types/api";

export interface CsvImportInput {
  accountId: string;
  file: File;
  debitPositive: boolean;
}

export function useCsvImport() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ accountId, file, debitPositive }: CsvImportInput) => {
      const formData = new FormData();
      formData.set("account_id", accountId);
      formData.set("debit_positive", String(debitPositive));
      formData.set("file", file);
      return apiFetch<CsvImportResult>("/api/v1/imports/csv", {
        method: "POST",
        body: formData,
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.netWorth });
      void queryClient.invalidateQueries({ queryKey: queryKeys.accounts });
    },
  });
}

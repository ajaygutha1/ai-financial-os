"use client";

import { useEffect, useState } from "react";
import { usePlaidLink } from "react-plaid-link";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useCreatePlaidLinkToken, useExchangePlaidPublicToken } from "@/hooks/use-plaid-link";
import { ApiError } from "@/lib/api-client";

export function ConnectBankButton() {
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const createLinkToken = useCreatePlaidLinkToken();
  const exchangeToken = useExchangePlaidPublicToken();

  const { open, ready } = usePlaidLink({
    token: linkToken,
    onSuccess: (publicToken, metadata) => {
      exchangeToken.mutate(
        { public_token: publicToken, institution_name: metadata.institution?.name ?? null },
        {
          onSuccess: (data) => {
            toast.success(
              data.accounts.length === 1
                ? `Connected ${data.accounts[0].name}.`
                : `Connected ${data.accounts.length} accounts.`
            );
          },
          onError: (error) => {
            toast.error(error instanceof ApiError ? error.message : "Failed to link account.");
          },
        }
      );
      setLinkToken(null);
    },
    onExit: () => setLinkToken(null),
  });

  // usePlaidLink creates a new handler whenever `token` changes and only
  // flips `ready` once that handler has finished loading -- open() has to
  // wait for both rather than firing right after the link-token mutation.
  useEffect(() => {
    if (linkToken && ready) {
      open();
    }
  }, [linkToken, ready, open]);

  const handleClick = async () => {
    try {
      const { link_token } = await createLinkToken.mutateAsync();
      setLinkToken(link_token);
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to start Plaid Link.");
    }
  };

  return (
    <Button variant="outline" onClick={handleClick} disabled={createLinkToken.isPending}>
      {createLinkToken.isPending ? "Connecting…" : "Connect a bank"}
    </Button>
  );
}

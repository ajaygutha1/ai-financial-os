"use client";

import { AnalyticsCard } from "@/components/dashboard/analytics-card";
import { useDebtPayoff } from "@/hooks/use-debt-payoff";
import { formatCurrency } from "@/lib/format";

export function DebtPayoffCard({ className }: { className?: string }) {
  const { data, isPending, isError } = useDebtPayoff(6);

  return (
    <AnalyticsCard
      title="Debt payoff"
      className={className}
      isPending={isPending}
      isError={isError}
    >
      {data ? (
        data.accounts.length === 0 ? (
          <p className="text-sm text-muted-foreground">No credit cards or loans tracked.</p>
        ) : (
          <ul className="divide-y divide-border">
            {data.accounts.map((account) => (
              <li key={account.account_id} className="space-y-1 py-2.5 first:pt-0 last:pb-0">
                <div className="flex items-center justify-between">
                  <span className="text-sm">{account.account_name}</span>
                  <span className="text-sm font-medium tabular-nums">
                    {formatCurrency(account.current_balance)}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">
                  {account.on_track && account.months_to_payoff
                    ? `On track: ~${Math.ceil(Number.parseFloat(account.months_to_payoff))} months at current pace`
                    : "Not currently paying down faster than new charges"}
                </p>
              </li>
            ))}
          </ul>
        )
      ) : null}
    </AnalyticsCard>
  );
}

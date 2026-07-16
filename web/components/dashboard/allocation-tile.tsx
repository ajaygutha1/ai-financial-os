"use client";

import { AnalyticsCard } from "@/components/dashboard/analytics-card";
import { useNetWorth } from "@/hooks/use-net-worth";
import { formatCurrency } from "@/lib/format";

const ACCOUNT_TYPE_LABEL: Record<string, string> = {
  checking: "Checking",
  savings: "Savings",
  credit_card: "Credit card",
  investment: "Investment",
  crypto: "Crypto",
  loan: "Loan",
  mortgage: "Mortgage",
  retirement: "Retirement",
  other: "Other",
};

export function AllocationTile({ className }: { className?: string }) {
  const { data, isPending, isError } = useNetWorth();

  const entries = data
    ? Object.entries(data.by_account_type)
        .map(([type, amount]) => ({ type, amount: Number.parseFloat(amount) }))
        .filter((e) => e.amount !== 0)
        .sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount))
    : [];
  const total = entries.reduce((sum, e) => sum + Math.abs(e.amount), 0);

  return (
    <AnalyticsCard
      title="Allocation"
      className={className}
      isPending={isPending}
      isError={isError}
    >
      {entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No accounts connected yet -- allocation shows once balances exist.
        </p>
      ) : (
        <ul className="space-y-3">
          {entries.map((e) => {
            const pct = total > 0 ? Math.round((Math.abs(e.amount) / total) * 100) : 0;
            return (
              <li key={e.type} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span>{ACCOUNT_TYPE_LABEL[e.type] ?? e.type}</span>
                  <span className="tabular-nums text-muted-foreground">
                    {formatCurrency(e.amount)} · {pct}%
                  </span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </AnalyticsCard>
  );
}

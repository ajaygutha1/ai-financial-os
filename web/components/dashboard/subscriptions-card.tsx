"use client";

import { AnalyticsCard } from "@/components/dashboard/analytics-card";
import { Badge } from "@/components/ui/badge";
import { useSubscriptions } from "@/hooks/use-subscriptions";
import { formatCurrency } from "@/lib/format";

export function SubscriptionsCard({ className }: { className?: string }) {
  const { data, isPending, isError } = useSubscriptions(6);

  return (
    <AnalyticsCard
      title="Subscriptions"
      className={className}
      isPending={isPending}
      isError={isError}
    >
      {data ? (
        data.subscriptions.length === 0 ? (
          <p className="text-sm text-muted-foreground">No recurring charges detected yet.</p>
        ) : (
          <div className="space-y-3">
            <ul className="divide-y divide-border">
              {data.subscriptions.slice(0, 5).map((sub) => (
                <li
                  key={sub.merchant}
                  className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm">{sub.merchant}</span>
                    <Badge variant="outline">{sub.cadence}</Badge>
                  </div>
                  <span className="text-sm font-medium tabular-nums">
                    {formatCurrency(sub.average_amount)}
                  </span>
                </li>
              ))}
            </ul>
            <p className="border-t border-border pt-3 text-xs text-muted-foreground">
              Est. {formatCurrency(data.estimated_monthly_total)}/mo in monthly subscriptions
            </p>
          </div>
        )
      ) : null}
    </AnalyticsCard>
  );
}

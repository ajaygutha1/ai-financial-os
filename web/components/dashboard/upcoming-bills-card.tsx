"use client";

import { AnalyticsCard } from "@/components/dashboard/analytics-card";
import { Badge } from "@/components/ui/badge";
import { useSubscriptions } from "@/hooks/use-subscriptions";
import { formatCurrency, formatDate } from "@/lib/format";

const DUE_SOON_DAYS = 7;

function daysUntil(dateStr: string): number {
  const target = new Date(dateStr);
  const now = new Date();
  target.setHours(0, 0, 0, 0);
  now.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - now.getTime()) / 86_400_000);
}

export function UpcomingBillsCard({ className }: { className?: string }) {
  const { data, isPending, isError } = useSubscriptions(6);

  const upcoming = data
    ? [...data.subscriptions].sort(
        (a, b) => new Date(a.next_expected_date).getTime() - new Date(b.next_expected_date).getTime()
      )
    : [];

  return (
    <AnalyticsCard
      title="Upcoming bills"
      className={className}
      isPending={isPending}
      isError={isError}
    >
      {upcoming.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No recurring charges detected yet, so nothing to project as upcoming.
        </p>
      ) : (
        <ul className="divide-y divide-border">
          {upcoming.slice(0, 5).map((sub) => {
            const days = daysUntil(sub.next_expected_date);
            const dueSoon = days <= DUE_SOON_DAYS;
            return (
              <li
                key={sub.merchant}
                className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0"
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm">{sub.merchant}</span>
                  {dueSoon && (
                    <Badge variant={days < 0 ? "destructive" : "outline"}>
                      {days < 0 ? "Overdue" : days === 0 ? "Today" : `${days}d`}
                    </Badge>
                  )}
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium tabular-nums">
                    {formatCurrency(sub.average_amount)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatDate(sub.next_expected_date)}
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </AnalyticsCard>
  );
}

"use client";

import { motion } from "framer-motion";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useNetWorth } from "@/hooks/use-net-worth";
import { cn } from "@/lib/utils";
import { formatCurrency } from "@/lib/format";

export function NetWorthTile({ className }: { className?: string }) {
  const { data, isPending, isError } = useNetWorth();

  if (isPending) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="text-sm font-medium text-muted-foreground">Net worth</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-10 w-48" />
        </CardContent>
      </Card>
    );
  }

  if (isError || !data) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="text-sm font-medium text-muted-foreground">Net worth</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">Couldn&apos;t load net worth.</p>
        </CardContent>
      </Card>
    );
  }

  const netWorth = Number.parseFloat(data.net_worth);
  const isPositive = netWorth >= 0;

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">Net worth</CardTitle>
      </CardHeader>
      <CardContent>
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-baseline gap-2.5"
        >
          <span className="font-heading text-4xl tabular-nums tracking-tight">
            {formatCurrency(data.net_worth)}
          </span>
          <span
            className={cn(
              "flex items-center gap-0.5 text-sm font-medium",
              isPositive ? "text-foreground" : "text-muted-foreground"
            )}
          >
            {isPositive ? (
              <ArrowUpRight className="size-4" />
            ) : (
              <ArrowDownRight className="size-4" />
            )}
          </span>
        </motion.div>
        <div className="mt-4 flex gap-6 border-t border-border pt-3 text-xs text-muted-foreground">
          <span>
            Assets <span className="text-foreground">{formatCurrency(data.assets_total)}</span>
          </span>
          <span>
            Liabilities{" "}
            <span className="text-foreground">{formatCurrency(data.liabilities_total)}</span>
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

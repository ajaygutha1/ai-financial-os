"use client";

import { motion } from "framer-motion";
import { TrendingDown, TrendingUp } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useNetWorth } from "@/hooks/use-net-worth";
import { formatCurrency } from "@/lib/format";

export function NetWorthTile() {
  const { data, isPending, isError } = useNetWorth();

  if (isPending) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium text-muted-foreground">Net Worth</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-9 w-40" />
        </CardContent>
      </Card>
    );
  }

  if (isError || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium text-muted-foreground">Net Worth</CardTitle>
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
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">Net Worth</CardTitle>
      </CardHeader>
      <CardContent>
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-2"
        >
          <span className="text-3xl font-semibold tracking-tight">
            {formatCurrency(data.net_worth)}
          </span>
          {isPositive ? (
            <TrendingUp className="size-5 text-emerald-500" />
          ) : (
            <TrendingDown className="size-5 text-red-500" />
          )}
        </motion.div>
        <div className="mt-3 flex gap-4 text-xs text-muted-foreground">
          <span>Assets: {formatCurrency(data.assets_total)}</span>
          <span>Liabilities: {formatCurrency(data.liabilities_total)}</span>
        </div>
      </CardContent>
    </Card>
  );
}

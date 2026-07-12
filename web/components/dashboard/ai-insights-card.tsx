"use client";

import { Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useFinancialAdvice } from "@/hooks/use-financial-advice";
import { useRecommendations } from "@/hooks/use-recommendations";
import { ApiError } from "@/lib/api-client";

const CATEGORY_LABEL: Record<string, string> = {
  emergency_fund: "Emergency fund",
  debt: "Debt",
  savings: "Savings",
  spending: "Spending",
  subscriptions: "Subscriptions",
  general: "General",
};

export function AIInsightsCard({ className }: { className?: string }) {
  const { data, isPending, isError } = useRecommendations();
  const advice = useFinancialAdvice();

  const handleGetAdvice = () => {
    advice.mutate(undefined, {
      onError: (error) => {
        toast.error(
          error instanceof ApiError ? error.message : "Couldn't get financial advice."
        );
      },
    });
  };

  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-sm font-medium text-muted-foreground">AI insights</CardTitle>
        <Button size="sm" variant="outline" onClick={handleGetAdvice} disabled={advice.isPending}>
          <Sparkles className="size-3.5" />
          {advice.isPending ? "Analyzing..." : "Get advice"}
        </Button>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <Skeleton className="h-10 w-full" />
        ) : isError ? (
          <p className="text-sm text-destructive">Couldn&apos;t load recommendations.</p>
        ) : data && data.length > 0 ? (
          <ul className="space-y-4">
            {data.map((rec) => (
              <li
                key={rec.id}
                className="space-y-1 border-b border-border pb-4 last:border-0 last:pb-0"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium">{rec.title}</span>
                  <Badge variant="outline">
                    {CATEGORY_LABEL[rec.category ?? "general"] ?? rec.category}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">{rec.explanation}</p>
                <p className="text-xs text-muted-foreground">
                  Confidence: {Math.round(Number.parseFloat(rec.confidence) * 100)}%
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            No AI insights yet. Click &quot;Get advice&quot; for an explainable, cited financial
            health check based on your real accounts and transactions.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

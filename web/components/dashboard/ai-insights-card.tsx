"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  budgeting: "Budgeting",
  retirement: "Retirement",
  capital_gains: "Capital gains",
  income: "Income",
  deductions: "Deductions",
  duplicate_charge: "Duplicate charge",
  unusual_amount: "Unusual amount",
  new_merchant: "New merchant",
  allocation: "Allocation",
  diversification: "Diversification",
  concentration: "Concentration",
  risk: "Risk",
  general: "General",
};

// slug (URL) -> agent_name (stored on each recommendation) -> display label.
// A static config array, not a GET /agents call -- the set of agents is
// fixed at deploy time, not user data worth a network round trip.
const AGENTS = [
  { slug: "financial-advisor", agentName: "financial_advisor", label: "Financial Advisor" },
  { slug: "expense-analyst", agentName: "expense_analyst", label: "Expense Analyst" },
  { slug: "budget-coach", agentName: "budget_coach", label: "Budget Coach" },
  { slug: "retirement-planner", agentName: "retirement_planner", label: "Retirement Planner" },
  { slug: "tax-advisor", agentName: "tax_advisor", label: "Tax Advisor" },
  { slug: "fraud-detection", agentName: "fraud_detection", label: "Fraud Detection" },
  { slug: "investment-analyst", agentName: "investment_analyst", label: "Investment Analyst" },
  {
    slug: "portfolio-risk-analyst",
    agentName: "portfolio_risk_analyst",
    label: "Portfolio Risk Analyst",
  },
] as const;

const AGENT_LABEL_BY_NAME: Record<string, string> = Object.fromEntries(
  AGENTS.map((a) => [a.agentName, a.label])
);

function citationList(citations: Record<string, unknown>, key: string): string[] {
  const value = citations[key];
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

export function AIInsightsCard({ className }: { className?: string }) {
  const { data, isPending, isError } = useRecommendations();
  const [agentSlug, setAgentSlug] = useState<string>(AGENTS[0].slug);
  const advice = useFinancialAdvice(agentSlug);

  const handleGetAdvice = () => {
    advice.mutate(undefined, {
      onError: (error) => {
        toast.error(
          error instanceof ApiError ? error.message : "Couldn't get advice from this agent."
        );
      },
    });
  };

  return (
    <Card className={className}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-sm font-medium text-muted-foreground">AI insights</CardTitle>
        <div className="flex items-center gap-2">
          <Select value={agentSlug} onValueChange={(value) => value && setAgentSlug(value)}>
            <SelectTrigger size="sm" className="w-[170px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {AGENTS.map((agent) => (
                <SelectItem key={agent.slug} value={agent.slug}>
                  {agent.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button size="sm" variant="outline" onClick={handleGetAdvice} disabled={advice.isPending}>
            <Sparkles className="size-3.5" />
            {advice.isPending ? "Analyzing..." : "Get advice"}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <Skeleton className="h-10 w-full" />
        ) : isError ? (
          <p className="text-sm text-destructive">Couldn&apos;t load recommendations.</p>
        ) : data && data.length > 0 ? (
          <ul className="space-y-4">
            {data.map((rec) => {
              const metricsUsed = citationList(rec.citations, "metrics_used");
              const sourcesUsed = citationList(rec.citations, "sources_used");
              return (
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
                  <p className="text-xs text-muted-foreground">
                    {AGENT_LABEL_BY_NAME[rec.agent_name] ?? rec.agent_name}
                  </p>
                  <p className="text-sm text-muted-foreground">{rec.explanation}</p>
                  <p className="text-xs text-muted-foreground">
                    Confidence: {Math.round(Number.parseFloat(rec.confidence) * 100)}%
                  </p>
                  {metricsUsed.length > 0 && (
                    <p className="text-xs text-muted-foreground">
                      Based on: {metricsUsed.join(", ")}
                    </p>
                  )}
                  {sourcesUsed.length > 0 && (
                    <p className="text-xs text-muted-foreground">
                      Sources: {sourcesUsed.join(", ")}
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            No AI insights yet. Choose an agent and click &quot;Get advice&quot; for an
            explainable, cited analysis based on your real accounts and transactions.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

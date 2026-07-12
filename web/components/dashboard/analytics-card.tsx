"use client";

import type { ReactNode } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface AnalyticsCardProps {
  title: string;
  className?: string;
  isPending: boolean;
  isError: boolean;
  errorMessage?: string;
  children: ReactNode;
}

export function AnalyticsCard({
  title,
  className,
  isPending,
  isError,
  errorMessage = "Couldn't load this data.",
  children,
}: AnalyticsCardProps) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {isPending ? (
          <Skeleton className="h-10 w-full" />
        ) : isError ? (
          <p className="text-sm text-destructive">{errorMessage}</p>
        ) : (
          children
        )}
      </CardContent>
    </Card>
  );
}

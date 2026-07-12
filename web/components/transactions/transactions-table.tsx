"use client";

import { useState } from "react";
import { Inbox } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useTransactions } from "@/hooks/use-transactions";
import { formatCurrency, formatDate } from "@/lib/format";

const PAGE_SIZE = 20;

export function TransactionsTable() {
  const [page, setPage] = useState(1);
  const { data, isPending, isPlaceholderData } = useTransactions({ page, pageSize: PAGE_SIZE });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  if (isPending) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  if (!data || data.items.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-border p-12 text-center">
        <Inbox className="size-8 text-muted-foreground" />
        <p className="text-sm font-medium">No transactions yet</p>
        <p className="text-sm text-muted-foreground">
          Import a CSV to bring in your history.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-xl border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Merchant</TableHead>
              <TableHead>Category</TableHead>
              <TableHead className="text-right">Amount</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.map((transaction) => {
              const amount = Number.parseFloat(transaction.amount);
              const isCredit = amount >= 0;
              return (
                <TableRow key={transaction.id}>
                  <TableCell className="whitespace-nowrap text-muted-foreground">
                    {formatDate(transaction.posted_at)}
                  </TableCell>
                  <TableCell className="font-medium">
                    {transaction.merchant_normalized ?? transaction.description ?? "--"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {transaction.category ?? "Uncategorized"}
                  </TableCell>
                  <TableCell className="text-right font-medium tabular-nums">
                    {isCredit ? "+" : ""}
                    {formatCurrency(transaction.amount)}
                  </TableCell>
                  <TableCell>
                    {transaction.is_duplicate_of && (
                      <Badge variant="secondary">Duplicate</Badge>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          Page {page} of {totalPages} &middot; {data.total} transactions
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages || isPlaceholderData}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}

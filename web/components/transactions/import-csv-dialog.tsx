"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAccounts } from "@/hooks/use-accounts";
import { useCsvImport } from "@/hooks/use-csv-import";
import { ApiError } from "@/lib/api-client";

export function ImportCsvDialog() {
  const [open, setOpen] = useState(false);
  const [accountId, setAccountId] = useState<string>("");
  const [debitPositive, setDebitPositive] = useState(false);
  const [file, setFile] = useState<File | null>(null);

  const { data: accounts } = useAccounts();
  const csvImport = useCsvImport();

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!accountId || !file) return;

    try {
      const result = await csvImport.mutateAsync({ accountId, file, debitPositive });
      toast.success(
        `Imported ${result.imported_count} transactions` +
          (result.duplicate_count ? ` (${result.duplicate_count} duplicates flagged)` : "") +
          (result.error_count ? ` -- ${result.error_count} rows had errors` : "")
      );
      setOpen(false);
      setFile(null);
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "CSV import failed.");
    }
  };

  const hasAccounts = (accounts?.length ?? 0) > 0;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button />}>Import CSV</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Import transactions from CSV</DialogTitle>
          <DialogDescription>
            Upload a bank export with date, description, and amount columns.
          </DialogDescription>
        </DialogHeader>

        {!hasAccounts ? (
          <p className="text-sm text-muted-foreground">
            Create an account first, then come back here to import transactions.
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="import-account">Account</Label>
              <Select
                value={accountId}
                onValueChange={(value) => value && setAccountId(value)}
              >
                <SelectTrigger id="import-account" className="w-full">
                  <SelectValue placeholder="Select an account" />
                </SelectTrigger>
                <SelectContent>
                  {accounts?.map((account) => (
                    <SelectItem key={account.id} value={account.id}>
                      {account.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="import-file">CSV file</Label>
              <input
                id="import-file"
                type="file"
                accept=".csv,text/csv"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                className="block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-secondary file:px-3 file:py-1.5 file:text-sm file:font-medium"
                required
              />
            </div>

            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={debitPositive}
                onCheckedChange={(checked) => setDebitPositive(checked === true)}
              />
              This file represents outflows as positive amounts
            </label>

            <DialogFooter>
              <Button type="submit" disabled={csvImport.isPending || !accountId || !file}>
                {csvImport.isPending ? "Importing..." : "Import"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAccounts } from "@/hooks/use-accounts";
import { useCreateGoal } from "@/hooks/use-goals";
import { ApiError } from "@/lib/api-client";

const NO_LINKED_ACCOUNT = "none";

export function NewGoalDialog() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [targetAmount, setTargetAmount] = useState("");
  const [linkedAccountId, setLinkedAccountId] = useState(NO_LINKED_ACCOUNT);
  const [manualCurrentAmount, setManualCurrentAmount] = useState("0");
  const { data: accounts } = useAccounts();
  const createGoal = useCreateGoal();

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await createGoal.mutateAsync({
        name,
        target_amount: targetAmount,
        linked_account_id: linkedAccountId === NO_LINKED_ACCOUNT ? null : linkedAccountId,
        manual_current_amount: manualCurrentAmount || "0",
      });
      toast.success("Goal created.");
      setOpen(false);
      setName("");
      setTargetAmount("");
      setLinkedAccountId(NO_LINKED_ACCOUNT);
      setManualCurrentAmount("0");
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to create goal.");
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="outline" size="sm" className="w-full" />}>
        New goal
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New goal</DialogTitle>
          <DialogDescription>
            Track progress toward a savings target, either against a real account&apos;s
            balance or a manually-updated amount.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="goal-name">Name</Label>
            <Input
              id="goal-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. Emergency fund"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="goal-target">Target amount</Label>
            <Input
              id="goal-target"
              type="number"
              step="0.01"
              min="0.01"
              value={targetAmount}
              onChange={(event) => setTargetAmount(event.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="goal-account">Track against</Label>
            <Select
              value={linkedAccountId}
              onValueChange={(value) => value && setLinkedAccountId(value)}
            >
              <SelectTrigger id="goal-account" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_LINKED_ACCOUNT}>Manual amount</SelectItem>
                {accounts?.map((account) => (
                  <SelectItem key={account.id} value={account.id}>
                    {account.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {linkedAccountId === NO_LINKED_ACCOUNT && (
            <div className="space-y-2">
              <Label htmlFor="goal-current">Current amount</Label>
              <Input
                id="goal-current"
                type="number"
                step="0.01"
                value={manualCurrentAmount}
                onChange={(event) => setManualCurrentAmount(event.target.value)}
              />
            </div>
          )}
          <DialogFooter>
            <Button type="submit" disabled={createGoal.isPending}>
              {createGoal.isPending ? "Creating..." : "Create goal"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

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
import { useCategories, useSetBudgetTarget } from "@/hooks/use-budget";
import { ApiError } from "@/lib/api-client";

export function SetBudgetDialog() {
  const [open, setOpen] = useState(false);
  const [categoryId, setCategoryId] = useState("");
  const [amount, setAmount] = useState("");
  const { data: categories } = useCategories();
  const setBudgetTarget = useSetBudgetTarget();

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await setBudgetTarget.mutateAsync({
        category_id: categoryId,
        monthly_target_amount: amount,
      });
      toast.success("Budget target set.");
      setOpen(false);
      setCategoryId("");
      setAmount("");
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Failed to set budget target.");
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="outline" size="sm" className="w-full" />}>
        Set budget
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Set a monthly budget</DialogTitle>
          <DialogDescription>
            Setting a target for a category you&apos;ve already budgeted replaces it.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="budget-category">Category</Label>
            <Select value={categoryId} onValueChange={(value) => value && setCategoryId(value)}>
              <SelectTrigger id="budget-category" className="w-full">
                <SelectValue placeholder="Choose a category" />
              </SelectTrigger>
              <SelectContent>
                {categories?.map((category) => (
                  <SelectItem key={category.id} value={category.id}>
                    {category.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="budget-amount">Monthly target</Label>
            <Input
              id="budget-amount"
              type="number"
              step="0.01"
              min="0.01"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              required
            />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={setBudgetTarget.isPending || !categoryId}>
              {setBudgetTarget.isPending ? "Saving..." : "Set budget"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

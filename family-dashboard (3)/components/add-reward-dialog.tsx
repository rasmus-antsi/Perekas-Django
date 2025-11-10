"use client"

import type React from "react"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

interface AddRewardDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onAddReward: (title: string, cost: number) => void
}

export function AddRewardDialog({ open, onOpenChange, onAddReward }: AddRewardDialogProps) {
  const [title, setTitle] = useState("")
  const [cost, setCost] = useState("30")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (title) {
      onAddReward(title, Number.parseInt(cost))
      setTitle("")
      setCost("30")
      onOpenChange(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Add New Reward</DialogTitle>
            <DialogDescription>Create a new reward that can be claimed with points.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="reward-title">Reward Title</Label>
              <Input
                id="reward-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., Extra screen time"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="cost">Point Cost</Label>
              <Input id="cost" type="number" value={cost} onChange={(e) => setCost(e.target.value)} min="1" />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit">Add Reward</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

interface AddTaskDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onAddTask: (title: string, assignee: string, points: number, category: string) => void
}

export function AddTaskDialog({ open, onOpenChange, onAddTask }: AddTaskDialogProps) {
  const [title, setTitle] = useState("")
  const [assignee, setAssignee] = useState("")
  const [points, setPoints] = useState("10")
  const [category, setCategory] = useState("")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (title && assignee) {
      onAddTask(title, assignee, Number.parseInt(points), category)
      setTitle("")
      setAssignee("")
      setPoints("10")
      setCategory("")
      onOpenChange(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Add New Task</DialogTitle>
            <DialogDescription>Create a new task and assign it to a family member.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="title">Task Title</Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., Clean your room"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="category">Category</Label>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger id="category">
                  <SelectValue placeholder="Select category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Chores">Chores</SelectItem>
                  <SelectItem value="Homework">Homework</SelectItem>
                  <SelectItem value="Exercise">Exercise</SelectItem>
                  <SelectItem value="Other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="assignee">Assign To</Label>
              <Select value={assignee} onValueChange={setAssignee}>
                <SelectTrigger id="assignee">
                  <SelectValue placeholder="Select family member" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Emma">Emma</SelectItem>
                  <SelectItem value="Lucas">Lucas</SelectItem>
                  <SelectItem value="Mom">Mom</SelectItem>
                  <SelectItem value="Dad">Dad</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="points">Points</Label>
              <Input id="points" type="number" value={points} onChange={(e) => setPoints(e.target.value)} min="1" />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit">Add Task</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

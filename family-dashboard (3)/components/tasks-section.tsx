"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Plus } from "lucide-react"
import { AddTaskDialog } from "@/components/add-task-dialog"

interface Task {
  id: string
  title: string
  assignee: string
  points: number
  completed: boolean
}

export function TasksSection() {
  const [tasks, setTasks] = useState<Task[]>([
    { id: "1", title: "Clean your room", assignee: "Emma", points: 10, completed: false },
    { id: "2", title: "Do homework", assignee: "Lucas", points: 15, completed: true },
    { id: "3", title: "Walk the dog", assignee: "Emma", points: 10, completed: false },
    { id: "4", title: "Set the table", assignee: "Lucas", points: 5, completed: false },
  ])
  const [dialogOpen, setDialogOpen] = useState(false)

  const toggleTask = (id: string) => {
    setTasks(tasks.map((task) => (task.id === id ? { ...task, completed: !task.completed } : task)))
  }

  const addTask = (title: string, assignee: string, points: number) => {
    const newTask: Task = {
      id: Date.now().toString(),
      title,
      assignee,
      points,
      completed: false,
    }
    setTasks([...tasks, newTask])
  }

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
          <CardTitle className="text-xl font-semibold">Tasks</CardTitle>
          <Button size="sm" onClick={() => setDialogOpen(true)}>
            <Plus className="mr-1.5 h-4 w-4" />
            Add Task
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {tasks.map((task) => (
            <div
              key={task.id}
              className="flex items-center gap-3 rounded-lg border border-border bg-card p-4 transition-colors hover:bg-secondary/50"
            >
              <Checkbox checked={task.completed} onCheckedChange={() => toggleTask(task.id)} className="h-5 w-5" />
              <div className="flex-1 space-y-0.5">
                <p
                  className={`font-medium leading-none ${task.completed ? "text-muted-foreground line-through" : "text-foreground"}`}
                >
                  {task.title}
                </p>
                <p className="text-sm text-muted-foreground">{task.assignee}</p>
              </div>
              <div className="flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1">
                <span className="text-sm font-semibold text-primary">{task.points}</span>
                <span className="text-xs text-primary">pts</span>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <AddTaskDialog open={dialogOpen} onOpenChange={setDialogOpen} onAddTask={addTask} />
    </>
  )
}

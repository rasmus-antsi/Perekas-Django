"use client"

import { useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Plus, CheckCircle2, Circle, Star, Clock } from "lucide-react"
import { AddTaskDialog } from "@/components/add-task-dialog"

interface Task {
  id: string
  title: string
  assignedTo: string
  points: number
  dueDate: string
  completed: boolean
  priority: "low" | "medium" | "high"
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([
    {
      id: "1",
      title: "Clean the kitchen",
      assignedTo: "Sarah",
      points: 50,
      dueDate: "Today",
      completed: false,
      priority: "high",
    },
    {
      id: "2",
      title: "Walk the dog",
      assignedTo: "Mike",
      points: 30,
      dueDate: "Today",
      completed: false,
      priority: "medium",
    },
    {
      id: "3",
      title: "Do homework",
      assignedTo: "Emma",
      points: 100,
      dueDate: "Tomorrow",
      completed: false,
      priority: "high",
    },
    {
      id: "4",
      title: "Take out trash",
      assignedTo: "Dad",
      points: 20,
      dueDate: "Today",
      completed: true,
      priority: "low",
    },
  ])
  const [dialogOpen, setDialogOpen] = useState(false)

  const toggleTask = (id: string) => {
    setTasks(tasks.map((task) => (task.id === id ? { ...task, completed: !task.completed } : task)))
  }

  const addTask = (newTask: Omit<Task, "id" | "completed">) => {
    setTasks([...tasks, { ...newTask, id: Date.now().toString(), completed: false }])
    setDialogOpen(false)
  }

  const activeTasks = tasks.filter((t) => !t.completed)
  const completedTasks = tasks.filter((t) => t.completed)

  const priorityColors = {
    high: "border-destructive/50 bg-destructive/5",
    medium: "border-warning/50 bg-warning/5",
    low: "border-success/50 bg-success/5",
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-bold tracking-tight text-balance mb-2">Family Tasks</h1>
          <p className="text-muted-foreground text-lg">
            {activeTasks.length} active tasks, {completedTasks.length} completed
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)} size="lg" className="gap-2">
          <Plus className="h-5 w-5" />
          Add Task
        </Button>
      </div>

      {/* Active Tasks */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold tracking-tight mb-4 flex items-center gap-2">
          <Circle className="h-6 w-6 text-primary" />
          Active Tasks
        </h2>
        <div className="grid gap-4">
          {activeTasks.map((task) => (
            <Card
              key={task.id}
              className={`p-6 border ${priorityColors[task.priority]} backdrop-blur-sm hover:bg-card/80 transition-all duration-300`}
            >
              <div className="flex items-start gap-4">
                <button
                  onClick={() => toggleTask(task.id)}
                  className="mt-1 text-muted-foreground hover:text-primary transition-colors"
                >
                  <Circle className="h-6 w-6" />
                </button>
                <div className="flex-1">
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="text-xl font-semibold">{task.title}</h3>
                    <div className="flex items-center gap-2 bg-primary/10 text-primary px-3 py-1 rounded-full">
                      <Star className="h-4 w-4 fill-current" />
                      <span className="font-semibold">{task.points}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    <span className="font-medium">Assigned to: {task.assignedTo}</span>
                    <span className="flex items-center gap-1">
                      <Clock className="h-4 w-4" />
                      {task.dueDate}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        task.priority === "high"
                          ? "bg-destructive/20 text-destructive"
                          : task.priority === "medium"
                            ? "bg-warning/20 text-warning"
                            : "bg-success/20 text-success"
                      }`}
                    >
                      {task.priority}
                    </span>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>

      {/* Completed Tasks */}
      {completedTasks.length > 0 && (
        <div>
          <h2 className="text-2xl font-bold tracking-tight mb-4 flex items-center gap-2">
            <CheckCircle2 className="h-6 w-6 text-success" />
            Completed
          </h2>
          <div className="grid gap-4">
            {completedTasks.map((task) => (
              <Card key={task.id} className="p-6 border-border/30 bg-card/30 backdrop-blur-sm opacity-60">
                <div className="flex items-start gap-4">
                  <button onClick={() => toggleTask(task.id)} className="mt-1 text-success">
                    <CheckCircle2 className="h-6 w-6" />
                  </button>
                  <div className="flex-1">
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="text-xl font-semibold line-through">{task.title}</h3>
                      <div className="flex items-center gap-2 bg-success/10 text-success px-3 py-1 rounded-full">
                        <Star className="h-4 w-4 fill-current" />
                        <span className="font-semibold">{task.points}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 text-sm text-muted-foreground">
                      <span className="font-medium">Completed by: {task.assignedTo}</span>
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      <AddTaskDialog open={dialogOpen} onOpenChange={setDialogOpen} onAdd={addTask} />
    </div>
  )
}

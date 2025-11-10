"use client"

import type React from "react"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Checkbox } from "@/components/ui/checkbox"
import { Plus, X } from "lucide-react"

interface ShoppingItem {
  id: string
  name: string
  checked: boolean
}

export function ShoppingListSection() {
  const [items, setItems] = useState<ShoppingItem[]>([
    { id: "1", name: "Milk", checked: false },
    { id: "2", name: "Bread", checked: false },
    { id: "3", name: "Eggs", checked: true },
    { id: "4", name: "Apples", checked: false },
    { id: "5", name: "Chicken", checked: false },
  ])
  const [newItem, setNewItem] = useState("")

  const toggleItem = (id: string) => {
    setItems(items.map((item) => (item.id === id ? { ...item, checked: !item.checked } : item)))
  }

  const addItem = (e: React.FormEvent) => {
    e.preventDefault()
    if (newItem.trim()) {
      const item: ShoppingItem = {
        id: Date.now().toString(),
        name: newItem.trim(),
        checked: false,
      }
      setItems([...items, item])
      setNewItem("")
    }
  }

  const removeItem = (id: string) => {
    setItems(items.filter((item) => item.id !== id))
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl font-semibold">Shopping List</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={addItem} className="flex gap-2">
          <Input
            value={newItem}
            onChange={(e) => setNewItem(e.target.value)}
            placeholder="Add item..."
            className="flex-1"
          />
          <Button type="submit" size="icon">
            <Plus className="h-4 w-4" />
          </Button>
        </form>

        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => (
            <div
              key={item.id}
              className="flex items-center gap-3 rounded-lg border border-border bg-card p-3 transition-colors hover:bg-secondary/50"
            >
              <Checkbox checked={item.checked} onCheckedChange={() => toggleItem(item.id)} className="h-5 w-5" />
              <span
                className={`flex-1 text-sm font-medium ${item.checked ? "text-muted-foreground line-through" : "text-foreground"}`}
              >
                {item.name}
              </span>
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => removeItem(item.id)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

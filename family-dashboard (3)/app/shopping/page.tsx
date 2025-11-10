"use client"

import { useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Plus, Check, X, ShoppingCart } from "lucide-react"

interface ShoppingItem {
  id: string
  name: string
  addedBy: string
  checked: boolean
}

export default function ShoppingPage() {
  const [items, setItems] = useState<ShoppingItem[]>([
    { id: "1", name: "Milk", addedBy: "Mom", checked: false },
    { id: "2", name: "Bread", addedBy: "Dad", checked: false },
    { id: "3", name: "Eggs", addedBy: "Sarah", checked: true },
    { id: "4", name: "Apples", addedBy: "Emma", checked: false },
  ])
  const [newItem, setNewItem] = useState("")

  const addItem = () => {
    if (newItem.trim()) {
      setItems([
        ...items,
        {
          id: Date.now().toString(),
          name: newItem,
          addedBy: "You",
          checked: false,
        },
      ])
      setNewItem("")
    }
  }

  const toggleItem = (id: string) => {
    setItems(items.map((item) => (item.id === id ? { ...item, checked: !item.checked } : item)))
  }

  const removeItem = (id: string) => {
    setItems(items.filter((item) => item.id !== id))
  }

  const activeItems = items.filter((i) => !i.checked)
  const checkedItems = items.filter((i) => i.checked)

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-4xl font-bold tracking-tight text-balance mb-2">Shopping List</h1>
        <p className="text-muted-foreground text-lg">
          {activeItems.length} items to buy, {checkedItems.length} in cart
        </p>
      </div>

      {/* Add Item Card */}
      <Card className="p-6 mb-8 border-secondary/50 bg-gradient-to-br from-secondary/10 to-primary/5 backdrop-blur-sm">
        <div className="flex gap-3">
          <Input
            placeholder="Add new item..."
            value={newItem}
            onChange={(e) => setNewItem(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addItem()}
            className="flex-1 bg-background/50 border-border/50"
          />
          <Button onClick={addItem} size="lg" className="gap-2">
            <Plus className="h-5 w-5" />
            Add
          </Button>
        </div>
      </Card>

      {/* Active Items */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold tracking-tight mb-4 flex items-center gap-2">
          <ShoppingCart className="h-6 w-6 text-secondary" />
          Need to Buy
        </h2>
        <div className="grid gap-3">
          {activeItems.map((item) => (
            <Card
              key={item.id}
              className="p-4 border-border/50 bg-card/50 backdrop-blur-sm hover:bg-card/80 transition-all duration-300"
            >
              <div className="flex items-center gap-4">
                <button
                  onClick={() => toggleItem(item.id)}
                  className="text-muted-foreground hover:text-secondary transition-colors"
                >
                  <div className="h-6 w-6 rounded-full border-2 border-current" />
                </button>
                <div className="flex-1">
                  <p className="font-semibold text-lg">{item.name}</p>
                  <p className="text-sm text-muted-foreground">Added by {item.addedBy}</p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => removeItem(item.id)}
                  className="text-muted-foreground hover:text-destructive"
                >
                  <X className="h-5 w-5" />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      </div>

      {/* Checked Items */}
      {checkedItems.length > 0 && (
        <div>
          <h2 className="text-2xl font-bold tracking-tight mb-4 flex items-center gap-2">
            <Check className="h-6 w-6 text-success" />
            In Cart
          </h2>
          <div className="grid gap-3">
            {checkedItems.map((item) => (
              <Card key={item.id} className="p-4 border-success/30 bg-success/5 backdrop-blur-sm opacity-75">
                <div className="flex items-center gap-4">
                  <button onClick={() => toggleItem(item.id)} className="text-success">
                    <div className="h-6 w-6 rounded-full bg-success flex items-center justify-center">
                      <Check className="h-4 w-4 text-success-foreground" />
                    </div>
                  </button>
                  <div className="flex-1">
                    <p className="font-semibold text-lg line-through">{item.name}</p>
                    <p className="text-sm text-muted-foreground">Added by {item.addedBy}</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => removeItem(item.id)}
                    className="text-muted-foreground hover:text-destructive"
                  >
                    <X className="h-5 w-5" />
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

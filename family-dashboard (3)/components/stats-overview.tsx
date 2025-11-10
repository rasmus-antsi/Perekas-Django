import { Card } from "@/components/ui/card"
import { CheckCircle2, Trophy, ShoppingCart } from "lucide-react"

export function StatsOverview() {
  const stats = [
    {
      label: "Tasks Completed",
      value: "24",
      subtext: "This week",
      icon: CheckCircle2,
      color: "text-primary",
    },
    {
      label: "Points Earned",
      value: "340",
      subtext: "Total balance",
      icon: Trophy,
      color: "text-accent",
    },
    {
      label: "Shopping Items",
      value: "8",
      subtext: "Pending",
      icon: ShoppingCart,
      color: "text-chart-3",
    },
  ]

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {stats.map((stat) => (
        <Card key={stat.label} className="p-6">
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">{stat.label}</p>
              <p className="text-3xl font-semibold tracking-tight text-foreground">{stat.value}</p>
              <p className="text-xs text-muted-foreground">{stat.subtext}</p>
            </div>
            <div className={`rounded-lg bg-secondary p-2.5 ${stat.color}`}>
              <stat.icon className="h-5 w-5" />
            </div>
          </div>
        </Card>
      ))}
    </div>
  )
}

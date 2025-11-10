import { TrendingUp, Target, ShoppingCart, Trophy, CheckCircle2, Clock, Users, Sparkles } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import Link from "next/link"

export default function DashboardPage() {
  const stats = [
    {
      title: "Active Tasks",
      value: "12",
      change: "+3 this week",
      icon: Target,
      color: "text-primary",
      bgColor: "bg-primary/10",
      borderColor: "border-primary/20",
    },
    {
      title: "Points Earned",
      value: "2,450",
      change: "+450 this month",
      icon: TrendingUp,
      color: "text-success",
      bgColor: "bg-success/10",
      borderColor: "border-success/20",
    },
    {
      title: "Rewards Available",
      value: "8",
      change: "3 new rewards",
      icon: Trophy,
      color: "text-accent",
      bgColor: "bg-accent/10",
      borderColor: "border-accent/20",
    },
    {
      title: "Shopping Items",
      value: "15",
      change: "5 items needed",
      icon: ShoppingCart,
      color: "text-secondary",
      bgColor: "bg-secondary/10",
      borderColor: "border-secondary/20",
    },
  ]

  const familyMembers = [
    { name: "Sarah", initials: "SA", points: 850, tasksCompleted: 12, color: "bg-primary" },
    { name: "Mike", initials: "MI", points: 720, tasksCompleted: 10, color: "bg-secondary" },
    { name: "Emma", initials: "EM", points: 650, tasksCompleted: 9, color: "bg-accent" },
    { name: "Dad", initials: "DA", points: 230, tasksCompleted: 4, color: "bg-success" },
  ]

  const recentTasks = [
    { task: "Clean bedroom", user: "Sarah", status: "completed", time: "2h ago" },
    { task: "Do homework", user: "Mike", status: "in-progress", time: "4h ago" },
    { task: "Walk the dog", user: "Emma", status: "completed", time: "1d ago" },
  ]

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <div>
        <h1 className="text-4xl font-bold tracking-tight mb-2">Welcome back, Family</h1>
        <p className="text-muted-foreground text-lg">Here's your household overview for today</p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => {
          const Icon = stat.icon
          return (
            <Card
              key={stat.title}
              className={`p-6 border ${stat.borderColor} bg-card/50 backdrop-blur-sm hover:bg-card/80 transition-all duration-300 hover:scale-[1.02]`}
            >
              <div className="flex items-start justify-between mb-4">
                <div className={`${stat.bgColor} ${stat.color} p-3 rounded-lg`}>
                  <Icon className="h-5 w-5" />
                </div>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-1">{stat.title}</p>
                <p className="text-3xl font-bold tracking-tight mb-1">{stat.value}</p>
                <p className="text-xs text-muted-foreground flex items-center gap-1">
                  <TrendingUp className="h-3 w-3" />
                  {stat.change}
                </p>
              </div>
            </Card>
          )
        })}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Family Members */}
        <Card className="lg:col-span-2 p-6 border-border bg-card/50 backdrop-blur-sm">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5 text-primary" />
              <h2 className="text-2xl font-bold tracking-tight">Family Members</h2>
            </div>
            <Sparkles className="h-5 w-5 text-accent" />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {familyMembers.map((member) => (
              <div
                key={member.name}
                className="p-4 rounded-lg bg-muted/30 border border-border/50 hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-3 mb-3">
                  <Avatar className={`h-12 w-12 ${member.color}`}>
                    <AvatarFallback className="text-white font-bold">{member.initials}</AvatarFallback>
                  </Avatar>
                  <div className="flex-1">
                    <h3 className="font-bold">{member.name}</h3>
                    <p className="text-sm text-muted-foreground">{member.points} points</p>
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>Progress</span>
                    <span>{member.tasksCompleted}/15 tasks</span>
                  </div>
                  <Progress value={(member.tasksCompleted / 15) * 100} className="h-2" />
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Recent Tasks */}
        <Card className="p-6 border-border bg-card/50 backdrop-blur-sm">
          <div className="flex items-center gap-2 mb-6">
            <Clock className="h-5 w-5 text-secondary" />
            <h2 className="text-2xl font-bold tracking-tight">Recent Tasks</h2>
          </div>
          <div className="space-y-3">
            {recentTasks.map((item, i) => (
              <div key={i} className="p-3 rounded-lg bg-muted/30 border border-border/50">
                <div className="flex items-start gap-2 mb-1">
                  {item.status === "completed" ? (
                    <CheckCircle2 className="h-4 w-4 text-success mt-0.5" />
                  ) : (
                    <Clock className="h-4 w-4 text-warning mt-0.5" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{item.task}</p>
                    <p className="text-xs text-muted-foreground">
                      {item.user} • {item.time}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <Link
            href="/tasks"
            className="mt-4 block text-center text-sm text-primary hover:text-primary/80 font-medium transition-colors"
          >
            View all tasks →
          </Link>
        </Card>
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight mb-4">Quick Actions</h2>
        <div className="grid gap-4 md:grid-cols-3">
          <Link href="/tasks">
            <Card className="p-6 border-primary/20 bg-card/50 backdrop-blur-sm hover:bg-card/80 hover:border-primary/40 transition-all duration-300 cursor-pointer group hover:scale-[1.02]">
              <div className="bg-primary/10 text-primary p-3 rounded-lg w-fit mb-3 group-hover:bg-primary/20 transition-colors">
                <Target className="h-6 w-6" />
              </div>
              <h3 className="text-xl font-bold mb-1">Manage Tasks</h3>
              <p className="text-sm text-muted-foreground">Create and assign family tasks</p>
            </Card>
          </Link>
          <Link href="/rewards">
            <Card className="p-6 border-accent/20 bg-card/50 backdrop-blur-sm hover:bg-card/80 hover:border-accent/40 transition-all duration-300 cursor-pointer group hover:scale-[1.02]">
              <div className="bg-accent/10 text-accent p-3 rounded-lg w-fit mb-3 group-hover:bg-accent/20 transition-colors">
                <Trophy className="h-6 w-6" />
              </div>
              <h3 className="text-xl font-bold mb-1">View Rewards</h3>
              <p className="text-sm text-muted-foreground">Claim rewards with earned points</p>
            </Card>
          </Link>
          <Link href="/shopping">
            <Card className="p-6 border-secondary/20 bg-card/50 backdrop-blur-sm hover:bg-card/80 hover:border-secondary/40 transition-all duration-300 cursor-pointer group hover:scale-[1.02]">
              <div className="bg-secondary/10 text-secondary p-3 rounded-lg w-fit mb-3 group-hover:bg-secondary/20 transition-colors">
                <ShoppingCart className="h-6 w-6" />
              </div>
              <h3 className="text-xl font-bold mb-1">Shopping List</h3>
              <p className="text-sm text-muted-foreground">Manage family shopping items</p>
            </Card>
          </Link>
        </div>
      </div>
    </div>
  )
}

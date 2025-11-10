"use client"

import { useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Plus, Gift, Star, Sparkles } from "lucide-react"
import { AddRewardDialog } from "@/components/add-reward-dialog"

interface Reward {
  id: string
  title: string
  description: string
  points: number
  claimed: boolean
  claimedBy?: string
}

export default function RewardsPage() {
  const [rewards, setRewards] = useState<Reward[]>([
    { id: "1", title: "Movie Night", description: "Choose the family movie", points: 200, claimed: false },
    { id: "2", title: "Extra Screen Time", description: "30 minutes extra", points: 150, claimed: false },
    { id: "3", title: "Ice Cream Trip", description: "Family ice cream outing", points: 300, claimed: false },
    {
      id: "4",
      title: "Skip a Chore",
      description: "Skip one chore this week",
      points: 250,
      claimed: true,
      claimedBy: "Sarah",
    },
  ])
  const [dialogOpen, setDialogOpen] = useState(false)
  const [userPoints] = useState(450)

  const claimReward = (id: string) => {
    setRewards(rewards.map((reward) => (reward.id === id ? { ...reward, claimed: true, claimedBy: "You" } : reward)))
  }

  const addReward = (newReward: Omit<Reward, "id" | "claimed">) => {
    setRewards([...rewards, { ...newReward, id: Date.now().toString(), claimed: false }])
    setDialogOpen(false)
  }

  const availableRewards = rewards.filter((r) => !r.claimed)
  const claimedRewards = rewards.filter((r) => r.claimed)

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-bold tracking-tight text-balance mb-2">Rewards Store</h1>
          <p className="text-muted-foreground text-lg">You have {userPoints} points to spend</p>
        </div>
        <Button onClick={() => setDialogOpen(true)} size="lg" className="gap-2">
          <Plus className="h-5 w-5" />
          Add Reward
        </Button>
      </div>

      {/* Points Balance Card */}
      <Card className="p-8 mb-8 border-primary/50 bg-gradient-to-br from-primary/10 via-accent/5 to-secondary/10 backdrop-blur-sm">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground mb-2">Your Points Balance</p>
            <p className="text-5xl font-bold tracking-tight flex items-center gap-3">
              <Sparkles className="h-10 w-10 text-primary" />
              {userPoints}
            </p>
          </div>
          <div className="text-right">
            <p className="text-sm text-muted-foreground mb-1">This Month</p>
            <p className="text-2xl font-bold text-success">+450</p>
          </div>
        </div>
      </Card>

      {/* Available Rewards */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold tracking-tight mb-4 flex items-center gap-2">
          <Gift className="h-6 w-6 text-accent" />
          Available Rewards
        </h2>
        <div className="grid gap-4 md:grid-cols-2">
          {availableRewards.map((reward) => {
            const canAfford = userPoints >= reward.points
            return (
              <Card
                key={reward.id}
                className={`p-6 border-border/50 backdrop-blur-sm hover:bg-card/80 transition-all duration-300 ${
                  canAfford ? "hover:border-accent/50" : "opacity-60"
                }`}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <h3 className="text-xl font-semibold mb-2">{reward.title}</h3>
                    <p className="text-sm text-muted-foreground mb-4">{reward.description}</p>
                  </div>
                  <div className="flex items-center gap-2 bg-accent/10 text-accent px-3 py-1 rounded-full">
                    <Star className="h-4 w-4 fill-current" />
                    <span className="font-semibold">{reward.points}</span>
                  </div>
                </div>
                <Button
                  onClick={() => claimReward(reward.id)}
                  disabled={!canAfford}
                  className="w-full"
                  variant={canAfford ? "default" : "secondary"}
                >
                  {canAfford ? "Claim Reward" : "Not Enough Points"}
                </Button>
              </Card>
            )
          })}
        </div>
      </div>

      {/* Claimed Rewards */}
      {claimedRewards.length > 0 && (
        <div>
          <h2 className="text-2xl font-bold tracking-tight mb-4 flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-success" />
            Claimed Rewards
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            {claimedRewards.map((reward) => (
              <Card key={reward.id} className="p-6 border-success/30 bg-success/5 backdrop-blur-sm">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1">
                    <h3 className="text-xl font-semibold mb-2">{reward.title}</h3>
                    <p className="text-sm text-muted-foreground mb-2">{reward.description}</p>
                    <p className="text-sm text-success font-medium">Claimed by {reward.claimedBy}</p>
                  </div>
                  <div className="flex items-center gap-2 bg-success/10 text-success px-3 py-1 rounded-full">
                    <Star className="h-4 w-4 fill-current" />
                    <span className="font-semibold">{reward.points}</span>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      <AddRewardDialog open={dialogOpen} onOpenChange={setDialogOpen} onAdd={addReward} />
    </div>
  )
}

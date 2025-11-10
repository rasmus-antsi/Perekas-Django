"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Gift, Plus } from "lucide-react"
import { AddRewardDialog } from "@/components/add-reward-dialog"

interface Reward {
  id: string
  title: string
  cost: number
  claimed: boolean
}

export function RewardsSection() {
  const [rewards, setRewards] = useState<Reward[]>([
    { id: "1", title: "Extra screen time", cost: 50, claimed: false },
    { id: "2", title: "Choose dinner", cost: 30, claimed: false },
    { id: "3", title: "Movie night pick", cost: 40, claimed: false },
    { id: "4", title: "Stay up late", cost: 60, claimed: false },
  ])
  const [dialogOpen, setDialogOpen] = useState(false)

  const claimReward = (id: string) => {
    setRewards(rewards.map((reward) => (reward.id === id ? { ...reward, claimed: true } : reward)))
  }

  const addReward = (title: string, cost: number) => {
    const newReward: Reward = {
      id: Date.now().toString(),
      title,
      cost,
      claimed: false,
    }
    setRewards([...rewards, newReward])
  }

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
          <CardTitle className="text-xl font-semibold">Rewards</CardTitle>
          <Button size="sm" onClick={() => setDialogOpen(true)}>
            <Plus className="mr-1.5 h-4 w-4" />
            Add Reward
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {rewards.map((reward) => (
            <div
              key={reward.id}
              className="flex items-center gap-3 rounded-lg border border-border bg-card p-4 transition-colors hover:bg-secondary/50"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10">
                <Gift className="h-5 w-5 text-accent" />
              </div>
              <div className="flex-1 space-y-0.5">
                <p
                  className={`font-medium leading-none ${reward.claimed ? "text-muted-foreground line-through" : "text-foreground"}`}
                >
                  {reward.title}
                </p>
                <p className="text-sm text-muted-foreground">{reward.cost} points</p>
              </div>
              <Button
                size="sm"
                variant={reward.claimed ? "outline" : "default"}
                onClick={() => claimReward(reward.id)}
                disabled={reward.claimed}
              >
                {reward.claimed ? "Claimed" : "Claim"}
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>

      <AddRewardDialog open={dialogOpen} onOpenChange={setDialogOpen} onAddReward={addReward} />
    </>
  )
}

"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { LayoutDashboard, Target, Gift, ShoppingCart, Settings, Users } from "lucide-react"
import { cn } from "@/lib/utils"

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Tasks", href: "/tasks", icon: Target },
  { name: "Rewards", href: "/rewards", icon: Gift },
  { name: "Shopping", href: "/shopping", icon: ShoppingCart },
]

const secondaryNavigation = [
  { name: "Family", href: "/family", icon: Users },
  { name: "Settings", href: "/settings", icon: Settings },
]

export function AppSidebar() {
  const pathname = usePathname()

  return (
    <div className="flex h-full w-64 flex-col bg-sidebar border-r border-sidebar-border">
      <div className="flex h-16 items-center gap-3 border-b border-sidebar-border px-6">
        <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center shadow-lg">
          <Users className="h-6 w-6 text-white" />
        </div>
        <span className="text-xl font-bold tracking-tight">FamilyHub</span>
      </div>

      {/* Main Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-6">
        {navigation.map((item) => {
          const isActive = pathname === item.href
          const Icon = item.icon
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-4 py-3 text-sm font-medium transition-all duration-200",
                isActive
                  ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-sm"
                  : "text-sidebar-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground",
              )}
            >
              <Icon className="h-5 w-5" />
              {item.name}
            </Link>
          )
        })}
      </nav>

      {/* Secondary Navigation */}
      <div className="border-t border-sidebar-border px-3 py-4">
        <div className="space-y-1">
          {secondaryNavigation.map((item) => {
            const isActive = pathname === item.href
            const Icon = item.icon
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-4 py-3 text-sm font-medium transition-all duration-200",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-sm"
                    : "text-sidebar-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground",
                )}
              >
                <Icon className="h-5 w-5" />
                {item.name}
              </Link>
            )
          })}
        </div>
      </div>

      <div className="border-t border-sidebar-border p-4">
        <div className="flex items-center gap-3 p-3 rounded-lg hover:bg-sidebar-accent/30 transition-colors cursor-pointer">
          <div className="h-10 w-10 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center shadow-md">
            <Users className="h-5 w-5 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold truncate">Family Account</p>
            <p className="text-xs text-muted-foreground truncate">4 members active</p>
          </div>
        </div>
      </div>
    </div>
  )
}

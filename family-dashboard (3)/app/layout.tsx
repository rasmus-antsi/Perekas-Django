import type React from "react"
import type { Metadata } from "next"
import { Inter } from "next/font/google"
import { Analytics } from "@vercel/analytics/next"
import "./globals.css"
import { AppSidebar } from "@/components/app-sidebar"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "FamilyHub - Premium Family Dashboard",
  description: "Manage tasks, rewards, and shopping together",
  generator: "v0.app",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} font-sans antialiased`}>
        <div className="flex h-screen overflow-hidden bg-background">
          <AppSidebar />
          <main className="flex-1 overflow-y-auto">{children}</main>
        </div>
        <Analytics />
      </body>
    </html>
  )
}

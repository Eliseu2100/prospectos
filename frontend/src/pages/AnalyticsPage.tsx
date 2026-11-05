import { ArrowLeft } from "lucide-react"
import { Link } from "react-router-dom"
import { MetricsDashboard } from "@/components/dashboard/MetricsDashboard"
import { FunilConversao } from "@/components/dashboard/FunilConversao"
import { BreakdownNicho } from "@/components/dashboard/BreakdownNicho"

export function AnalyticsPage() {
  return (
      <main className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Voltar para o dashboard
        </Link>

        <h2 className="text-xl font-semibold tracking-tight">Analytics</h2>

        <MetricsDashboard />

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <FunilConversao />
          <BreakdownNicho />
        </div>
      </main>
  )
}

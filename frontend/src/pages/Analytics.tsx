import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  LineChart, Line, ResponsiveContainer, Legend
} from 'recharts'
import { format, parseISO } from 'date-fns'
import { TrendingDown, TrendingUp, Minus, BarChart3, Leaf, DollarSign } from 'lucide-react'
import { analyticsApi } from '@/services/api'
import type { MonthlyAnalytics, CostProjection, CO2TrendResponse } from '@/types'
import { Card, SkeletonCard } from '@/components/ui'

const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

function TrendBadge({ pct }: { pct: number | null }) {
  if (pct === null) return <span className="text-gray-600 text-xs">—</span>
  const Icon = pct > 0 ? TrendingUp : pct < 0 ? TrendingDown : Minus
  const color = pct > 0 ? 'text-red-400' : pct < 0 ? 'text-brand-400' : 'text-gray-500'
  return (
    <span className={`flex items-center gap-1 text-xs font-mono ${color}`}>
      <Icon className="w-3 h-3" />
      {Math.abs(pct).toFixed(1)}%
    </span>
  )
}

export default function Analytics() {
  const [monthly, setMonthly] = useState<MonthlyAnalytics[]>([])
  const [co2, setCo2] = useState<CO2TrendResponse | null>(null)
  const [projection, setProjection] = useState<CostProjection | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      analyticsApi.monthly(),
      analyticsApi.co2Trend(30),
      analyticsApi.costProjection(),
    ]).then(([{ data: m }, { data: c }, { data: p }]) => {
      setMonthly(m)
      setCo2(c)
      setProjection(p)
    }).finally(() => setLoading(false))
  }, [])

  const co2ChartData = co2?.points.map(p => ({
    date: format(parseISO(p.timestamp), 'MMM d'),
    co2: p.value,
  })) ?? []

  const monthlyChartData = [...monthly].reverse().map(m => ({
    month: MONTH_NAMES[m.month - 1],
    kwh: m.total_kwh,
    cost: m.total_cost_usd,
    co2: m.total_co2_kg,
  }))

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Cost projection */}
      {loading ? (
        <div className="grid grid-cols-3 gap-4">{[1,2,3].map(i => <SkeletonCard key={i} />)}</div>
      ) : projection && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            {
              label: 'Current Month Cost',
              value: `$${projection.current_month_cost.toFixed(2)}`,
              icon: <DollarSign className="w-5 h-5" />,
              color: 'text-purple-400',
              sub: 'This month so far',
            },
            {
              label: 'Projected Month End',
              value: `$${projection.projected_month_cost.toFixed(2)}`,
              icon: <BarChart3 className="w-5 h-5" />,
              color: 'text-amber-400',
              sub: 'Based on current trend',
            },
            {
              label: 'Potential Savings',
              value: `$${projection.potential_savings.toFixed(2)}`,
              icon: <Leaf className="w-5 h-5" />,
              color: 'text-brand-400',
              sub: `${projection.savings_percentage}% via idle shutdowns`,
            },
          ].map(({ label, value, icon, color, sub }, i) => (
            <motion.div
              key={label}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08 }}
              className="glass-card p-5"
            >
              <div className="flex items-start justify-between mb-3">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">{label}</p>
                <div className={`${color} p-2 rounded-xl bg-dark-muted`}>{icon}</div>
              </div>
              <div className={`text-2xl font-display font-bold ${color} mb-1`}>{value}</div>
              <div className="text-xs text-gray-600">{sub}</div>
            </motion.div>
          ))}
        </div>
      )}

      {/* CO2 Trend */}
      <Card delay={0.1}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-300">CO₂ Emissions Trend</h3>
            <p className="text-xs text-gray-600 mt-0.5">Last 30 days · kg per day</p>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-brand-400 font-mono px-2.5 py-1 rounded-lg bg-brand-500/10 border border-brand-500/20">
            <Leaf className="w-3 h-3" />
            kg CO₂
          </div>
        </div>

        {co2ChartData.length === 0 ? (
          <div className="h-52 flex items-center justify-center text-sm text-gray-600">
            No emissions data yet
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={208}>
            <LineChart data={co2ChartData} margin={{ top: 4, right: 0, bottom: 0, left: -16 }}>
              <CartesianGrid stroke="#1e2a1e" strokeDasharray="4 4" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: '#4b5563', fontSize: 10, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} interval={4} />
              <YAxis tick={{ fill: '#4b5563', fontSize: 10, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: '#131a12', border: '1px solid #1e2a1e', borderRadius: 12 }}
                labelStyle={{ color: '#6b7280', fontSize: 11 }}
                itemStyle={{ color: '#10be5c' }}
              />
              <Line type="monotone" dataKey="co2" stroke="#10be5c" strokeWidth={2} dot={false} activeDot={{ r: 4, fill: '#10be5c', stroke: '#0d1210', strokeWidth: 2 }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Card>

      {/* Monthly report */}
      <Card delay={0.2}>
        <h3 className="text-sm font-semibold text-gray-300 mb-4">Monthly Report</h3>

        {monthly.length === 0 ? (
          <div className="py-10 text-center text-sm text-gray-600">
            Monthly data is aggregated on the 1st of each month by the background worker.
            <br />Run the Celery beat scheduler to generate reports.
          </div>
        ) : (
          <>
            {/* Bar chart */}
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={monthlyChartData} margin={{ top: 4, right: 0, bottom: 0, left: -16 }}>
                <CartesianGrid stroke="#1e2a1e" strokeDasharray="4 4" vertical={false} />
                <XAxis dataKey="month" tick={{ fill: '#4b5563', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#4b5563', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: '#131a12', border: '1px solid #1e2a1e', borderRadius: 12 }} />
                <Legend wrapperStyle={{ fontSize: 11, color: '#6b7280' }} />
                <Bar dataKey="kwh" name="kWh" fill="#f59e0b" radius={[4,4,0,0]} />
                <Bar dataKey="co2" name="CO₂ kg" fill="#10be5c" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>

            {/* Table */}
            <div className="mt-5 border-t border-dark-border pt-4">
              <div className="grid grid-cols-7 gap-3 text-xs font-medium text-gray-600 uppercase tracking-wider mb-3">
                {['Month', 'kWh', 'vs prev', 'CO₂ kg', 'vs prev', 'Cost', 'vs prev'].map(h => (
                  <div key={h}>{h}</div>
                ))}
              </div>
              {monthly.map((m) => (
                <div key={m.id} className="grid grid-cols-7 gap-3 py-2.5 border-b border-dark-border/50 text-sm">
                  <div className="font-medium text-gray-300">{MONTH_NAMES[m.month - 1]} {m.year}</div>
                  <div className="font-mono text-amber-400">{m.total_kwh.toFixed(3)}</div>
                  <TrendBadge pct={m.kwh_change_pct} />
                  <div className="font-mono text-brand-400">{m.total_co2_kg.toFixed(3)}</div>
                  <TrendBadge pct={m.co2_change_pct} />
                  <div className="font-mono text-purple-400">${m.total_cost_usd.toFixed(4)}</div>
                  <TrendBadge pct={m.cost_change_pct} />
                </div>
              ))}
            </div>
          </>
        )}
      </Card>
    </div>
  )
}

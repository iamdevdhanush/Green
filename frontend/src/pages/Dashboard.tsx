import { useEffect, useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import { Zap, Leaf, DollarSign, Server, Clock, Activity } from 'lucide-react'
import { format, parseISO } from 'date-fns'
import { analyticsApi } from '@/services/api'
import type { OverviewStats, TimeSeriesPoint } from '@/types'
import { StatCard, SkeletonCard, Card } from '@/components/ui'

const REFRESH_INTERVAL = 30_000

function formatValue(n: number, decimals = 2) {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return n.toFixed(decimals)
}

const CustomTooltip = ({ active, payload, label }: Record<string, unknown>) => {
  if (!active || !(payload as unknown[])?.length) return null
  return (
    <div className="bg-dark-card border border-dark-border rounded-xl px-4 py-3 shadow-card">
      <p className="text-xs text-gray-500 mb-1">{label as string}</p>
      <p className="text-sm font-semibold text-brand-400">
        {((payload as { value: number }[])[0]?.value ?? 0).toFixed(4)} kWh
      </p>
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState<OverviewStats | null>(null)
  const [series, setSeries] = useState<TimeSeriesPoint[]>([])
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    try {
      const [{ data: ov }, { data: ts }] = await Promise.all([
        analyticsApi.overview(),
        analyticsApi.energyTimeseries(24),
      ])
      setStats(ov)
      setSeries(ts)
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const id = setInterval(fetchData, REFRESH_INTERVAL)
    return () => clearInterval(id)
  }, [fetchData])

  const chartData = series.map(p => ({
    time: format(parseISO(p.timestamp), 'HH:mm'),
    value: p.value,
  }))

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)
        ) : (
          <>
            <StatCard
              label="Energy Wasted"
              value={formatValue(stats?.total_energy_kwh ?? 0)}
              unit="kWh"
              icon={<Zap className="w-5 h-5" />}
              iconColor="text-amber-400"
              delay={0}
            />
            <StatCard
              label="CO₂ Emissions"
              value={formatValue(stats?.total_co2_kg ?? 0)}
              unit="kg"
              icon={<Leaf className="w-5 h-5" />}
              iconColor="text-brand-400"
              delay={0.08}
            />
            <StatCard
              label="Cost Impact"
              value={`$${formatValue(stats?.total_cost_usd ?? 0)}`}
              icon={<DollarSign className="w-5 h-5" />}
              iconColor="text-purple-400"
              delay={0.16}
            />
            <StatCard
              label="Total Idle Hours"
              value={formatValue(stats?.total_idle_hours ?? 0, 1)}
              unit="hrs"
              icon={<Clock className="w-5 h-5" />}
              iconColor="text-blue-400"
              delay={0.24}
            />
          </>
        )}
      </div>

      {/* Machine Status + Chart Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Machine status */}
        <Card delay={0.15}>
          <div className="flex items-center gap-2 mb-4">
            <Server className="w-4 h-4 text-gray-500" />
            <span className="text-sm font-semibold text-gray-300">Machine Status</span>
          </div>
          {loading ? (
            <div className="space-y-3">
              {[1,2,3].map(i => <div key={i} className="skeleton h-14 rounded-xl" />)}
            </div>
          ) : (
            <div className="space-y-3">
              {[
                { label: 'Active', count: stats?.active_machines ?? 0, color: 'bg-brand-500', dot: 'status-dot-active' },
                { label: 'Idle', count: stats?.idle_machines ?? 0, color: 'bg-amber-500', dot: 'status-dot-idle' },
                { label: 'Offline', count: stats?.offline_machines ?? 0, color: 'bg-gray-700', dot: 'status-dot-offline' },
              ].map(({ label, count, color, dot }) => {
                const total = stats?.total_machines || 1
                const pct = Math.round((count / total) * 100)
                return (
                  <div key={label}>
                    <div className="flex justify-between items-center mb-1">
                      <div className="flex items-center gap-2">
                        <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
                        <span className="text-xs text-gray-400">{label}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono text-gray-500">{pct}%</span>
                        <span className="text-sm font-bold text-white w-6 text-right">{count}</span>
                      </div>
                    </div>
                    <div className="h-1.5 bg-dark-muted rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${pct}%` }}
                        transition={{ delay: 0.3, duration: 0.6, ease: 'easeOut' }}
                        className={`h-full ${color} rounded-full`}
                      />
                    </div>
                  </div>
                )
              })}

              <div className="pt-2 border-t border-dark-border">
                <div className="flex justify-between">
                  <span className="text-xs text-gray-600">Total Machines</span>
                  <span className="text-sm font-bold text-white">{stats?.total_machines ?? 0}</span>
                </div>
              </div>
            </div>
          )}
        </Card>

        {/* Energy chart */}
        <Card className="lg:col-span-2" delay={0.2}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-gray-500" />
              <span className="text-sm font-semibold text-gray-300">Energy Waste</span>
              <span className="text-xs text-gray-600">last 24h</span>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-brand-400 font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse-slow" />
              kWh / hour
            </div>
          </div>

          {loading ? (
            <div className="skeleton rounded-xl h-44" />
          ) : chartData.length === 0 ? (
            <div className="h-44 flex items-center justify-center text-gray-600 text-sm">
              No data yet — waiting for agent heartbeats
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={176}>
              <AreaChart data={chartData} margin={{ top: 4, right: 0, bottom: 0, left: -16 }}>
                <defs>
                  <linearGradient id="energyGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10be5c" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#10be5c" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#1e2a1e" strokeDasharray="4 4" vertical={false} />
                <XAxis
                  dataKey="time"
                  tick={{ fill: '#4b5563', fontSize: 10, fontFamily: 'JetBrains Mono' }}
                  axisLine={false}
                  tickLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{ fill: '#4b5563', fontSize: 10, fontFamily: 'JetBrains Mono' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={<CustomTooltip />} />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="#10be5c"
                  strokeWidth={2}
                  fill="url(#energyGradient)"
                  dot={false}
                  activeDot={{ r: 4, fill: '#10be5c', stroke: '#0d1210', strokeWidth: 2 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>
    </div>
  )
}

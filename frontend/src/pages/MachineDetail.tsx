import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'
import {
  ArrowLeft, Server, Cpu, HardDrive, Wifi, Clock, Zap, Leaf, DollarSign, PowerOff
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import { format, parseISO, formatDistanceToNow } from 'date-fns'
import { machinesApi, commandsApi } from '@/services/api'
import type { Machine, EnergyMetric, ShutdownCommand } from '@/types'
import { Badge, Button, Card, Skeleton } from '@/components/ui'
import { useAuthStore } from '@/store/authStore'

export default function MachineDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useAuthStore()

  const [machine, setMachine] = useState<Machine | null>(null)
  const [history, setHistory] = useState<EnergyMetric[]>([])
  const [loading, setLoading] = useState(true)
  const [shutdownLoading, setShutdownLoading] = useState(false)

  useEffect(() => {
    if (!id) return
    Promise.all([
      machinesApi.get(id),
      machinesApi.history(id, 24),
    ]).then(([{ data: m }, { data: h }]) => {
      setMachine(m)
      setHistory(h)
    }).catch(() => {
      toast.error('Machine not found')
      navigate('/machines')
    }).finally(() => setLoading(false))
  }, [id, navigate])

  const handleShutdown = async () => {
    if (!id || !machine) return
    if (machine.status !== 'idle') {
      toast.error('Machine must be idle to shutdown')
      return
    }
    setShutdownLoading(true)
    try {
      await commandsApi.issueShutdown(id, 15)
      toast.success('Shutdown command issued — agent will execute within 2 minutes')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed'
      toast.error(msg)
    } finally {
      setShutdownLoading(false)
    }
  }

  const chartData = history.map(h => ({
    time: format(parseISO(h.recorded_at), 'HH:mm'),
    kwh: h.energy_kwh,
    cpu: h.cpu_percent,
    idle: h.idle_minutes,
  }))

  if (loading) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-2 gap-4">
          {[1,2,3,4].map(i => <Skeleton key={i} className="h-28 rounded-2xl" />)}
        </div>
        <Skeleton className="h-64 rounded-2xl" />
      </div>
    )
  }

  if (!machine) return null

  const specs = [
    { icon: <Cpu className="w-4 h-4" />, label: 'CPU', value: machine.cpu_info ?? '—' },
    { icon: <HardDrive className="w-4 h-4" />, label: 'RAM', value: machine.ram_gb ? `${machine.ram_gb} GB` : '—' },
    { icon: <Server className="w-4 h-4" />, label: 'OS', value: machine.os_version ?? '—' },
    { icon: <Wifi className="w-4 h-4" />, label: 'IP', value: machine.ip_address ?? '—' },
  ]

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Back + header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/machines')}
            className="p-2 rounded-xl text-gray-500 hover:text-gray-200 hover:bg-dark-muted transition-all"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-display font-bold text-white">{machine.hostname}</h2>
              <Badge variant={machine.status as 'active' | 'idle' | 'offline' | 'shutdown'} dot>
                {machine.status}
              </Badge>
            </div>
            <div className="text-xs font-mono text-gray-600 mt-0.5">{machine.mac_address}</div>
          </div>
        </div>

        {user?.role === 'admin' && (
          <Button
            variant="danger"
            size="sm"
            loading={shutdownLoading}
            disabled={machine.status !== 'idle'}
            onClick={handleShutdown}
          >
            <PowerOff className="w-3.5 h-3.5" />
            Shutdown
          </Button>
        )}
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { icon: <Zap className="w-4 h-4 text-amber-400" />, label: 'Energy Wasted', value: `${machine.total_energy_kwh.toFixed(4)} kWh`, color: 'text-amber-400' },
          { icon: <Leaf className="w-4 h-4 text-brand-400" />, label: 'CO₂ Emitted', value: `${machine.total_co2_kg.toFixed(4)} kg`, color: 'text-brand-400' },
          { icon: <DollarSign className="w-4 h-4 text-purple-400" />, label: 'Cost Impact', value: `$${machine.total_cost_usd.toFixed(4)}`, color: 'text-purple-400' },
          { icon: <Clock className="w-4 h-4 text-blue-400" />, label: 'Idle Hours', value: `${machine.total_idle_hours.toFixed(2)} hrs`, color: 'text-blue-400' },
        ].map(({ icon, label, value, color }, i) => (
          <motion.div
            key={label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
            className="glass-card p-4"
          >
            <div className="flex items-center gap-2 mb-2">{icon}<span className="text-xs text-gray-500">{label}</span></div>
            <div className={`text-xl font-display font-bold ${color}`}>{value}</div>
          </motion.div>
        ))}
      </div>

      {/* Chart */}
      <Card delay={0.2}>
        <div className="flex items-center justify-between mb-4">
          <span className="text-sm font-semibold text-gray-300">Energy History (24h)</span>
          <span className="text-xs font-mono text-gray-600">kWh / heartbeat</span>
        </div>
        {chartData.length === 0 ? (
          <div className="h-48 flex items-center justify-center text-sm text-gray-600">
            No history yet — agent hasn't reported
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={192}>
            <AreaChart data={chartData} margin={{ top: 4, right: 0, bottom: 0, left: -16 }}>
              <defs>
                <linearGradient id="detailGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#f59e0b" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#1e2a1e" strokeDasharray="4 4" vertical={false} />
              <XAxis dataKey="time" tick={{ fill: '#4b5563', fontSize: 10, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#4b5563', fontSize: 10, fontFamily: 'JetBrains Mono' }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: '#131a12', border: '1px solid #1e2a1e', borderRadius: 12, fontFamily: 'DM Sans' }}
                labelStyle={{ color: '#6b7280', fontSize: 11 }}
                itemStyle={{ color: '#f59e0b' }}
              />
              <Area type="monotone" dataKey="kwh" stroke="#f59e0b" strokeWidth={2} fill="url(#detailGradient)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </Card>

      {/* System specs */}
      <Card delay={0.3}>
        <h3 className="text-sm font-semibold text-gray-300 mb-4">System Specs</h3>
        <div className="grid grid-cols-2 gap-3">
          {specs.map(({ icon, label, value }) => (
            <div key={label} className="flex items-center gap-3 p-3 rounded-xl bg-dark-muted/50">
              <div className="text-gray-600">{icon}</div>
              <div>
                <div className="text-xs text-gray-600">{label}</div>
                <div className="text-sm font-mono text-gray-300 truncate">{value}</div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 pt-4 border-t border-dark-border grid grid-cols-2 gap-3 text-xs">
          <div>
            <span className="text-gray-600">Registered</span>
            <div className="text-gray-400 mt-0.5 font-mono">
              {format(parseISO(machine.registered_at), 'MMM d, yyyy HH:mm')}
            </div>
          </div>
          <div>
            <span className="text-gray-600">Last Seen</span>
            <div className="text-gray-400 mt-0.5 font-mono">
              {machine.last_seen
                ? formatDistanceToNow(parseISO(machine.last_seen), { addSuffix: true })
                : 'Never'}
            </div>
          </div>
        </div>
      </Card>
    </div>
  )
}

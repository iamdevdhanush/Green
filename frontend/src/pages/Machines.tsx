import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import toast from 'react-hot-toast'
import { Search, Server, PowerOff, ChevronRight, Filter, RefreshCw } from 'lucide-react'
import { formatDistanceToNow, parseISO } from 'date-fns'
import { machinesApi, commandsApi } from '@/services/api'
import type { Machine, MachineStatus } from '@/types'
import { Badge, Button, EmptyState, Skeleton } from '@/components/ui'
import { useAuthStore } from '@/store/authStore'

const STATUS_OPTIONS = ['all', 'active', 'idle', 'offline', 'shutdown']

export default function Machines() {
  const [machines, setMachines] = useState<Machine[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [shutdownId, setShutdownId] = useState<string | null>(null)
  const navigate = useNavigate()
  const { user } = useAuthStore()

  const fetchMachines = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await machinesApi.list({
        page,
        per_page: 20,
        search: search || undefined,
        status: statusFilter === 'all' ? undefined : statusFilter,
      })
      setMachines(data.machines)
      setTotal(data.total)
    } catch {
      toast.error('Failed to load machines')
    } finally {
      setLoading(false)
    }
  }, [page, search, statusFilter])

  useEffect(() => {
    const t = setTimeout(fetchMachines, 300)
    return () => clearTimeout(t)
  }, [fetchMachines])

  const handleShutdown = async (e: React.MouseEvent, machine: Machine) => {
    e.stopPropagation()
    if (machine.status !== 'idle') {
      toast.error('Machine must be idle to shutdown')
      return
    }
    setShutdownId(machine.id)
    try {
      await commandsApi.issueShutdown(machine.id, 15)
      toast.success(`Shutdown command issued for ${machine.hostname}`)
      fetchMachines()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to issue shutdown'
      toast.error(msg)
    } finally {
      setShutdownId(null)
    }
  }

  const totalPages = Math.ceil(total / 20)

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Search */}
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-600" />
          <input
            type="text"
            placeholder="Search hostname, IP, MAC…"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
            className="w-full pl-9 pr-4 py-2 bg-dark-card border border-dark-border rounded-xl text-sm text-gray-300 placeholder-gray-600 focus:outline-none focus:border-brand-500/50 transition-all"
          />
        </div>

        {/* Status filter */}
        <div className="flex items-center gap-1 bg-dark-card border border-dark-border rounded-xl p-1">
          {STATUS_OPTIONS.map(s => (
            <button
              key={s}
              onClick={() => { setStatusFilter(s); setPage(1) }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all capitalize ${
                statusFilter === s
                  ? 'bg-brand-500/15 text-brand-400 border border-brand-500/25'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        <Button variant="outline" size="sm" onClick={fetchMachines}>
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </Button>
      </div>

      {/* Total */}
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <span>{total} machine{total !== 1 ? 's' : ''}</span>
        {statusFilter !== 'all' && <span>· filtered by <span className="text-brand-400 capitalize">{statusFilter}</span></span>}
      </div>

      {/* Table */}
      <div className="glass-card overflow-hidden">
        {/* Header */}
        <div className="grid grid-cols-12 gap-4 px-5 py-3 border-b border-dark-border">
          {['Machine', 'Status', 'Idle', 'Energy', 'CO₂', 'Cost', 'Last Seen', ''].map((h, i) => (
            <div key={i} className={`text-xs font-medium text-gray-500 uppercase tracking-wider ${
              i === 0 ? 'col-span-3' : i === 1 ? 'col-span-1' : i === 7 ? 'col-span-1' : 'col-span-2'
            }`}>
              {h}
            </div>
          ))}
        </div>

        {/* Rows */}
        <AnimatePresence mode="wait">
          {loading ? (
            <div className="divide-y divide-dark-border">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="grid grid-cols-12 gap-4 px-5 py-4">
                  <div className="col-span-3 space-y-1.5">
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-3 w-24" />
                  </div>
                  <div className="col-span-1"><Skeleton className="h-5 w-14 rounded-full" /></div>
                  <div className="col-span-2"><Skeleton className="h-4 w-16" /></div>
                  <div className="col-span-2"><Skeleton className="h-4 w-16" /></div>
                  <div className="col-span-2"><Skeleton className="h-4 w-12" /></div>
                  <div className="col-span-2"><Skeleton className="h-4 w-20" /></div>
                </div>
              ))}
            </div>
          ) : machines.length === 0 ? (
            <EmptyState
              icon={<Server className="w-8 h-8" />}
              title="No machines found"
              description="Install the GreenOps Agent on your servers to start monitoring energy usage."
            />
          ) : (
            <div className="divide-y divide-dark-border">
              {machines.map((m, i) => (
                <motion.div
                  key={m.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.03 }}
                  onClick={() => navigate(`/machines/${m.id}`)}
                  className="grid grid-cols-12 gap-4 px-5 py-4 hover:bg-dark-muted/50 cursor-pointer transition-colors group items-center"
                >
                  {/* Machine info */}
                  <div className="col-span-3">
                    <div className="font-medium text-sm text-gray-200 group-hover:text-white transition-colors">
                      {m.hostname}
                    </div>
                    <div className="text-xs font-mono text-gray-600 mt-0.5">{m.ip_address ?? m.mac_address}</div>
                  </div>

                  {/* Status */}
                  <div className="col-span-1">
                    <Badge variant={m.status as MachineStatus} dot>
                      {m.status}
                    </Badge>
                  </div>

                  {/* Idle */}
                  <div className="col-span-2 text-sm font-mono text-gray-400">
                    {m.idle_minutes}m
                  </div>

                  {/* Energy */}
                  <div className="col-span-2 text-sm font-mono text-amber-400">
                    {m.total_energy_kwh.toFixed(3)} kWh
                  </div>

                  {/* CO2 */}
                  <div className="col-span-2 text-sm font-mono text-brand-400">
                    {m.total_co2_kg.toFixed(3)} kg
                  </div>

                  {/* Last seen */}
                  <div className="col-span-1 text-xs text-gray-600">
                    {m.last_seen
                      ? formatDistanceToNow(parseISO(m.last_seen), { addSuffix: true })
                      : 'Never'}
                  </div>

                  {/* Actions */}
                  <div className="col-span-1 flex items-center justify-end gap-2">
                    {user?.role === 'admin' && m.status === 'idle' && (
                      <button
                        onClick={e => handleShutdown(e, m)}
                        disabled={shutdownId === m.id}
                        className="p-1.5 rounded-lg text-gray-600 hover:text-red-400 hover:bg-red-500/10 transition-all"
                        title="Issue shutdown command"
                      >
                        <PowerOff className="w-3.5 h-3.5" />
                      </button>
                    )}
                    <ChevronRight className="w-4 h-4 text-gray-700 group-hover:text-gray-400 transition-colors" />
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </AnimatePresence>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>
            Previous
          </Button>
          <span className="text-sm text-gray-500 px-3">
            {page} / {totalPages}
          </span>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
            Next
          </Button>
        </div>
      )}
    </div>
  )
}

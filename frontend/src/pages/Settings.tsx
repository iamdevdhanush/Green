import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'
import { Users, Shield, Clock, Activity, Trash2 } from 'lucide-react'
import { format, parseISO } from 'date-fns'
import { usersApi, analyticsApi } from '@/services/api'
import type { User, AuditLog } from '@/types'
import { Badge, Button, Card, Skeleton } from '@/components/ui'
import { useAuthStore } from '@/store/authStore'

export default function Settings() {
  const [users, setUsers] = useState<User[]>([])
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<'users' | 'audit'>('users')
  const { user: currentUser } = useAuthStore()

  useEffect(() => {
    Promise.all([
      usersApi.list(),
      analyticsApi.audit(30),
    ]).then(([{ data: u }, { data: a }]) => {
      setUsers(u)
      setAuditLogs(a)
    }).finally(() => setLoading(false))
  }, [])

  const toggleUserStatus = async (userId: string, isActive: boolean) => {
    try {
      await usersApi.update(userId, { is_active: !isActive })
      setUsers(u => u.map(u => u.id === userId ? { ...u, is_active: !isActive } : u))
      toast.success(`User ${!isActive ? 'enabled' : 'disabled'}`)
    } catch {
      toast.error('Failed to update user')
    }
  }

  const ACTION_LABELS: Record<string, string> = {
    user_login: 'User login',
    user_registered: 'User registered',
    shutdown_command_issued: 'Shutdown issued',
    shutdown_executed: 'Shutdown executed',
    shutdown_rejected: 'Shutdown rejected',
  }

  return (
    <div className="space-y-5 animate-fade-in max-w-4xl">
      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-dark-card border border-dark-border rounded-xl w-fit">
        {(['users', 'audit'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all capitalize ${
              tab === t ? 'bg-brand-500/15 text-brand-400 border border-brand-500/20' : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            {t === 'users' ? 'User Management' : 'Audit Log'}
          </button>
        ))}
      </div>

      {tab === 'users' && (
        <Card>
          <div className="flex items-center gap-2 mb-5">
            <Users className="w-4 h-4 text-gray-500" />
            <h3 className="text-sm font-semibold text-gray-300">Users</h3>
            <span className="ml-auto text-xs text-gray-600">{users.length} members</span>
          </div>

          {loading ? (
            <div className="space-y-3">
              {[1,2,3].map(i => <Skeleton key={i} className="h-16 rounded-xl" />)}
            </div>
          ) : (
            <div className="divide-y divide-dark-border">
              {users.map((u, i) => (
                <motion.div
                  key={u.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: i * 0.05 }}
                  className="flex items-center gap-4 py-3"
                >
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-700 to-brand-900 flex items-center justify-center text-xs font-bold text-white">
                    {u.full_name[0]?.toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-200">{u.full_name}</span>
                      {u.id === currentUser?.id && (
                        <span className="text-xs text-brand-500 font-mono">(you)</span>
                      )}
                    </div>
                    <div className="text-xs text-gray-600 font-mono">{u.email}</div>
                  </div>
                  <Badge variant={u.role as 'admin' | 'manager' | 'viewer'}>
                    <Shield className="w-3 h-3" />
                    {u.role}
                  </Badge>
                  {!u.is_active && <Badge variant="offline">disabled</Badge>}
                  {currentUser?.role === 'admin' && u.id !== currentUser.id && (
                    <button
                      onClick={() => toggleUserStatus(u.id, u.is_active)}
                      className={`text-xs px-2.5 py-1 rounded-lg border transition-all ${
                        u.is_active
                          ? 'text-gray-600 border-gray-800 hover:text-red-400 hover:border-red-500/30'
                          : 'text-brand-400 border-brand-500/30 hover:bg-brand-500/10'
                      }`}
                    >
                      {u.is_active ? 'Disable' : 'Enable'}
                    </button>
                  )}
                </motion.div>
              ))}
            </div>
          )}
        </Card>
      )}

      {tab === 'audit' && (
        <Card>
          <div className="flex items-center gap-2 mb-5">
            <Activity className="w-4 h-4 text-gray-500" />
            <h3 className="text-sm font-semibold text-gray-300">Recent Activity</h3>
            <span className="ml-auto text-xs text-gray-600">Last 30 events</span>
          </div>

          {loading ? (
            <div className="space-y-2">
              {[1,2,3,4,5].map(i => <Skeleton key={i} className="h-12 rounded-xl" />)}
            </div>
          ) : auditLogs.length === 0 ? (
            <div className="py-10 text-center text-sm text-gray-600">No audit events yet</div>
          ) : (
            <div className="space-y-1">
              {auditLogs.map((log, i) => (
                <motion.div
                  key={log.id}
                  initial={{ opacity: 0, x: -4 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.02 }}
                  className="flex items-start gap-3 p-3 rounded-xl hover:bg-dark-muted/50 transition-colors"
                >
                  <div className="w-6 h-6 rounded-lg bg-dark-muted flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Activity className="w-3 h-3 text-gray-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-300">
                        {ACTION_LABELS[log.action] ?? log.action.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mt-0.5">
                      {log.ip_address && (
                        <span className="text-xs font-mono text-gray-600">{log.ip_address}</span>
                      )}
                      <span className="text-xs text-gray-700 flex items-center gap-1">
                        <Clock className="w-2.5 h-2.5" />
                        {format(parseISO(log.created_at), 'MMM d, HH:mm')}
                      </span>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  )
}

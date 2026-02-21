import { NavLink, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  LayoutDashboard,
  Server,
  BarChart3,
  Settings,
  Zap,
  LogOut,
} from 'lucide-react'
import { useAuthStore } from '@/store/authStore'

const NAV_ITEMS = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Overview' },
  { to: '/machines', icon: Server, label: 'Machines' },
  { to: '/analytics', icon: BarChart3, label: 'Analytics' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Sidebar() {
  const { user, logout } = useAuthStore()
  const location = useLocation()

  return (
    <motion.aside
      initial={{ x: -20, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      className="w-64 flex-shrink-0 flex flex-col border-r border-dark-border bg-dark-card"
      style={{ background: 'rgba(13, 18, 16, 0.95)' }}
    >
      {/* Logo */}
      <div className="px-6 py-5 border-b border-dark-border">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center shadow-glow">
            <Zap className="w-4 h-4 text-white" strokeWidth={2.5} />
          </div>
          <div>
            <span className="font-display font-bold text-white text-lg tracking-tight">GreenOps</span>
            <div className="text-[10px] text-brand-500 font-mono uppercase tracking-widest">Energy Intelligence</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => {
          const active = location.pathname.startsWith(to)
          return (
            <NavLink key={to} to={to}>
              <motion.div
                whileHover={{ x: 2 }}
                whileTap={{ scale: 0.98 }}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-150 group ${
                  active
                    ? 'bg-brand-500/10 text-brand-400 border border-brand-500/20'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-dark-muted'
                }`}
              >
                <Icon
                  className={`w-4 h-4 transition-colors ${active ? 'text-brand-400' : 'text-gray-500 group-hover:text-gray-300'}`}
                  strokeWidth={active ? 2.5 : 2}
                />
                <span className={`text-sm font-medium ${active ? 'text-brand-300' : ''}`}>
                  {label}
                </span>
                {active && (
                  <motion.div
                    layoutId="sidebar-active"
                    className="ml-auto w-1.5 h-1.5 rounded-full bg-brand-400"
                    style={{ boxShadow: '0 0 6px rgba(52, 213, 120, 0.8)' }}
                  />
                )}
              </motion.div>
            </NavLink>
          )
        })}
      </nav>

      {/* User */}
      <div className="px-3 py-4 border-t border-dark-border">
        <div className="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-dark-muted/50">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-brand-600 to-brand-800 flex items-center justify-center text-xs font-bold text-white">
            {user?.full_name?.[0]?.toUpperCase() ?? 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-gray-200 truncate">{user?.full_name}</div>
            <div className="text-xs text-gray-500 capitalize">{user?.role}</div>
          </div>
          <button
            onClick={logout}
            className="text-gray-600 hover:text-red-400 transition-colors"
            title="Logout"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </motion.aside>
  )
}

import { useLocation } from 'react-router-dom'
import { Bell, RefreshCw } from 'lucide-react'
import { motion } from 'framer-motion'

const PAGE_TITLES: Record<string, { title: string; subtitle: string }> = {
  '/dashboard': { title: 'Overview', subtitle: 'Platform energy intelligence at a glance' },
  '/machines': { title: 'Machines', subtitle: 'Monitor and manage registered devices' },
  '/analytics': { title: 'Analytics', subtitle: 'Monthly reports and CO₂ trends' },
  '/settings': { title: 'Settings', subtitle: 'Platform configuration and user management' },
}

export default function Header() {
  const location = useLocation()
  const page = Object.entries(PAGE_TITLES).find(([path]) =>
    location.pathname.startsWith(path)
  )?.[1] ?? { title: 'GreenOps', subtitle: '' }

  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-dark-border bg-dark-card/50 backdrop-blur-sm">
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: -4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
      >
        <h1 className="text-lg font-display font-bold text-white">{page.title}</h1>
        <p className="text-xs text-gray-500 mt-0.5">{page.subtitle}</p>
      </motion.div>

      <div className="flex items-center gap-3">
        {/* Live indicator */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-brand-500/10 border border-brand-500/20">
          <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse-slow" />
          <span className="text-xs font-mono text-brand-400">LIVE</span>
        </div>
      </div>
    </header>
  )
}

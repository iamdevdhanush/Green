import { motion } from 'framer-motion'
import { ReactNode } from 'react'

// ── Card ─────────────────────────────────────────────────────────────────

interface CardProps {
  children: ReactNode
  className?: string
  hover?: boolean
  delay?: number
}

export function Card({ children, className = '', hover = false, delay = 0 }: CardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay }}
      whileHover={hover ? { y: -2, boxShadow: '0 8px 25px rgba(0,0,0,0.5)' } : undefined}
      className={`glass-card p-5 ${className}`}
    >
      {children}
    </motion.div>
  )
}

// ── Stat Card ────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string
  value: string | number
  unit?: string
  icon: ReactNode
  trend?: { value: number; label?: string } | null
  iconColor?: string
  delay?: number
}

export function StatCard({ label, value, unit, icon, trend, iconColor = 'text-brand-400', delay = 0 }: StatCardProps) {
  return (
    <Card delay={delay} hover>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">{label}</p>
          <div className="flex items-baseline gap-1.5">
            <span className={`stat-number text-2xl text-white`}>{value}</span>
            {unit && <span className="text-sm text-gray-500 font-mono">{unit}</span>}
          </div>
          {trend != null && (
            <div className={`flex items-center gap-1 mt-2 text-xs font-medium ${
              trend.value > 0 ? 'text-red-400' : trend.value < 0 ? 'text-brand-400' : 'text-gray-500'
            }`}>
              <span>{trend.value > 0 ? '↑' : trend.value < 0 ? '↓' : '→'}</span>
              <span>{Math.abs(trend.value).toFixed(1)}%</span>
              {trend.label && <span className="text-gray-600">{trend.label}</span>}
            </div>
          )}
        </div>
        <div className={`p-2.5 rounded-xl bg-dark-muted ${iconColor}`}>
          {icon}
        </div>
      </div>
    </Card>
  )
}

// ── Badge ────────────────────────────────────────────────────────────────

type BadgeVariant = 'active' | 'idle' | 'offline' | 'shutdown' | 'admin' | 'manager' | 'viewer' | 'pending' | 'executed' | 'rejected' | 'expired'

const BADGE_STYLES: Record<BadgeVariant, string> = {
  active: 'bg-brand-500/15 text-brand-400 border-brand-500/25',
  idle: 'bg-amber-500/15 text-amber-400 border-amber-500/25',
  offline: 'bg-gray-700/50 text-gray-500 border-gray-600/25',
  shutdown: 'bg-red-500/15 text-red-400 border-red-500/25',
  admin: 'bg-purple-500/15 text-purple-400 border-purple-500/25',
  manager: 'bg-blue-500/15 text-blue-400 border-blue-500/25',
  viewer: 'bg-gray-700/50 text-gray-400 border-gray-600/25',
  pending: 'bg-amber-500/15 text-amber-400 border-amber-500/25',
  executed: 'bg-brand-500/15 text-brand-400 border-brand-500/25',
  rejected: 'bg-red-500/15 text-red-400 border-red-500/25',
  expired: 'bg-gray-700/50 text-gray-500 border-gray-600/25',
}

interface BadgeProps {
  variant: BadgeVariant
  children: ReactNode
  dot?: boolean
}

export function Badge({ variant, children, dot = false }: BadgeProps) {
  const style = BADGE_STYLES[variant] ?? BADGE_STYLES.offline
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${style}`}>
      {dot && (
        <span className={`w-1.5 h-1.5 rounded-full status-dot-${variant}`} />
      )}
      {children}
    </span>
  )
}

// ── Button ───────────────────────────────────────────────────────────────

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'danger' | 'ghost' | 'outline'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  children: ReactNode
}

const BUTTON_VARIANTS = {
  primary: 'bg-brand-500 hover:bg-brand-600 text-white border-transparent shadow-glow hover:shadow-glow-lg',
  danger: 'bg-red-500/10 hover:bg-red-500/20 text-red-400 border-red-500/30',
  ghost: 'bg-transparent hover:bg-dark-muted text-gray-400 hover:text-gray-200 border-transparent',
  outline: 'bg-transparent hover:bg-dark-muted text-gray-300 border-dark-border hover:border-dark-muted',
}

const BUTTON_SIZES = {
  sm: 'px-3 py-1.5 text-xs rounded-lg',
  md: 'px-4 py-2 text-sm rounded-xl',
  lg: 'px-6 py-3 text-base rounded-xl',
}

export function Button({ variant = 'primary', size = 'md', loading, children, className = '', disabled, ...props }: ButtonProps) {
  return (
    <motion.button
      whileTap={{ scale: 0.97 }}
      disabled={disabled || loading}
      className={`
        inline-flex items-center justify-center gap-2 font-medium border transition-all duration-150
        disabled:opacity-50 disabled:cursor-not-allowed
        ${BUTTON_VARIANTS[variant]}
        ${BUTTON_SIZES[size]}
        ${className}
      `}
      {...(props as Record<string, unknown>)}
    >
      {loading && (
        <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
      {children}
    </motion.button>
  )
}

// ── Skeleton ─────────────────────────────────────────────────────────────

interface SkeletonProps {
  className?: string
  lines?: number
}

export function Skeleton({ className = '' }: SkeletonProps) {
  return <div className={`skeleton rounded-lg ${className}`} />
}

export function SkeletonCard() {
  return (
    <div className="glass-card p-5 space-y-3">
      <div className="flex justify-between items-start">
        <div className="space-y-2">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-7 w-32" />
        </div>
        <Skeleton className="h-10 w-10 rounded-xl" />
      </div>
      <Skeleton className="h-3 w-16" />
    </div>
  )
}

// ── Empty State ───────────────────────────────────────────────────────────

interface EmptyStateProps {
  icon: ReactNode
  title: string
  description: string
  action?: ReactNode
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex flex-col items-center justify-center py-20 text-center"
    >
      <div className="w-16 h-16 rounded-2xl bg-dark-muted flex items-center justify-center text-gray-600 mb-4">
        {icon}
      </div>
      <h3 className="text-base font-semibold text-gray-300 mb-1">{title}</h3>
      <p className="text-sm text-gray-600 max-w-xs mb-4">{description}</p>
      {action}
    </motion.div>
  )
}

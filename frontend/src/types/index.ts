// ── Auth ──────────────────────────────────────────────────────────────────

export interface User {
  id: string
  email: string
  full_name: string
  role: 'admin' | 'manager' | 'viewer'
  is_active: boolean
  created_at: string
  last_login: string | null
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
}

// ── Machine ───────────────────────────────────────────────────────────────

export type MachineStatus = 'active' | 'idle' | 'offline' | 'shutdown'

export interface Machine {
  id: string
  mac_address: string
  hostname: string
  os_version: string | null
  cpu_info: string | null
  ram_gb: number | null
  ip_address: string | null
  status: MachineStatus
  idle_minutes: number
  total_idle_hours: number
  total_energy_kwh: number
  total_co2_kg: number
  total_cost_usd: number
  last_seen: string | null
  registered_at: string
  is_active: boolean
}

export interface MachineListResponse {
  total: number
  page: number
  per_page: number
  machines: Machine[]
}

export interface EnergyMetric {
  id: string
  machine_id: string
  idle_minutes: number
  cpu_percent: number
  ram_percent: number
  energy_kwh: number
  co2_kg: number
  cost_usd: number
  recorded_at: string
}

// ── Analytics ─────────────────────────────────────────────────────────────

export interface OverviewStats {
  total_machines: number
  active_machines: number
  idle_machines: number
  offline_machines: number
  total_energy_kwh: number
  total_co2_kg: number
  total_cost_usd: number
  total_idle_hours: number
}

export interface TimeSeriesPoint {
  timestamp: string
  value: number
  label?: string
}

export interface CO2TrendResponse {
  points: TimeSeriesPoint[]
  unit: string
}

export interface CostProjection {
  current_month_cost: number
  projected_month_cost: number
  potential_savings: number
  savings_percentage: number
}

export interface MonthlyAnalytics {
  id: string
  machine_id: string | null
  year: number
  month: number
  total_kwh: number
  total_co2_kg: number
  total_cost_usd: number
  total_idle_hours: number
  kwh_change_pct: number | null
  co2_change_pct: number | null
  cost_change_pct: number | null
  aggregated_at: string
}

// ── Commands ──────────────────────────────────────────────────────────────

export interface ShutdownCommand {
  id: string
  machine_id: string
  issued_by: string
  status: 'pending' | 'executed' | 'rejected' | 'expired'
  idle_threshold_minutes: number
  rejection_reason: string | null
  notes: string | null
  issued_at: string
  expires_at: string
  executed_at: string | null
}

// ── Audit ─────────────────────────────────────────────────────────────────

export interface AuditLog {
  id: string
  user_id: string | null
  machine_id: string | null
  action: string
  resource_type: string | null
  details: Record<string, unknown> | null
  ip_address: string | null
  created_at: string
}

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

const BASE_URL = '/api/v1'

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

// Attach access token to every request
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('access_token')
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Auto-refresh on 401
api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean }
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      const refresh = localStorage.getItem('refresh_token')
      if (refresh) {
        try {
          const { data } = await axios.post(`${BASE_URL}/auth/refresh`, {
            refresh_token: refresh,
          })
          localStorage.setItem('access_token', data.access_token)
          localStorage.setItem('refresh_token', data.refresh_token)
          if (original.headers) {
            original.headers.Authorization = `Bearer ${data.access_token}`
          }
          return api(original)
        } catch {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  }
)

// ── Auth ──────────────────────────────────────────────────────────────────
export const authApi = {
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),
  register: (email: string, password: string, full_name: string) =>
    api.post('/auth/register', { email, password, full_name }),
  me: () => api.get('/auth/me'),
  refresh: (refresh_token: string) =>
    api.post('/auth/refresh', { refresh_token }),
}

// ── Machines ──────────────────────────────────────────────────────────────
export const machinesApi = {
  list: (params?: { page?: number; per_page?: number; status?: string; search?: string }) =>
    api.get('/machines', { params }),
  get: (id: string) => api.get(`/machines/${id}`),
  history: (id: string, hours = 24) =>
    api.get(`/machines/${id}/history`, { params: { hours } }),
  deactivate: (id: string) => api.delete(`/machines/${id}`),
}

// ── Analytics ─────────────────────────────────────────────────────────────
export const analyticsApi = {
  overview: () => api.get('/analytics/overview'),
  energyTimeseries: (hours = 24) =>
    api.get('/analytics/energy/timeseries', { params: { hours } }),
  co2Trend: (days = 30) =>
    api.get('/analytics/co2/trend', { params: { days } }),
  costProjection: () => api.get('/analytics/cost/projection'),
  monthly: (year?: number) =>
    api.get('/analytics/monthly', { params: year ? { year } : {} }),
  audit: (limit = 50) =>
    api.get('/analytics/audit', { params: { limit } }),
}

// ── Commands ──────────────────────────────────────────────────────────────
export const commandsApi = {
  issueShutdown: (machine_id: string, idle_threshold_minutes = 15, notes?: string) =>
    api.post('/commands/shutdown', { machine_id, idle_threshold_minutes, notes }),
  listMachineCommands: (machine_id: string) =>
    api.get(`/commands/shutdown/${machine_id}`),
}

// ── Users ─────────────────────────────────────────────────────────────────
export const usersApi = {
  list: () => api.get('/users'),
  get: (id: string) => api.get(`/users/${id}`),
  update: (id: string, data: Partial<{ full_name: string; role: string; is_active: boolean }>) =>
    api.patch(`/users/${id}`, data),
  delete: (id: string) => api.delete(`/users/${id}`),
}

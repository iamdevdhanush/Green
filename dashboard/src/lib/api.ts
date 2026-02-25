import axios from 'axios';

export const api = axios.create({
  baseURL: '',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let isRefreshing = false;
let failedQueue: Array<{ resolve: (token: string) => void; reject: (err: unknown) => void }> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((p) => {
    if (error) p.reject(error);
    else p.resolve(token!);
  });
  failedQueue = [];
};

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const orig = error.config;
    if (error.response?.status === 401 && !orig._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          orig.headers.Authorization = `Bearer ${token}`;
          return api(orig);
        });
      }
      orig._retry = true;
      isRefreshing = true;
      const refreshToken = typeof window !== 'undefined' ? localStorage.getItem('refresh_token') : null;
      if (!refreshToken) {
        isRefreshing = false;
        clearAuth();
        return Promise.reject(error);
      }
      try {
        const { data } = await axios.post('/api/auth/refresh', { refresh_token: refreshToken });
        if (typeof window !== 'undefined') {
          localStorage.setItem('access_token', data.access_token);
        }
        api.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;
        processQueue(null, data.access_token);
        orig.headers.Authorization = `Bearer ${data.access_token}`;
        return api(orig);
      } catch (err) {
        processQueue(err, null);
        clearAuth();
        return Promise.reject(err);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);

function clearAuth() {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    window.location.href = '/login';
  }
}

export const authAPI = {
  login: (username: string, password: string) =>
    api.post('/api/auth/login', { username, password }),
  logout: (refreshToken: string) =>
    api.post('/api/auth/logout', { refresh_token: refreshToken }),
  refresh: (refreshToken: string) =>
    api.post('/api/auth/refresh', { refresh_token: refreshToken }),
  verify: () => api.get('/api/auth/verify'),
  me: () => api.get('/api/auth/me'),
};

export const machinesAPI = {
  list: (params?: Record<string, unknown>) => api.get('/api/machines', { params }),
  get: (id: number) => api.get(`/api/machines/${id}`),
  update: (id: number, data: Record<string, unknown>) => api.patch(`/api/machines/${id}`, data),
  delete: (id: number) => api.delete(`/api/machines/${id}`),
  heartbeats: (id: number, params?: Record<string, unknown>) =>
    api.get(`/api/machines/${id}/heartbeats`, { params }),
  revokeToken: (id: number) => api.post(`/api/machines/${id}/revoke-token`),
};

export const dashboardAPI = {
  stats: () => api.get('/api/dashboard/stats'),
  energyTrend: (days: number) => api.get('/api/dashboard/energy-trend', { params: { days } }),
  topIdle: (limit: number) => api.get('/api/dashboard/top-idle', { params: { limit } }),
  recentActivity: (limit: number) => api.get('/api/dashboard/recent-activity', { params: { limit } }),
};

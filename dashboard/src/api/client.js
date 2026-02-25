import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL || '';

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach((p) => error ? p.reject(error) : p.resolve(token));
  failedQueue = [];
};

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const orig = error.config;
    if (error.response?.status === 401 && !orig._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => failedQueue.push({ resolve, reject }))
          .then((token) => { orig.headers.Authorization = `Bearer ${token}`; return api(orig); })
          .catch((e) => Promise.reject(e));
      }
      orig._retry = true;
      isRefreshing = true;
      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) { isRefreshing = false; clearAuth(); return Promise.reject(error); }
      try {
        const { data } = await axios.post(`${BASE_URL}/api/auth/refresh`, { refresh_token: refreshToken });
        localStorage.setItem('access_token', data.access_token);
        api.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;
        processQueue(null, data.access_token);
        orig.headers.Authorization = `Bearer ${data.access_token}`;
        return api(orig);
      } catch (e) {
        processQueue(e, null);
        clearAuth();
        return Promise.reject(e);
      } finally { isRefreshing = false; }
    }
    return Promise.reject(error);
  }
);

function clearAuth() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user');
  window.location.href = '/login';
}

export const authAPI = {
  login: (username, password) => api.post('/api/auth/login', { username, password }),
  logout: (refreshToken) => api.post('/api/auth/logout', { refresh_token: refreshToken }),
  refresh: (refreshToken) => api.post('/api/auth/refresh', { refresh_token: refreshToken }),
  verify: () => api.get('/api/auth/verify'),
  me: () => api.get('/api/auth/me'),
};

export const machinesAPI = {
  list: (params) => api.get('/api/machines', { params }),
  get: (id) => api.get(`/api/machines/${id}`),
  update: (id, data) => api.patch(`/api/machines/${id}`, data),
  delete: (id) => api.delete(`/api/machines/${id}`),
  heartbeats: (id, params) => api.get(`/api/machines/${id}/heartbeats`, { params }),
  revokeToken: (id) => api.post(`/api/machines/${id}/revoke-token`),
};

export const dashboardAPI = {
  stats: () => api.get('/api/dashboard/stats'),
  energyTrend: (days) => api.get('/api/dashboard/energy-trend', { params: { days } }),
  topIdle: (limit) => api.get('/api/dashboard/top-idle', { params: { limit } }),
  recentActivity: (limit) => api.get('/api/dashboard/recent-activity', { params: { limit } }),
};

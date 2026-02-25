// GreenOps API Client
import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL || '';

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

// Request interceptor: attach access token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Response interceptor: handle 401 with token refresh
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach((prom) => {
    if (error) prom.reject(error);
    else prom.resolve(token);
  });
  failedQueue = [];
};

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return api(originalRequest);
        }).catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        isRefreshing = false;
        clearAuthAndRedirect();
        return Promise.reject(error);
      }

      try {
        const { data } = await axios.post(`${BASE_URL}/api/auth/refresh`, {
          refresh_token: refreshToken,
        });

        const newToken = data.access_token;
        localStorage.setItem('access_token', newToken);
        api.defaults.headers.common.Authorization = `Bearer ${newToken}`;
        processQueue(null, newToken);
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        clearAuthAndRedirect();
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

function clearAuthAndRedirect() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user');
  window.location.href = '/login';
}

// Auth API
export const authAPI = {
  login: (username, password) =>
    api.post('/api/auth/login', { username, password }),
  logout: (refreshToken) =>
    api.post('/api/auth/logout', { refresh_token: refreshToken }),
  refresh: (refreshToken) =>
    api.post('/api/auth/refresh', { refresh_token: refreshToken }),
  verify: () => api.get('/api/auth/verify'),
  me: () => api.get('/api/auth/me'),
};

// Machines API
export const machinesAPI = {
  list: (params) => api.get('/api/machines', { params }),
  count: () => api.get('/api/machines/count'),
  get: (id) => api.get(`/api/machines/${id}`),
  update: (id, data) => api.patch(`/api/machines/${id}`, data),
  delete: (id) => api.delete(`/api/machines/${id}`),
  heartbeats: (id, params) => api.get(`/api/machines/${id}/heartbeats`, { params }),
  revokeToken: (id) => api.post(`/api/machines/${id}/revoke-token`),
};

// Dashboard API
export const dashboardAPI = {
  stats: () => api.get('/api/dashboard/stats'),
  energyTrend: (days) => api.get('/api/dashboard/energy-trend', { params: { days } }),
  topIdle: (limit) => api.get('/api/dashboard/top-idle', { params: { limit } }),
  recentActivity: (limit) => api.get('/api/dashboard/recent-activity', { params: { limit } }),
};

// Health
export const healthAPI = {
  check: () => api.get('/health'),
};

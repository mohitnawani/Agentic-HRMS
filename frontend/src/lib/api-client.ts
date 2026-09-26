import axios from "axios";
import { store } from "@/store/store";
import { setAccessToken, logout } from "@/store/authSlice";

const configuredApiUrl = (import.meta.env.VITE_API_URL as string | undefined)?.trim();
const renderApiHost = (import.meta.env.VITE_API_HOST as string | undefined)?.trim();

export const API_BASE_URL = (
  configuredApiUrl ||
  (renderApiHost ? `https://${renderApiHost}/api/v1` : "http://127.0.0.1:8000/api/v1")
).replace(/\/$/, "");

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

apiClient.interceptors.request.use((config) => {
  const token = store.getState().auth.accessToken;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let isRefreshing = false;
let pendingQueue: (() => void)[] = [];

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const refreshToken = store.getState().auth.refreshToken;

      if (!refreshToken) {
        store.dispatch(logout());
        return Promise.reject(error);
      }

      if (isRefreshing) {
        return new Promise((resolve) => {
          pendingQueue.push(() => resolve(apiClient(originalRequest)));
        });
      }

      isRefreshing = true;
      try {
        const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });
        store.dispatch(setAccessToken(data.access_token));
        pendingQueue.forEach((cb) => cb());
        pendingQueue = [];
        return apiClient(originalRequest);
      } catch (refreshError) {
        store.dispatch(logout());
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

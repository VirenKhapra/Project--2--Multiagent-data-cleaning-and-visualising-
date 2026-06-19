import axios from "axios";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  withCredentials: true,
});

let isRefreshing = false;
let waitQueue = [];

const processQueue = (error, newToken = null) => {
  waitQueue.forEach(({ resolve, reject }) =>
    error ? reject(error) : resolve(newToken),
  );
  waitQueue = [];
};

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const requestUrl = original?.url || "";
    const isLoginAttempt =
      requestUrl.includes("/auth/login") ||
      requestUrl.includes("/auth/register");
    const isRefreshAttempt = requestUrl.includes("/auth/refresh");

    if (error.response?.status !== 401) {
      return Promise.reject(error);
    }

    if (isLoginAttempt) {
      return Promise.reject(error);
    }

    if (isRefreshAttempt || original._retry) {
      if (window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
      return Promise.reject(error);
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        waitQueue.push({ resolve, reject });
      }).then((newToken) => {
        return api(original);
      });
    }

    original._retry = true;
    isRefreshing = true;

    try {
      await api.post("/auth/refresh");
      processQueue(null, true);
      return api(original);
    } catch (refreshError) {
      processQueue(refreshError, null);
      if (window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  },
);

export function websocketUrl(channel) {
  const url = new URL(API_BASE_URL);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = `/ws/${channel}`;
  return url.toString();
}

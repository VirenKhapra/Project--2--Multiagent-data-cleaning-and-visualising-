import React from "react";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api } from "../api/client.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [isCheckingSession, setIsCheckingSession] = useState(true);

  async function login(payload) {
    const response = await api.post("/auth/login", payload);
    setSession({ user: response.data });
    return response.data;
  }

  async function register(payload) {
    const response = await api.post("/auth/register", payload);
    setSession({ user: response.data });
    return response.data;
  }

  function updateUser(nextUser) {
    setSession((currentSession) => {
      if (!currentSession) return currentSession;
      const nextSession = { ...currentSession, user: nextUser };
      return nextSession;
    });
  }

  async function logout() {
    setSession(null);
    try {
      await api.post("/auth/logout");
    } catch {}
  }

  useEffect(() => {
    let isMounted = true;

    async function validateStoredSession() {
      setIsCheckingSession(true);
      try {
        const response = await api.get("/auth/me");
        if (isMounted) {
          setSession({ user: response.data });
        }
      } catch {
        if (isMounted) setSession(null);
      } finally {
        if (isMounted) setIsCheckingSession(false);
      }
    }

    validateStoredSession();

    return () => {
      isMounted = false;
    };
  }, []);

  const value = useMemo(
    () => ({
      user: session?.user || null,
      isAuthenticated: Boolean(session?.user),
      isCheckingSession,
      login,
      register,
      updateUser,
      logout,
    }),
    [isCheckingSession, session],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}

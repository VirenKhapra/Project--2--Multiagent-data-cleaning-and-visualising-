import React from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext.jsx";
import { getHomeRoute } from "../utils/finflowFormatters.js";

export default function ProtectedRoute({ roles = [] }) {
  const location = useLocation();
  const { isAuthenticated, isCheckingSession, user, logout } = useAuth();

  if (isCheckingSession) {
    return null;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (roles.length && !roles.includes(user?.role)) {
    const hasToken = new URLSearchParams(location.search).get("token");
    if (hasToken) {
      logout();
      return <Navigate to="/login" replace state={{ from: location }} />;
    }
    return <Navigate to={getHomeRoute(user?.role)} replace />;
  }

  return <Outlet />;
}

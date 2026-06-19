import React, { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { FiCheckCircle, FiAlertTriangle, FiLoader } from "react-icons/fi";

export default function VerifyPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState("verifying"); // verifying | success | error
  const [message, setMessage] = useState("");

  useEffect(() => {
    const token = searchParams.get("token");
    if (!token) {
      setStatus("error");
      setMessage("No verification token found. Please use the link from your email.");
      return;
    }

    async function verify() {
      try {
        const { data } = await api.post("/auth/verify-password-change", { token });
        setStatus("success");
        setMessage(data.message || "Password updated successfully.");
      } catch (err) {
        setStatus("error");
        setMessage(
          err.response?.data?.detail ||
          "Failed to verify password change. The link may have expired."
        );
      }
    }

    verify();
  }, [searchParams]);

  const handleLoginRedirect = () => {
    // Force full page reload to ensure all cookies/state are cleared
    window.location.assign("/login");
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)",
        padding: "2rem",
      }}
    >
      <div
        style={{
          background: "rgba(255,255,255,0.05)",
          backdropFilter: "blur(20px)",
          border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: "16px",
          padding: "3rem",
          maxWidth: "480px",
          width: "100%",
          textAlign: "center",
          color: "#fff",
        }}
      >
        {status === "verifying" && (
          <>
            <FiLoader
              size={48}
              style={{ animation: "spin 1s linear infinite", color: "#ffe600", marginBottom: "1.5rem" }}
            />
            <h2 style={{ fontSize: "1.5rem", marginBottom: "0.75rem" }}>Verifying your password change...</h2>
            <p style={{ color: "rgba(255,255,255,0.6)" }}>Please wait while we confirm your request.</p>
          </>
        )}

        {status === "success" && (
          <>
            <FiCheckCircle size={48} style={{ color: "#22c55e", marginBottom: "1.5rem" }} />
            <h2 style={{ fontSize: "1.5rem", marginBottom: "0.75rem" }}>Password Updated!</h2>
            <p style={{ color: "rgba(255,255,255,0.7)", marginBottom: "2rem", lineHeight: 1.6 }}>
              {message}
            </p>
            <button
              onClick={handleLoginRedirect}
              style={{
                background: "#ffe600",
                color: "#1a1a2e",
                border: "none",
                borderRadius: "10px",
                padding: "0.85rem 2.5rem",
                fontSize: "1rem",
                fontWeight: 700,
                cursor: "pointer",
                transition: "transform 0.15s, box-shadow 0.15s",
              }}
              onMouseOver={(e) => {
                e.currentTarget.style.transform = "translateY(-2px)";
                e.currentTarget.style.boxShadow = "0 8px 24px rgba(255,230,0,0.3)";
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.transform = "translateY(0)";
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              Log in with new password
            </button>
          </>
        )}

        {status === "error" && (
          <>
            <FiAlertTriangle size={48} style={{ color: "#ef4444", marginBottom: "1.5rem" }} />
            <h2 style={{ fontSize: "1.5rem", marginBottom: "0.75rem" }}>Verification Failed</h2>
            <p style={{ color: "rgba(255,255,255,0.7)", marginBottom: "2rem", lineHeight: 1.6 }}>
              {message}
            </p>
            <button
              onClick={() => navigate("/login")}
              style={{
                background: "transparent",
                color: "#ffe600",
                border: "2px solid #ffe600",
                borderRadius: "10px",
                padding: "0.85rem 2.5rem",
                fontSize: "1rem",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              Back to Login
            </button>
          </>
        )}
      </div>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

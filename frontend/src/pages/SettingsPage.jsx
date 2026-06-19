import React, { useState } from "react";
import { FiBell, FiLayers, FiLock, FiSliders, FiUser, FiX, FiMail } from "react-icons/fi";
import { useAuth } from "../auth/AuthContext.jsx";
import { api } from "../api/client.js";

export default function SettingsPage() {
  const { user } = useAuth();

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    setError("");

    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      await api.post("/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setShowModal(true);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to initiate password change.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ff-page-grid">
      <section className="ff-hero-panel ff-hero-panel--settings">
        <div>
          <p className="ff-eyebrow">Workspace settings</p>
          <h2 style={{ maxWidth: "100%" }}>
            Keep your FinFlow workspace predictable, secure, and tuned to how
            your team works.
          </h2>
        </div>
      </section>

      <section className="ff-settings-layout">
        <article className="ff-panel">
          <div className="ff-side-head">
            <FiUser size={16} />
            <strong>Profile</strong>
          </div>
          <div style={{
            display: "flex",
            flexDirection: "column",
            gap: "24px",
            background: "rgba(255, 255, 255, 0.02)",
            border: "1px solid rgba(255, 255, 255, 0.05)",
            borderRadius: "16px",
            padding: "24px",
            marginTop: "16px"
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
              <div style={{
                width: "64px",
                height: "64px",
                borderRadius: "50%",
                background: "linear-gradient(135deg, #ffe600, #ffb300)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#1a1a2e",
                flexShrink: 0,
                boxShadow: "0 8px 16px rgba(255, 230, 0, 0.15)"
              }}>
                <FiUser size={32} />
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <h3 style={{ margin: 0, fontSize: "22px", color: "#fff", fontWeight: 700 }}>
                  {user?.name || "Finance User"}
                </h3>
                <span style={{ color: "rgba(255, 255, 255, 0.6)", fontSize: "14px" }}>
                  {user?.email || "workspace@finflow.app"}
                </span>
              </div>
            </div>

            <div style={{ height: "1px", background: "rgba(255, 255, 255, 0.08)" }} />

            <div style={{ display: "flex", gap: "40px" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                <span style={{ fontSize: "12px", color: "rgba(255, 255, 255, 0.5)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 }}>Role</span>
                <div style={{
                  display: "inline-flex",
                  alignItems: "center",
                  background: "rgba(255, 255, 255, 0.08)",
                  padding: "6px 16px",
                  borderRadius: "999px",
                  fontSize: "14px",
                  fontWeight: 600,
                  color: "#fff",
                  textTransform: "capitalize"
                }}>
                  {user?.role || "employee"}
                </div>
              </div>
              
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                <span style={{ fontSize: "12px", color: "rgba(255, 255, 255, 0.5)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 }}>Default Output</span>
                <div style={{
                  display: "inline-flex",
                  alignItems: "center",
                  background: "rgba(255, 255, 255, 0.08)",
                  padding: "6px 16px",
                  borderRadius: "999px",
                  fontSize: "14px",
                  fontWeight: 600,
                  color: "#fff"
                }}>
                  PDF packs
                </div>
              </div>
            </div>
          </div>
        </article>

        <article className="ff-panel">
          <div className="ff-side-head">
            <FiLock size={16} />
            <strong>Security</strong>
          </div>
          <div className="ff-settings-stack">
            <div className="ff-settings-card ff-settings-card--dense">
              <strong>Change Password</strong>
              <p style={{ marginBottom: "1rem", color: "rgba(255,255,255,0.6)", fontSize: "0.85rem" }}>
                Enter your current password and a new password. A verification email will be sent to confirm the change.
              </p>
              <form onSubmit={handlePasswordChange} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <input
                  type="password"
                  placeholder="Current password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  required
                  style={inputStyle}
                />
                <input
                  type="password"
                  placeholder="New password (min 8 chars)"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  style={inputStyle}
                />
                <input
                  type="password"
                  placeholder="Confirm new password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  style={inputStyle}
                />
                {error && (
                  <p style={{ color: "#ef4444", fontSize: "0.85rem", margin: 0 }}>{error}</p>
                )}
                <button
                  type="submit"
                  disabled={loading}
                  style={{
                    background: "#ffe600",
                    color: "#1a1a2e",
                    border: "none",
                    borderRadius: "8px",
                    padding: "0.65rem 1.5rem",
                    fontWeight: 700,
                    fontSize: "0.9rem",
                    cursor: loading ? "not-allowed" : "pointer",
                    opacity: loading ? 0.6 : 1,
                    alignSelf: "flex-start",
                    transition: "transform 0.15s",
                  }}
                >
                  {loading ? "Sending..." : "Change Password"}
                </button>
              </form>
            </div>
            <div className="ff-settings-card ff-settings-card--dense">
              <strong>Manager escalation control</strong>
              <p>
                Decide whether failed or stalled jobs should appear earlier in
                the manager workspace versus staying with the submitting analyst
                first.
              </p>
            </div>
          </div>
        </article>
      </section>



      {/* Email Sent Confirmation Modal */}
      {showModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            backdropFilter: "blur(6px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
          }}
          onClick={() => setShowModal(false)}
        >
          <div
            style={{
              background: "rgba(30,30,50,0.95)",
              border: "1px solid rgba(255,230,0,0.2)",
              borderRadius: "16px",
              padding: "2.5rem",
              maxWidth: "440px",
              width: "90%",
              textAlign: "center",
              position: "relative",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setShowModal(false)}
              style={{
                position: "absolute",
                top: "1rem",
                right: "1rem",
                background: "none",
                border: "none",
                color: "rgba(255,255,255,0.5)",
                cursor: "pointer",
              }}
            >
              <FiX size={20} />
            </button>
            <FiMail size={48} style={{ color: "#ffe600", marginBottom: "1.25rem" }} />
            <h3 style={{ color: "#fff", fontSize: "1.25rem", marginBottom: "0.75rem" }}>
              Verification Email Sent
            </h3>
            <p style={{ color: "rgba(255,255,255,0.7)", lineHeight: 1.6, marginBottom: "1.5rem" }}>
              We've sent a verification link to your email address. Please click the link to confirm your password change.
              <br />
              <strong style={{ color: "#ffe600" }}>The link expires in 15 minutes.</strong>
            </p>
            <button
              onClick={() => setShowModal(false)}
              style={{
                background: "#ffe600",
                color: "#1a1a2e",
                border: "none",
                borderRadius: "10px",
                padding: "0.75rem 2rem",
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              Got it
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

const inputStyle = {
  background: "rgba(255,255,255,0.06)",
  border: "1px solid rgba(255,255,255,0.12)",
  borderRadius: "8px",
  padding: "0.65rem 1rem",
  color: "#fff",
  fontSize: "0.9rem",
  outline: "none",
  width: "100%",
  boxSizing: "border-box",
};

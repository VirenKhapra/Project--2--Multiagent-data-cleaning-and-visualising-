import React from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  FiAlertTriangle,
  FiArrowRight,
  FiExternalLink,
  FiRefreshCw,
  FiSearch,
  FiX,
} from "react-icons/fi";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client.js";
import PageHero from "../components/PageHero.jsx";
import StatusPill from "../components/StatusPill.jsx";
import { useWebSocket } from "../hooks/useWebSocket.js";

export default function AlertsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [entryFilter, setEntryFilter] = useState(searchParams.get("entry") || "");
  const [accountFilter, setAccountFilter] = useState(searchParams.get("account") || "");
  const [statusFilter, setStatusFilter] = useState("");
  const [selectedAlert, setSelectedAlert] = useState(null);

  const syncUrlFilters = useCallback((nextEntry, nextAccount) => {
    const params = new URLSearchParams();
    if (nextEntry.trim()) params.set("entry", nextEntry.trim());
    if (nextAccount.trim()) params.set("account", nextAccount.trim());
    setSearchParams(params, { replace: true });
  }, [setSearchParams]);

  const loadAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (entryFilter.trim()) params.set("entry", entryFilter.trim());
      if (accountFilter.trim()) params.set("account", accountFilter.trim());
      const response = await api.get(`/alerts${params.toString() ? `?${params.toString()}` : ""}`);
      setAlerts(Array.isArray(response.data) ? response.data : []);
    } finally {
      setLoading(false);
    }
  }, [accountFilter, entryFilter]);

  useEffect(() => {
    setEntryFilter(searchParams.get("entry") || "");
    setAccountFilter(searchParams.get("account") || "");
  }, [searchParams]);

  useEffect(() => {
    loadAlerts().catch(() => setAlerts([]));
  }, [loadAlerts]);

  useWebSocket("notifications", useCallback((event) => {
    if (!["dtcd_alert", "workflow_alert"].includes(event.event)) return;
    setAlerts((current) => [
      event.payload,
      ...current.filter((alert) => alert.id !== event.payload.id),
    ]);
  }, []));

  const filteredAlerts = useMemo(() => {
    const normalizedStatus = statusFilter.trim().toLowerCase();
    return alerts.filter((alert) => {
      if (!normalizedStatus) return true;
      return getAlertStatus(alert) === normalizedStatus;
    });
  }, [alerts, statusFilter]);

  function updateEntryFilter(value) {
    setEntryFilter(value);
    syncUrlFilters(value, accountFilter);
  }

  function updateAccountFilter(value) {
    setAccountFilter(value);
    syncUrlFilters(entryFilter, value);
  }

  function clearFilters() {
    setEntryFilter("");
    setAccountFilter("");
    setStatusFilter("");
    setSearchParams({}, { replace: true });
  }

  return (
    <div className="ff-page-grid">
      <PageHero
        eyebrow="Operations alerts"
        title="Validation failures and quarantined workflows."
        description="Review reconciliation alerts, inspect quarantined workflows, and jump directly into the audit view when follow-up is needed."
        actions={(
          <button
            className="ff-secondary-button"
            onClick={loadAlerts}
            disabled={loading}
            type="button"
          >
            <FiRefreshCw size={16} />
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        )}
      />

      <section className="ff-panel ff-panel--dense">
        <div className="ff-alert-filters">
          <label className="ff-search">
            <FiSearch size={15} />
            <input
              value={entryFilter}
              onChange={(event) => updateEntryFilter(event.target.value)}
              placeholder="Filter reference"
            />
          </label>
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="">All statuses</option>
            <option value="failed">Failed</option>
            <option value="quarantined">Quarantined</option>
          </select>
          <button
            className="ff-secondary-button"
            onClick={clearFilters}
            type="button"
          >
            <FiX size={16} />
            Clear
          </button>
        </div>
      </section>

      <section className="ff-panel">
        {filteredAlerts.length ? (
          <table className="ff-table">
            <thead>
              <tr>
                <th>Reference</th>
                <th>Code</th>
                <th>Subject</th>
                <th>Summary</th>
                <th>Status</th>
                <th>Received At</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredAlerts.map((alert) => (
                <tr key={alert.id}>
                  <td className="mono-cell">{alert.entry_no}</td>
                  <td className="mono-cell">{alert.account_code}</td>
                  <td>{alert.title || alert.sub_account}</td>
                  <td>{renderAlertSummary(alert)}</td>
                  <td>
                    <StatusPill
                      status={getAlertTone(alert)}
                      label={formatAlertLabel(alert)}
                    />
                  </td>
                  <td>{formatReceivedAt(alert.created_at)}</td>
                  <td>
                    <button
                      type="button"
                      className="ff-inline-action"
                      onClick={() => setSelectedAlert(alert)}
                    >
                      View details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="ff-alert-empty">
            <FiAlertTriangle size={22} />
            <strong>No validation alerts found</strong>
            <span>
              Validation failures and quarantined workflows will appear here as soon as they are raised.
            </span>
          </div>
        )}
      </section>

      {selectedAlert ? (
        <TransactionDetailModal
          alert={selectedAlert}
          onClose={() => setSelectedAlert(null)}
        />
      ) : null}
    </div>
  );
}

function TransactionDetailModal({ alert, onClose }) {
  if (alert.alert_type === "workflow_quarantine") {
    const detailRows = [
      ["Workflow", alert.entry_no || "-"],
      ["File", alert.sub_account || "-"],
      ["Reason code", alert.account_code || "-"],
      ["Received At", formatReceivedAt(alert.created_at || alert.received_at)],
      ["Status", formatAlertLabel(alert)],
    ];

    return (
      <div
        className="ff-alert-modal-backdrop"
        role="presentation"
        onClick={onClose}
      >
        <section
          className="ff-alert-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="alert-detail-title"
          onClick={(event) => event.stopPropagation()}
        >
          <header className="ff-alert-modal__head">
            <div>
              <p className="ff-eyebrow">Workflow quarantine</p>
              <h3 id="alert-detail-title">{alert.title || "Workflow quarantine alert"}</h3>
              <p className="ff-copy-muted">{alert.message || "No capable agent matched this workflow."}</p>
            </div>
            <button
              className="ff-secondary-button"
              type="button"
              aria-label="Close details"
              onClick={onClose}
            >
              <FiX size={16} />
            </button>
          </header>

          <dl className="ff-alert-detail-grid">
            {detailRows.map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value || "-"}</dd>
              </div>
            ))}
          </dl>

          {alert.upload_id ? (
            <div className="ff-alert-modal__footer">
              <Link to={`/jobs/${alert.upload_id}`} className="ff-inline-link">
                Open workflow audit <FiExternalLink size={14} />
              </Link>
            </div>
          ) : null}
        </section>
      </div>
    );
  }

  const debit = getDebitDetail(alert);
  const credit = getCreditDetail(alert);
  const detailRows = [
    ["Transaction ID", alert.transaction_id || alert.transactionId || alert.id],
    ["Upload ID", alert.upload_id || alert.uploadId || "-"],
    ["Entry No", alert.entry_no || "-"],
    ["Received At", formatReceivedAt(alert.created_at || alert.received_at)],
    ["Status", formatAlertLabel(alert)],
    ["Difference", formatCurrency(alert.difference)],
  ];

  return (
    <div
      className="ff-alert-modal-backdrop"
      role="presentation"
      onClick={onClose}
    >
      <section
        className="ff-alert-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="alert-detail-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="ff-alert-modal__head">
          <div>
            <p className="ff-eyebrow">Validation alert</p>
            <h3 id="alert-detail-title">Transaction detail</h3>
            <p className="ff-copy-muted">
              {alert.entry_no ? `Entry ${alert.entry_no}` : "Validation alert"}
            </p>
          </div>
          <button
            className="ff-secondary-button"
            type="button"
            aria-label="Close details"
            onClick={onClose}
          >
            <FiX size={16} />
          </button>
        </header>

        <div className="ff-alert-flow">
          <FlowCard
            tone="debit"
            title="From (Debit)"
            detail={debit}
            amountLabel="Debit amount"
          />
          <div className="ff-alert-flow__delta">
            <FiArrowRight size={22} />
            <span>Difference {formatCurrency(alert.difference)}</span>
          </div>
          <FlowCard
            tone="credit"
            title="To (Credit)"
            detail={credit}
            amountLabel="Credit amount"
          />
        </div>

        <dl className="ff-alert-detail-grid">
          {detailRows.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value || "-"}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}

function FlowCard({ tone, title, detail, amountLabel }) {
  return (
    <article className={`ff-alert-flow-card ff-alert-flow-card--${tone}`}>
      <span>{title}</span>
      <strong>{detail.name}</strong>
      <p>{detail.code}</p>
      <div>
        <small>{amountLabel}</small>
        <b>{formatCurrency(detail.amount)}</b>
      </div>
    </article>
  );
}

function getAlertStatus(alert) {
  const normalized = String(alert.status || "").trim().toLowerCase();
  if (normalized === "quarantined" || alert.alert_type === "workflow_quarantine") {
    return "quarantined";
  }
  return normalized || "failed";
}

function getAlertTone(alert) {
  return getAlertStatus(alert) === "quarantined" ? "quarantined" : "failed";
}

function formatAlertLabel(alert) {
  return getAlertStatus(alert) === "quarantined" ? "Quarantined" : "Failed";
}

function renderAlertSummary(alert) {
  if (alert.alert_type === "workflow_quarantine") {
    return alert.message || "Workflow is awaiting a capable agent.";
  }
  return formatCurrency(alert.difference);
}

function getDebitDetail(alert) {
  return {
    name: alert.debit_account_name || alert.from_account_name || alert.sub_account || "-",
    code: alert.debit_account_code || alert.from_account_code || alert.account_code || "-",
    amount: alert.debit_amount ?? alert.from_amount ?? alert.difference ?? 0,
  };
}

function getCreditDetail(alert) {
  return {
    name: alert.credit_account_name || alert.to_account_name || alert.credit_sub_account || "-",
    code: alert.credit_account_code || alert.to_account_code || "-",
    amount: alert.credit_amount ?? alert.to_amount ?? 0,
  };
}

function formatCurrency(value) {
  return Number(value || 0).toLocaleString("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  });
}

function formatReceivedAt(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

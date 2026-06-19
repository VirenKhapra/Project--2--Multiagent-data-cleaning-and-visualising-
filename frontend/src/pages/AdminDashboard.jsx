import React from "react";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  FiArrowRight,
  FiAlertTriangle,
  FiCheckCircle,
  FiCpu,
  FiHash,
  FiRefreshCw,
  FiUsers,
} from "react-icons/fi";
import {
  assignEmployee,
  assignQuarantinedJob,
  fetchEmployees,
  fetchAnalyticsKpis,
  fetchManagers,
  fetchQuarantinedJobs,
  fetchRegisteredAgents,
  reassignEmployee,
  retryQuarantinedJob,
} from "../api/finflow.js";
import { useLiveJobRefresh } from "../hooks/useLiveJobRefresh.js";
import { useAuth } from "../auth/AuthContext.jsx";
import MiniStat from "../components/MiniStat.jsx";
import PageHero from "../components/PageHero.jsx";
import StatusPill from "../components/StatusPill.jsx";
import {
  formatAgentName,
  formatCapabilityTag,
} from "../utils/finflowFormatters.js";

export default function AdminDashboard() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const {
    data: agents = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["agents"],
    queryFn: fetchRegisteredAgents,
  });
  const { data: analyticsKpis } = useQuery({
    queryKey: ["analytics-kpis"],
    queryFn: fetchAnalyticsKpis,
  });
  const { data: quarantinedJobs = [], isLoading: quarantinedLoading } = useQuery({
    queryKey: ["quarantined-jobs"],
    queryFn: fetchQuarantinedJobs,
  });
  const [selectedAgentByJob, setSelectedAgentByJob] = useState({});
  const [selectedManagerByEmployee, setSelectedManagerByEmployee] = useState({});
  const { data: managers = [] } = useQuery({
    queryKey: ["admin-managers"],
    queryFn: fetchManagers,
    enabled: isAdmin,
  });
  const { data: employees = [] } = useQuery({
    queryKey: ["admin-employees"],
    queryFn: fetchEmployees,
    enabled: isAdmin,
  });
  useLiveJobRefresh();

  const retryMutation = useMutation({
    mutationFn: retryQuarantinedJob,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["quarantined-jobs"] });
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const assignMutation = useMutation({
    mutationFn: ({ jobId, preferredAgentName }) =>
      assignQuarantinedJob(jobId, preferredAgentName),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["quarantined-jobs"] });
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const employeeAssignmentMutation = useMutation({
    mutationFn: ({ employeeId, managerId, isReassign }) =>
      (isReassign ? reassignEmployee(employeeId, managerId) : assignEmployee(employeeId, managerId)),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["admin-employees"] });
      await queryClient.invalidateQueries({ queryKey: ["admin-managers"] });
      await queryClient.invalidateQueries({ queryKey: ["manager-dashboard"] });
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const activeAgents = agents.filter(
    (agent) => agent.status === "active",
  ).length;
  const degradedAgents = agents.filter(
    (agent) => agent.status === "degraded",
  ).length;
  const totalInvocations = agents.reduce(
    (sum, agent) => sum + (agent.total_invocations || 0),
    0,
  );
  const workflowPlanner = analyticsKpis?.workflow_planner || {};
  const assignedEmployees = employees.filter((employee) => employee.assignment_status === "assigned").length;
  const unassignedEmployees = employees.filter((employee) => employee.assignment_status !== "assigned").length;
  const managerCoverage = managers.length;
  const mappedAgents = useMemo(
    () =>
      agents.map((agent) => ({
        name: agent.name,
        description: agent.description,
        capabilityTags: agent.capability_tags || [],
        inputFormats: agent.input_formats || [],
        outputFormats: agent.output_formats || [],
        status: agent.status,
        lastHeartbeat: agent.last_heartbeat
          ? new Date(agent.last_heartbeat).toLocaleString("en-IN", {
              day: "2-digit",
              month: "short",
              hour: "2-digit",
              minute: "2-digit",
            })
          : "No heartbeat yet",
        totalInvocations: agent.total_invocations || 0,
      })),
    [agents],
  );

  if (isLoading) {
    return (
      <div className="ff-page-grid">
        <section className="ff-panel">
          <h2>Loading agent registry...</h2>
        </section>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="ff-page-grid">
        <section className="ff-panel">
          <h2>We could not load the agent registry.</h2>
          <p className="ff-copy-muted">
            Run the latest backend migration and check the API.
          </p>
        </section>
      </div>
    );
  }

  return (
    <div className="ff-page-grid">
      <PageHero
        className="ff-hero-panel--registry"
        eyebrow="Admin dashboard"
        title={`${activeAgents} agents online, ${degradedAgents} need attention.`}
        description={`${activeAgents} agents online, ${degradedAgents} need attention, ${totalInvocations} invocations processed across the current fleet.`}
        actions={
          <>
            <MiniStat
              icon={<FiCheckCircle size={16} />}
              value={activeAgents}
              label="Active agents"
            />
            <MiniStat
              icon={<FiAlertTriangle size={16} />}
              value={degradedAgents}
              label="Degraded"
            />
            <MiniStat
              icon={<FiHash size={16} />}
              value={totalInvocations}
              label="Total invocations"
            />
            <MiniStat
              icon={<FiAlertTriangle size={16} />}
              value={quarantinedJobs.length}
              label="Quarantined jobs"
            />
          </>
        }
      />

      <section className="ff-panel">
        <div className="ff-panel__head">
          <div>
            <p className="ff-eyebrow">Workflow planner</p>
            <h2>Orchestrator activity</h2>
            <p className="ff-copy-muted">
              Planning is tracked separately from leaf agents so the control plane stays visible without inflating agent telemetry.
            </p>
          </div>
        </div>

        <div className="ff-signal-grid ff-signal-grid--tight">
          <MiniStat
            icon={<FiCpu size={16} />}
            value={workflowPlanner.total_runs ?? 0}
            label="Planner runs"
          />
          <MiniStat
            icon={<FiHash size={16} />}
            value={workflowPlanner.last_run_at ? formatPlannerTime(workflowPlanner.last_run_at) : "No runs yet"}
            label="Last planned"
          />
          <article className="ff-signal-card ff-signal-card--text">
            <span>Latest planner note</span>
            <strong>{workflowPlanner.latest_summary || "No planner summary is available yet."}</strong>
          </article>
        </div>

        {Array.isArray(workflowPlanner.recent_runs) && workflowPlanner.recent_runs.length > 0 && (
          <div className="ff-registry-section" style={{ marginTop: 18 }}>
            <span className="ff-section-label">Recent planner decisions</span>
            <div className="ff-audit-list">
              {workflowPlanner.recent_runs.map((run) => (
                <div key={`${run.upload_id}-${run.planned_at}`} className="ff-audit-row">
                  <strong style={{ width: 280, wordBreak: "break-all", flexShrink: 0, paddingRight: 16 }}>{run.filename}</strong>
                  <span style={{ flex: 1, minWidth: 0 }}>{run.summary}</span>
                  <p style={{ whiteSpace: "nowrap", marginLeft: 16 }}>{formatPlannerTime(run.planned_at)}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {isAdmin ? (
        <section className="ff-panel">
          <div className="ff-panel__head">
            <div>
              <p className="ff-eyebrow">Team assignments</p>
              <h2>Manager to employee coverage</h2>
              <p className="ff-copy-muted">
                Assign employees to managers from the same control surface so
                dashboard visibility and review ownership stay aligned.
              </p>
            </div>
          </div>

          <div className="ff-signal-grid ff-signal-grid--tight">
            <MiniStat
              icon={<FiUsers size={16} />}
              value={managerCoverage}
              label="Managers"
            />
            <MiniStat
              icon={<FiCheckCircle size={16} />}
              value={assignedEmployees}
              label="Assigned employees"
            />
            <MiniStat
              icon={<FiAlertTriangle size={16} />}
              value={unassignedEmployees}
              label="Unassigned employees"
            />
          </div>

          <div className="ff-table-grid" style={{ marginTop: 18 }}>
            <table className="ff-table">
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Status</th>
                  <th>Current manager</th>
                  <th>Assign to</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {employees.map((employee) => {
                  const selectedManager =
                    selectedManagerByEmployee[employee.id]
                    || employee.manager_id
                    || managers[0]?.id
                    || "";
                  const isReassign = employee.assignment_status === "assigned";

                  return (
                    <tr key={employee.id}>
                      <td>
                        <strong>{employee.name}</strong>
                        <div className="ff-copy-muted">{employee.email}</div>
                      </td>
                      <td>
                        <StatusPill
                          status={isReassign ? "complete" : "quarantined"}
                          label={isReassign ? "Assigned" : "Unassigned"}
                        />
                      </td>
                      <td>{employee.manager_name || "Not assigned"}</td>
                      <td>
                        <select
                          className="form-input"
                          value={selectedManager}
                          onChange={(event) =>
                            setSelectedManagerByEmployee((current) => ({
                              ...current,
                              [employee.id]: event.target.value,
                            }))
                          }
                          disabled={!managers.length}
                        >
                          <option value="">Select manager</option>
                          {managers.map((manager) => (
                            <option key={manager.id} value={manager.id}>
                              {manager.name} ({manager.assigned_employee_count})
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={() =>
                            employeeAssignmentMutation.mutate({
                              employeeId: employee.id,
                              managerId: selectedManager,
                              isReassign,
                            })
                          }
                          disabled={
                            !selectedManager
                            || selectedManager === employee.manager_id
                            || employeeAssignmentMutation.isPending
                          }
                        >
                          <FiArrowRight size={14} />
                          {isReassign ? "Reassign" : "Assign"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {!employees.length ? (
              <div className="ff-copy-muted" style={{ padding: 16 }}>
                No employees are available for assignment yet.
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      <section className="ff-registry-grid ff-registry-grid--balanced">
        {mappedAgents.map((agent) => (
          <article
            key={agent.name}
            className="ff-registry-card ff-registry-card--refined"
          >
            <div className="ff-registry-card__top">
              <div className="ff-registry-card__title">
                <div className="ff-registry-card__icon">
                  <FiCpu size={18} />
                </div>
                <div>
                  <h3>{formatAgentName(agent.name)}</h3>
                  <p>{agent.description}</p>
                </div>
              </div>
              <StatusPill
                status={agent.status}
                label={
                  agent.status === "degraded" ? "Needs attention" : undefined
                }
              />
            </div>

            <div className="ff-registry-section">
              <span className="ff-section-label">Capability tags</span>
              <div className="ff-tag-list">
                {agent.capabilityTags.map((tag) => (
                  <span key={tag} title={formatCapabilityTag(tag)}>
                    {formatCapabilityTag(tag)}
                  </span>
                ))}
              </div>
            </div>

            <div className="ff-registry-metrics">
              <div>
                <span>Input formats</span>
                <strong>{agent.inputFormats.join(", ") || "-"}</strong>
              </div>
              <div>
                <span>Output formats</span>
                <strong>{agent.outputFormats.join(", ") || "-"}</strong>
              </div>
              <div>
                <span>Total invocations</span>
                <strong>{agent.totalInvocations}</strong>
              </div>
              <div>
                <span>Last heartbeat</span>
                <strong>{agent.lastHeartbeat}</strong>
              </div>
            </div>
          </article>
        ))}

        {!mappedAgents.length && (
          <article className="ff-panel">
            <p className="ff-copy-muted">
              No agents are registered yet. The registry screen is wired and
              ready once your backend agents start registering themselves.
            </p>
          </article>
        )}
      </section>

      <section className="ff-panel">
        <div className="ff-panel__head">
          <div>
            <p className="ff-eyebrow">Quarantine queue</p>
            <h2>Quarantined jobs</h2>
            <p className="ff-copy-muted">
              Jobs quarantined because part of the workflow is not currently
              supported. Retry after a new agent is added, or assign a
              preferred agent before reprocessing.
            </p>
          </div>
          <span className="ff-copy-muted">
            {quarantinedLoading ? "Refreshing..." : `${quarantinedJobs.length} quarantined`}
          </span>
        </div>

        <div className="ff-table-grid">
          <table className="ff-table">
            <thead>
              <tr>
                <th>Workflow</th>
                <th>File</th>
                <th>Status</th>
                <th>Preferred agent</th>
                <th>Suggested agent</th>
                <th>Submitted</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {quarantinedJobs.map((job) => {
                const selectedAgent =
                  selectedAgentByJob[job.backendId] ||
                  job.preferredAgentName ||
                  agents[0]?.name ||
                  "";

                return (
                  <tr key={job.backendId}>
                    <td className="mono-cell">{job.id}</td>
                    <td>{job.fileName}</td>
                    <td>
                      <StatusPill status={job.status} label="Quarantined" />
                    </td>
                    <td>{job.preferredAgentName || "-"}</td>
                    <td>{job.availableAgents?.[0] || "No match yet"}</td>
                    <td>{formatWhen(job.submittedAt)}</td>
                    <td>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        <select
                          className="form-input"
                          value={selectedAgent}
                          onChange={(event) =>
                            setSelectedAgentByJob((current) => ({
                              ...current,
                              [job.backendId]: event.target.value,
                            }))
                          }
                          disabled={!agents.length}
                        >
                          <option value="">Select agent</option>
                          {agents.map((agent) => (
                            <option key={agent.id} value={agent.name}>
                              {agent.name}
                            </option>
                          ))}
                        </select>
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={() => retryMutation.mutate(job.backendId)}
                          disabled={retryMutation.isPending}
                        >
                          <FiRefreshCw size={14} />
                          Retry
                        </button>
                        <button
                          className="secondary-button"
                          type="button"
                          onClick={() =>
                            assignMutation.mutate({
                              jobId: job.backendId,
                              preferredAgentName: selectedAgent,
                            })
                          }
                          disabled={!selectedAgent || assignMutation.isPending}
                        >
                          <FiCpu size={14} />
                          Assign
                        </button>
                        <Link className="ff-inline-link" to={`/jobs/${job.backendId}`}>
                          Review
                        </Link>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {!quarantinedJobs.length && (
            <div className="ff-copy-muted" style={{ padding: 16 }}>
              No quarantined jobs right now. New unmatched workflows will appear here.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function formatWhen(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatPlannerTime(value) {
  if (!value) return "No runs yet";
  return new Date(value).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

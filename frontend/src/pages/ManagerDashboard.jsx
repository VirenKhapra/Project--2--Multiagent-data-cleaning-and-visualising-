import React from "react";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchJobs, fetchRegisteredAgents } from "../api/finflow.js";
import { useLiveJobRefresh } from "../hooks/useLiveJobRefresh.js";
import PageHero from "../components/PageHero.jsx";
import StatCard from "../components/StatCard.jsx";
import { formatAgentName, formatDateTime } from "../utils/finflowFormatters.js";

const statusColors = {
  Complete: "#5ac88c",
  Running: "#ffe600",
  Quarantined: "#ffb25c",
  Failed: "#dc6060",
};

const tooltipStyle = {
  backgroundColor: "rgba(34, 34, 46, 0.96)",
  border: "1px solid rgba(45, 45, 58, 0.9)",
  borderRadius: "14px",
  color: "#ffffff",
  boxShadow: "0 16px 34px rgba(0, 0, 0, 0.28)",
};

const tooltipLabelStyle = {
  color: "#ffffff",
};

function startOfLocalDay(value) {
  const date = new Date(value);
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function daysAgo(count) {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate() - count);
}

function averageCompletionMinutes(jobs) {
  const completed = jobs.filter(
    (job) => job.status === "complete" && job.submittedAt && job.completedAt,
  );
  if (!completed.length) return 0;

  const totalMinutes = completed.reduce((sum, job) => {
    const started = new Date(job.submittedAt).getTime();
    const finished = new Date(job.completedAt).getTime();
    return sum + Math.max(0, Math.round((finished - started) / 60000));
  }, 0);

  return Math.round(totalMinutes / completed.length);
}

function buildCompletionTrend(jobs) {
  const labels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const start = daysAgo(6);

  return Array.from({ length: 7 }, (_, index) => {
    const day = new Date(
      start.getFullYear(),
      start.getMonth(),
      start.getDate() + index,
    );
    const dayJobs = jobs.filter((job) => {
      if (job.status !== "complete" || !job.completedAt || !job.submittedAt)
        return false;
      const completedDay = startOfLocalDay(job.completedAt);
      return completedDay.getTime() === day.getTime();
    });

    const minutes = averageCompletionMinutes(dayJobs);
    return {
      day: labels[day.getDay()],
      minutes,
    };
  });
}

function buildWorkloadRows(jobs) {
  const map = new Map();

  jobs.forEach((job) => {
    const name = job.submittedBy || "Unknown owner";
    const entry = map.get(name) || {
      name,
      jobs: 0,
      completed: 0,
      latestSubmittedAt: null,
    };

    entry.jobs += 1;
    if (job.status === "complete") entry.completed += 1;
    if (
      !entry.latestSubmittedAt ||
      new Date(job.submittedAt) > new Date(entry.latestSubmittedAt)
    ) {
      entry.latestSubmittedAt = job.submittedAt;
    }

    map.set(name, entry);
  });

  return [...map.values()]
    .map((entry) => ({
      ...entry,
      successRate: entry.jobs
        ? `${Math.round((entry.completed / entry.jobs) * 100)}%`
        : "0%",
    }))
    .sort((left, right) => right.jobs - left.jobs)
    .slice(0, 6);
}

function formatHeartbeat(value) {
  if (!value) return "No heartbeat yet";
  return formatDateTime(value);
}

export default function ManagerDashboard() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["manager-dashboard"],
    queryFn: async () => {
      const [jobs, agents] = await Promise.all([
        fetchJobs(),
        fetchRegisteredAgents(),
      ]);
      return { jobs, agents };
    },
  });
  useLiveJobRefresh();

  const jobs = data?.jobs || [];
  const agents = data?.agents || [];

  const dashboard = useMemo(() => {
    const todayStart = daysAgo(0);
    const weekStart = daysAgo(6);
    const monthStart = new Date(
      new Date().getFullYear(),
      new Date().getMonth(),
      1,
    );

    const jobsToday = jobs.filter(
      (job) => job.submittedAt && new Date(job.submittedAt) >= todayStart,
    ).length;
    const jobsThisWeek = jobs.filter(
      (job) => job.submittedAt && new Date(job.submittedAt) >= weekStart,
    ).length;
    const jobsThisMonth = jobs.filter(
      (job) => job.submittedAt && new Date(job.submittedAt) >= monthStart,
    ).length;
    const avgCompletion = averageCompletionMinutes(jobs);
    const completedJobs = jobs.filter(
      (job) => job.status === "complete",
    ).length;
    const completionRate = jobs.length
      ? Math.round((completedJobs / jobs.length) * 100)
      : 0;
    const quarantinedJobs = jobs.filter(
      (job) => job.status === "quarantined",
    ).length;
    const runningJobs = jobs.filter((job) => job.status === "running").length;
    const failedJobs = jobs.filter((job) => job.status === "failed").length;
    const activeAgents = agents.filter(
      (agent) => agent.status === "active",
    ).length;

    const statusBreakdown = [
      { name: "Complete", value: completedJobs, fill: statusColors.Complete },
      { name: "Running", value: runningJobs, fill: statusColors.Running },
      { name: "Quarantined", value: quarantinedJobs, fill: statusColors.Quarantined },
      { name: "Failed", value: failedJobs, fill: statusColors.Failed },
    ];

    const completionTrend = buildCompletionTrend(jobs);
    const trendValues = completionTrend
      .map((entry) => entry.minutes)
      .filter((value) => value > 0);
    const trendMin = trendValues.length
      ? Math.max(0, Math.min(...trendValues) - 2)
      : 0;
    const trendMax = trendValues.length ? Math.max(...trendValues) + 2 : 10;

    const utilizationData = agents
      .map((agent) => ({
        name: agent.name,
        label: formatAgentName(agent.name),
        invocations: agent.total_invocations || 0,
      }))
      .sort((left, right) => right.invocations - left.invocations)
      .slice(0, 6);

    const watchlist = agents
      .map((agent) => ({
        name: agent.name,
        status: agent.status,
        lastHeartbeat: formatHeartbeat(agent.last_heartbeat),
        invocations: agent.total_invocations || 0,
      }))
      .sort((left, right) => {
        const score = { degraded: 0, idle: 1, active: 2 };
        return (score[left.status] ?? 3) - (score[right.status] ?? 3);
      });

    return {
      jobsToday,
      jobsThisWeek,
      jobsThisMonth,
      avgCompletion,
      completionRate,
      quarantinedJobs,
      runningJobs,
      activeAgents,
      totalAgents: agents.length,
      statusBreakdown,
      completionTrend,
      trendMin,
      trendMax,
      utilizationData,
      watchlist,
      workloadRows: buildWorkloadRows(jobs),
    };
  }, [agents, jobs]);

  if (isLoading) {
    return (
      <div className="ff-page-grid">
        <section className="ff-panel">
          <h2>Loading manager dashboard...</h2>
        </section>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="ff-page-grid">
        <section className="ff-panel">
          <h2>We could not load manager telemetry.</h2>
          <p className="ff-copy-muted">
            Check the backend connection and agent registry endpoints, then try
            again.
          </p>
        </section>
      </div>
    );
  }

  return (
    <div className="ff-page-grid">
      <PageHero
        className="ff-page-hero--compact"
        eyebrow="Manager dashboard"
        title={`System is healthy | ${dashboard.jobsToday} jobs submitted today.`}
        description={`${dashboard.quarantinedJobs} quarantined, ${dashboard.runningJobs} running right now, ${dashboard.activeAgents} of ${dashboard.totalAgents} agents active.`}
      />

      <section className="ff-panel ff-panel--dense">
        <div className="ff-stats-grid">
            <StatCard
              label="Jobs today"
              value={dashboard.jobsToday}
              meta={`${dashboard.quarantinedJobs} quarantined for review`}
            />
          <StatCard
            label="Jobs this week"
            value={dashboard.jobsThisWeek}
            meta={`${dashboard.completionRate}% completed successfully`}
          />
          <StatCard
            label="Jobs this month"
            value={dashboard.jobsThisMonth}
            meta={`${dashboard.activeAgents}/${dashboard.totalAgents} agents active`}
          />
          <StatCard
            label="Average completion"
              value={`${dashboard.avgCompletion}m`}
              meta="Measured from submitted to completed jobs"
            />
        </div>
      </section>

      <section className="ff-chart-grid">
        <article className="ff-panel">
          <div className="ff-panel__head">
            <div>
              <p className="ff-eyebrow">Jobs by status</p>
              <h3>Current mix</h3>
            </div>
          </div>
          <div className="ff-chart-wrap">
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={dashboard.statusBreakdown}
                  innerRadius={64}
                  outerRadius={92}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {dashboard.statusBreakdown.map((entry) => (
                    <Cell key={entry.name} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={tooltipStyle}
                  labelStyle={tooltipLabelStyle}
                  itemStyle={tooltipLabelStyle}
                />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="ff-panel">
          <div className="ff-panel__head">
            <div>
              <p className="ff-eyebrow">Average completion time</p>
              <h3>7-day trend</h3>
            </div>
          </div>
          <div className="ff-chart-wrap">
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={dashboard.completionTrend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2d2d3a" />
                <XAxis dataKey="day" stroke="#8080a0" />
                <YAxis
                  stroke="#8080a0"
                  domain={[dashboard.trendMin, dashboard.trendMax]}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  labelStyle={tooltipLabelStyle}
                  itemStyle={tooltipLabelStyle}
                />
                <Line
                  type="monotone"
                  dataKey="minutes"
                  stroke="#ffe600"
                  strokeWidth={3}
                  dot={{ r: 3, fill: "#ffe600" }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="ff-panel">
          <div className="ff-panel__head">
            <div>
              <p className="ff-eyebrow">Agent utilisation</p>
              <h3>Most-invoked agents</h3>
            </div>
          </div>
          <div className="ff-chart-wrap">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={dashboard.utilizationData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2d2d3a" />
                <XAxis
                  dataKey="label"
                  stroke="#8080a0"
                  tick={{ fontSize: 11 }}
                  interval={0}
                  angle={-10}
                  textAnchor="end"
                  height={70}
                />
                <YAxis stroke="#8080a0" />
                <Tooltip
                  contentStyle={tooltipStyle}
                  labelStyle={tooltipLabelStyle}
                  itemStyle={tooltipLabelStyle}
                />
                <Bar
                  dataKey="invocations"
                  fill="#ffe600"
                  radius={[8, 8, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="ff-panel">
          <div className="ff-panel__head">
            <div>
              <p className="ff-eyebrow">Queue and health</p>
              <h3>Live operating signals</h3>
            </div>
          </div>
          <div className="ff-ops-cards">
            <div className="ff-ops-card">
              <span>Live queue depth</span>
              <strong>{dashboard.runningJobs}</strong>
              <small>Jobs actively moving through the workflow</small>
            </div>
            <div className="ff-ops-card">
              <span>Agent health</span>
              <strong>
                {dashboard.activeAgents}/{dashboard.totalAgents}
              </strong>
              <small>Active vs total registered agents</small>
            </div>
          </div>
        </article>
      </section>

      <section className="ff-table-grid">
        <article className="ff-panel">
          <div className="ff-panel__head">
            <div>
              <p className="ff-eyebrow">Agent fleet health</p>
              <h3>Risk watchlist</h3>
            </div>
          </div>
          <table className="ff-table">
            <thead>
              <tr>
                <th>Agent</th>
                <th>Status</th>
                <th>Last heartbeat</th>
                <th>Invocations</th>
              </tr>
            </thead>
            <tbody>
              {dashboard.watchlist.map((agent) => (
                <tr key={agent.name}>
                  <td>{formatAgentName(agent.name)}</td>
                  <td>
                    <span
                      className={`ff-health ff-health--${agent.status === "degraded" ? "risk" : agent.status === "idle" ? "watch" : "good"}`}
                    >
                      {agent.status}
                    </span>
                  </td>
                  <td>{agent.lastHeartbeat}</td>
                  <td>{agent.invocations}</td>
                </tr>
              ))}
              {!dashboard.watchlist.length && (
                <tr>
                  <td colSpan="4">No agent telemetry is available yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </article>

        <article className="ff-panel">
          <div className="ff-panel__head">
            <div>
              <p className="ff-eyebrow">Jobs per team member</p>
              <h3>Live workload table</h3>
            </div>
          </div>
          <table className="ff-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Jobs</th>
                <th>Success rate</th>
                <th>Last submission</th>
              </tr>
            </thead>
            <tbody>
              {dashboard.workloadRows.map((member) => (
                <tr key={member.name}>
                  <td>{member.name}</td>
                  <td>{member.jobs}</td>
                  <td>{member.successRate}</td>
                  <td>
                    {member.latestSubmittedAt
                      ? formatDateTime(member.latestSubmittedAt)
                      : "No submissions"}
                  </td>
                </tr>
              ))}
              {!dashboard.workloadRows.length && (
                <tr>
                  <td colSpan="4">No team workload data is available yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </article>
      </section>
    </div>
  );
}

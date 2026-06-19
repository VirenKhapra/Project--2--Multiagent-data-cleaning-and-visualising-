import React from "react";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  FiArrowRight,
  FiClock,
  FiFileText,
  FiPlayCircle,
} from "react-icons/fi";
import { fetchJobs } from "../api/finflow.js";
import { useLiveJobRefresh } from "../hooks/useLiveJobRefresh.js";
import PageHero from "../components/PageHero.jsx";
import StatCard from "../components/StatCard.jsx";
import StatusPill from "../components/StatusPill.jsx";
import {
  formatDateTime,
  formatStepStatus,
  summarizeInstruction,
} from "../utils/finflowFormatters.js";

export default function Dashboard() {
  const {
    data: visibleJobs = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["jobs"],
    queryFn: fetchJobs,
  });
  useLiveJobRefresh();
  const running = visibleJobs.filter((job) => job.status === "running").length;
  const quarantined = visibleJobs.filter(
    (job) => job.status === "quarantined",
  ).length;
  const complete = visibleJobs.filter(
    (job) => job.status === "complete",
  ).length;
  const failed = visibleJobs.filter((job) => job.status === "failed").length;
  const spotlight = visibleJobs[0] || null;
  const recentActivity = useMemo(() => visibleJobs.slice(0, 4), [visibleJobs]);

  if (isLoading) {
    return (
      <div className="ff-page-grid">
        <section className="ff-panel">
          <h2>Loading your jobs...</h2>
        </section>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="ff-page-grid">
        <section className="ff-panel">
          <h2>We could not load your jobs right now.</h2>
          <p className="ff-copy-muted">
            Check that the backend is running and try again.
          </p>
        </section>
      </div>
    );
  }

  return (
    <div className="ff-page-grid ff-dashboard-page">
      <PageHero
        eyebrow="Workflow overview"
        title="What needs your attention right now."
        description="Submit new work, keep an eye on queue pressure, and jump straight into the jobs that need your attention."
        actions={
          <>
            <Link to="/jobs/new" className="ff-primary-button">
              Create a new job <FiArrowRight size={15} />
            </Link>
            <Link to="/jobs" className="ff-secondary-button">
              Open full job list
            </Link>
          </>
        }
      />

      <section className="ff-stats-grid">
        <StatCard
          label="Running now"
          value={running}
          icon={<FiPlayCircle size={16} />}
          tone="running"
        />
        <StatCard
          label="Quarantined"
          value={quarantined}
          icon={<FiClock size={16} />}
          tone="failed"
        />
        <StatCard
          label="Total jobs"
          value={visibleJobs.length}
          icon={<FiArrowRight size={16} />}
          tone="complete"
        />
        <StatCard
          label="Completed"
          value={complete}
          icon={<FiFileText size={16} />}
          tone="complete"
        />
        <StatCard label="Failed" value={failed} icon={<FiArrowRight size={16} />} tone="failed" />
      </section>

      <section className="ff-two-column">
        <article className="ff-panel">
          {spotlight ? (
            <>
              <div className="ff-panel__head">
                <div>
                  <p className="ff-eyebrow">Active now</p>
                  <h3>{spotlight.title}</h3>
                </div>
                <StatusPill status={spotlight.status} />
              </div>
              <p className="ff-copy-muted">{spotlight.instruction}</p>
              {spotlight.jobSummary ? (
                <p className="ff-copy-muted">{spotlight.jobSummary}</p>
              ) : null}
              <div className="ff-key-metrics">
                <div>
                  <span>Job ID</span>
                  <strong>{spotlight.id}</strong>
                </div>
                <div>
                  <span>Input file</span>
                  <strong>{spotlight.fileName}</strong>
                </div>
                <div>
                  <span>Output</span>
                  <strong>{spotlight.outputFormat}</strong>
                </div>
                <div>
                  <span>Submitted</span>
                  <strong>{formatDateTime(spotlight.submittedAt)}</strong>
                </div>
              </div>
              <div className="ff-stage-progress" aria-label="Pipeline progress">
                {Array.isArray(spotlight?.steps) ? spotlight.steps.map((step) => (
                  <div
                    key={step.name}
                    className={`ff-stage-progress__item is-${step.status}`}
                  >
                    <div className="ff-stage-progress__topline">
                      <strong>{step.name}</strong>
                      <span>{formatStepStatus(step.status)}</span>
                    </div>
                    <div className="ff-stage-progress__track">
                      <span className="ff-stage-progress__fill" />
                    </div>
                  </div>
                )) : null}
              </div>
               <Link
                 to={`/jobs/${spotlight.backendId}`}
                 className="ff-inline-link"
               >
                 Open detailed audit view
               </Link>
            </>
          ) : (
            <>
              <div className="ff-panel__head">
                <div>
                  <p className="ff-eyebrow">Active now</p>
                  <h3>No jobs yet</h3>
                </div>
              </div>
              <p className="ff-copy-muted">
                Submit your first finance workflow and it will appear here.
              </p>
              <Link to="/jobs/new" className="ff-inline-link">
                Create your first job
              </Link>
            </>
          )}
        </article>

        <article className="ff-panel">
          <div className="ff-panel__head">
            <div>
              <p className="ff-eyebrow">Recent activity</p>
              <h3>Latest job movement</h3>
            </div>
          </div>
          <div className="ff-activity-list">
            {recentActivity.map((job) => (
              <Link
                to={`/jobs/${job.backendId}`}
                key={job.backendId}
                className="ff-activity-card"
              >
                <div>
                  <strong>{job.id}</strong>
                  <p>{summarizeInstruction(job.instruction)}</p>
                </div>
                <div className="ff-activity-card__meta">
                  <StatusPill status={job.status} />
                  <small>{formatDateTime(job.submittedAt)}</small>
                </div>
              </Link>
            ))}
            {!recentActivity.length && (
              <div className="ff-copy-muted">
                No recent workflow activity yet.
              </div>
            )}
          </div>
        </article>
      </section>
    </div>
  );
}

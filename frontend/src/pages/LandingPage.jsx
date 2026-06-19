import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import { getHomeRoute } from "../utils/finflowFormatters.js";
import eyBackground from "../asset/ey-background.png";

export default function LandingPage() {
  const { isAuthenticated, user } = useAuth();
  const navigate = useNavigate();

  React.useEffect(() => {
    if (isAuthenticated) {
      navigate(getHomeRoute(user?.role), { replace: true });
    }
  }, [isAuthenticated, navigate, user?.role]);

  return (
    <main
      className="ff-marketing ff-marketing--landing"
      style={{
        backgroundImage: `linear-gradient(135deg, rgba(10, 10, 16, 0.72), rgba(10, 10, 16, 0.86)), url(${eyBackground})`,
      }}
    >
      <section className="ff-marketing__hero">
        <div className="ff-marketing__copy">
          <p className="ff-eyebrow">Multi-agent finance workflow platform</p>
          <h1>Turn raw finance files into polished outputs.</h1>
          <p className="ff-marketing__lead">
            FinFlow lets finance teams upload ERP exports, spreadsheets, PDFs,
            and screenshots with a plain-English instruction, then routes the
            work through specialist agents for cleanup, analysis, charting, and
            export.
          </p>
          <div className="ff-marketing__actions">
            <Link to="/login" className="ff-primary-button">
              Enter workspace
            </Link>
            <a href="#platform" className="ff-secondary-button">
              See the workflow
            </a>
          </div>
          <div className="ff-marketing__stats">
            <div>
              <strong>14 min</strong>
              <span>average workflow completion</span>
            </div>
            <div>
              <strong>11</strong>
              <span>registered specialist agents</span>
            </div>
            <div>
              <strong>PDF, XLSX, PNG, CSV</strong>
              <span>production-ready outputs</span>
            </div>
          </div>
        </div>

        <div className="ff-hero-card">
          <div className="ff-hero-card__header">
            <span>Live example</span>
            <strong>Budget variance to board pack</strong>
          </div>
          <div className="ff-hero-card__flow">
            {[
              "Upload ERP export",
              "Clean and classify",
              "Generate charts",
              "Publish PDF",
            ].map((step) => (
              <div key={step} className="ff-hero-card__step">
                {step}
              </div>
            ))}
          </div>
          <div className="ff-hero-card__footer">
            <span>Instruction</span>
            <p>
              Clean this file, extract revenue variance by region, and return a
              PDF chart pack for leadership review.
            </p>
          </div>
        </div>
      </section>

      <section className="ff-marketing__panel" id="platform">
        <div>
          <p className="ff-eyebrow">Why the layout works</p>
          <h2>
            Built for analysts, managers, and finance operators who need
            visibility as much as speed.
          </h2>
        </div>
        <div className="ff-marketing__grid">
          <article>
            <strong>Job submission</strong>
            <p>
              Drag-and-drop intake with output targeting and realistic finance
              prompts.
            </p>
          </article>
          <article>
            <strong>My jobs</strong>
            <p>
              Track queued, running, complete, and failed workflows with inline
              execution pipelines.
            </p>
          </article>
          <article>
            <strong>Manager dashboard</strong>
            <p>
              See throughput, queue pressure, agent utilisation, and
              team-by-team workload at a glance.
            </p>
          </article>
        </div>
      </section>
    </main>
  );
}

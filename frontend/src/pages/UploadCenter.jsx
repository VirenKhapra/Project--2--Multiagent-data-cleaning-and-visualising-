import React from "react";
import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FiArrowRight, FiCheckCircle, FiFileText, FiStar, FiUploadCloud } from "react-icons/fi";
import { useNavigate } from "react-router-dom";
import { fetchAnalyticsKpis, fetchUploadMetadata, submitJob as submitJobRequest } from "../api/finflow.js";
import PageHero from "../components/PageHero.jsx";

const placeholders = [
  "Clean this ERP export, extract revenue by region, and return a PDF chart pack.",
  "Standardise the dates, remove duplicate AP lines, and output a reconciled XLSX file.",
  "Read this screenshot, extract budget variance figures, and produce a PNG summary visual.",
];

function inferOutputFormat(instruction, options) {
  const normalizedInstruction = String(instruction || "").toUpperCase();
  const normalizedOptions = (options || []).map((option) => String(option).toUpperCase());

  for (const option of normalizedOptions) {
    if (normalizedInstruction.includes(option)) return option;
  }

  if (normalizedInstruction.includes("CHART PACK") || normalizedInstruction.includes("BOARD PACK")) {
    return normalizedOptions.includes("PDF") ? "PDF" : normalizedOptions[0] || "PDF";
  }

  return "";
}

export default function UploadCenter() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const inputRef = useRef(null);
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState(null);
  const [instruction, setInstruction] = useState("");
  const [outputFormat, setOutputFormat] = useState("PDF");
  const [hasManualOutputSelection, setHasManualOutputSelection] = useState(false);
  const [submitError, setSubmitError] = useState("");

  const { data: uploadMetadata } = useQuery({
    queryKey: ["upload-metadata"],
    queryFn: fetchUploadMetadata,
  });
  const { data: analyticsKpis } = useQuery({
    queryKey: ["upload-signals"],
    queryFn: fetchAnalyticsKpis,
  });

  const outputFormatOptions = useMemo(() => {
    const options = uploadMetadata?.output_format_options || [];
    return options.length ? options : ["XLSX", "PDF", "PNG", "CSV", "JSON", "TXT"];
  }, [uploadMetadata]);
  const acceptedFileTypes = useMemo(() => uploadMetadata?.accepted_file_types || [], [uploadMetadata]);
  const displayFileTypes = useMemo(() => {
    const major = ["XLSX", "XLS", "CSV", "PDF", "PNG", "JPG"];
    return acceptedFileTypes.length 
      ? acceptedFileTypes.filter(t => major.includes(t.toUpperCase())) 
      : major;
  }, [acceptedFileTypes]);

  const acceptedLabel = useMemo(
    () => displayFileTypes.join(", "),
    [displayFileTypes],
  );
  const acceptedMime = useMemo(
    () => acceptedFileTypes.map((type) => `.${type.toLowerCase()}`).join(",") || ".xlsx,.xls,.csv,.tsv,.pdf,.png,.jpg,.jpeg,.webp,.json,.txt",
    [acceptedFileTypes],
  );
  const submissionSignals = useMemo(() => {
    const totals = analyticsKpis?.totals || {};
    const outputBreakdown = analyticsKpis?.output_breakdown || [];
    const averageReviewSeconds = Number(totals.average_review_seconds || 0);
    const averageMinutes = averageReviewSeconds > 0 ? Math.max(1, Math.round(averageReviewSeconds / 60)) : null;
    const queuedJobs = Number(totals.queued ?? totals.pending ?? 0);
    const planningJobs = Number(totals.planning ?? 0);
    const runningJobs = Number(totals.running ?? totals.processing ?? 0);
    const quarantinedJobs = Number(totals.quarantined ?? totals.awaiting_agent ?? 0);
    const activeJobs = queuedJobs + planningJobs + runningJobs;

    return [
      { label: "Accepted formats", value: acceptedFileTypes.length ? acceptedLabel : "Loading..." },
      { label: "Average turnaround", value: averageMinutes ? `${averageMinutes} minutes` : "Not enough completed jobs yet" },
      { label: "Most requested output", value: outputBreakdown[0]?.output_format || "No uploads yet" },
        {
          label: "Queue health",
          value: activeJobs || quarantinedJobs
            ? `${activeJobs} active${quarantinedJobs ? ` | ${quarantinedJobs} quarantined` : ""}`
            : "No active or quarantined jobs",
        },
    ];
  }, [acceptedFileTypes.length, acceptedLabel, analyticsKpis]);

  React.useEffect(() => {
    if (!outputFormatOptions.includes(outputFormat)) {
      setOutputFormat(outputFormatOptions[0] || "PDF");
    }
  }, [outputFormat, outputFormatOptions]);

  React.useEffect(() => {
    if (hasManualOutputSelection) return;
    const inferredFormat = inferOutputFormat(instruction, outputFormatOptions);
    if (inferredFormat && inferredFormat !== outputFormat) {
      setOutputFormat(inferredFormat);
    }
  }, [hasManualOutputSelection, instruction, outputFormat, outputFormatOptions]);

  const createJobMutation = useMutation({
    mutationFn: submitJobRequest,
    onSuccess: async (createdJob) => {
      setSubmitError("");
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
      await queryClient.invalidateQueries({ queryKey: ["upload-signals"] });
      await queryClient.invalidateQueries({ queryKey: ["manager-dashboard"] });
      navigate(`/jobs/${createdJob.upload_id}`);
    },
    onError: (error) => {
      setSubmitError(error?.response?.data?.detail || "We could not submit the job.");
    },
  });

  function onDrop(event) {
    event.preventDefault();
    setDragActive(false);
    const nextFile = event.dataTransfer.files?.[0];
    if (nextFile) setFile(nextFile);
  }

  function submitJob() {
    if (!file || !instruction.trim()) return;
    createJobMutation.mutate({
      file,
      instruction: instruction.trim(),
      outputFormat,
    });
  }

  return (
    <div className="ff-page-grid">
      <PageHero
        className="ff-hero-panel--submit"
        eyebrow="Job submission"
        title="Turn a raw finance file into a structured workflow request in one pass."
        description="Upload the source file, describe the finance task in plain language, and choose the format you want back."
        aside={(
          <div className="ff-submit-summary">
            <strong>Built for spreadsheet clean-up, reconciliations, chart packs, OCR intake, and finance-ready exports.</strong>
            <span>Keep the prompt outcome-focused and FinFlow will shape the workflow around it.</span>
          </div>
        )}
      />

      <section className="ff-signal-grid ff-signal-grid--tight">
        {submissionSignals.map((item) => (
          <div key={item.label} className={`ff-signal-card${item.label === "Queue health" ? " ff-signal-card--queue" : ""}`}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </div>
        ))}
      </section>

      <section className="ff-submit-layout">
        <article className="ff-panel ff-panel--tall">
          <div
            className={`ff-dropzone ${dragActive ? "is-active" : ""}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(event) => {
              event.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={onDrop}
            role="presentation"
          >
            <input
              ref={inputRef}
              type="file"
              accept={acceptedMime}
              className="hidden"
              onChange={(event) => setFile(event.target.files?.[0] || null)}
            />
            <div className="ff-dropzone__icon">
              <FiUploadCloud size={28} />
            </div>
            <h3>Drag and drop your source file</h3>
            <p>
              Supports {acceptedLabel}. Built for ERP exports, board-pack source files,
              screenshot evidence, and scanned PDFs.
            </p>
            <button type="button" className="ff-primary-button">Browse files</button>
          </div>

          {file && (
            <div className="ff-file-card" style={{ display: "flex", alignItems: "center", gap: "12px", overflow: "hidden" }}>
              <div className="ff-file-card__icon" style={{ flexShrink: 0 }}>
                <FiFileText size={18} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <strong style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={file.name}>
                  {file.name}
                </strong>
                <span style={{ display: "block" }}>
                  {Math.max(1, Math.round(file.size / 1024))} KB | Output {outputFormat}
                </span>
              </div>
            </div>
          )}

          <label className="ff-field">
            <textarea
              value={instruction}
              onChange={(event) => setInstruction(event.target.value)}
              rows={7}
              placeholder="ENTER A PROMPT OR JOB DESCRIPTION"
            />
          </label>

          <div className="ff-submit-controls" style={{ display: "flex", gap: "24px", alignItems: "flex-end" }}>
            <label className="ff-field ff-field--compact" style={{ flex: 1 }}>
              <span>Output format</span>
              <select
                value={outputFormat}
                onChange={(event) => {
                  setHasManualOutputSelection(true);
                  setOutputFormat(event.target.value);
                }}
              >
                {outputFormatOptions.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </label>

            <button
              type="button"
              className="ff-primary-button"
              onClick={submitJob}
              disabled={createJobMutation.isPending}
              style={{ flexShrink: 0, height: "48px" }}
            >
              {createJobMutation.isPending ? "Submitting..." : "Submit workflow"} <FiArrowRight size={15} />
            </button>
          </div>

          {createJobMutation.isSuccess && (
            <div className="ff-success-banner">
              <FiCheckCircle size={18} />
              <div>
                <strong>Job created successfully.</strong>
                <span>Redirecting you to the live job detail view.</span>
              </div>
            </div>
          )}

          {submitError && (
            <p className="ff-copy-muted" role="alert">{submitError}</p>
          )}
        </article>

        <aside className="ff-submit-side">
          <article className="ff-panel">
            <div className="ff-side-head">
              <FiStar size={16} />
              <strong>Prompt examples</strong>
            </div>
            <div className="ff-template-card ff-template-card--flush">
              <div className="ff-example-chip-list">
                {placeholders.map((example) => (
                  <button
                    key={example}
                    type="button"
                    className={`ff-example-chip${instruction === example ? " is-active" : ""}`}
                    onClick={() => {
                      setHasManualOutputSelection(false);
                      setInstruction(example);
                    }}
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          </article>
        </aside>
      </section>
    </div>
  );
}

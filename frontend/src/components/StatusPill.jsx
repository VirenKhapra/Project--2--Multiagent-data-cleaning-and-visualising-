import React from "react";
import { formatJobStatus } from "../utils/finflowFormatters.js";

export default function StatusPill({ status, label, className = "" }) {
  return (
    <span className={`ff-status ff-status--${status} ${className}`.trim()}>
      {label || formatJobStatus(status)}
    </span>
  );
}

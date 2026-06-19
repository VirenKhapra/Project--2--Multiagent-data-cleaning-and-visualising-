import React from "react";

export default function MiniStat({ icon, value, label, className = "" }) {
  return (
    <div className={`ff-mini-stat ${className}`.trim()}>
      {icon}
      <div>
        <strong>{value}</strong>
        <span>{label}</span>
      </div>
    </div>
  );
}

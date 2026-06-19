import React from "react";
import CountUpValue from "./CountUpValue.jsx";

export default function StatCard({
  label,
  value,
  icon,
  tone = "default",
  meta,
  className = "",
}) {
  return (
    <article
      className={`ff-stat-card ff-stat-card--${tone} ${className}`.trim()}
    >
      {icon ? <div className="ff-stat-card__icon">{icon}</div> : null}
      <div>
        <span>{label}</span>
        <strong>
          <CountUpValue value={value} />
        </strong>
        {meta ? <small>{meta}</small> : null}
      </div>
    </article>
  );
}

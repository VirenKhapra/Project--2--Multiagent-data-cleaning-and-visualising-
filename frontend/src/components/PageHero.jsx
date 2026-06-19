import React from "react";

export default function PageHero({
  eyebrow,
  title,
  description,
  actions,
  aside,
  className = "",
}) {
  return (
    <section className={`ff-hero-panel ff-page-hero ${className}`.trim()}>
      <div className="ff-page-hero__body">
        {eyebrow ? <p className="ff-eyebrow">{eyebrow}</p> : null}
        {title ? <h2>{title}</h2> : null}
        {description ? <p className="ff-copy-muted">{description}</p> : null}
      </div>
      {actions ? (
        <div className="ff-hero-panel__actions ff-page-hero__actions">
          {actions}
        </div>
      ) : null}
      {aside ? <div className="ff-page-hero__aside">{aside}</div> : null}
    </section>
  );
}

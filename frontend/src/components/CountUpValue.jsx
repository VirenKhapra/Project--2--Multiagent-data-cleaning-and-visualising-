import React from "react";

export default function CountUpValue({ value, duration = 800 }) {
  const { prefix, suffix, numeric } = React.useMemo(
    () => parseValue(value),
    [value],
  );
  const [displayValue, setDisplayValue] = React.useState(numeric);

  React.useEffect(() => {
    if (numeric === null) return;

    let frameId = 0;
    let startTime = 0;

    const animate = (timestamp) => {
      if (!startTime) startTime = timestamp;
      const progress = Math.min((timestamp - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayValue(Math.round(numeric * eased));
      if (progress < 1) frameId = window.requestAnimationFrame(animate);
    };

    setDisplayValue(0);
    frameId = window.requestAnimationFrame(animate);
    return () => window.cancelAnimationFrame(frameId);
  }, [duration, numeric]);

  if (numeric === null) {
    return value;
  }

  return `${prefix}${displayValue}${suffix}`;
}

function parseValue(value) {
  const raw = String(value ?? "");
  const match = raw.match(/^([^0-9]*)(\d+)([^0-9]*)$/);
  if (!match) {
    return { prefix: "", suffix: "", numeric: null };
  }
  return {
    prefix: match[1] || "",
    numeric: Number(match[2]),
    suffix: match[3] || "",
  };
}

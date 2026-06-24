import React from "react";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

/**
 * ScatterVisualization — renders a Recharts ScatterChart from a VisualizationSpec.
 *
 * Uses encoding.x and encoding.y as the XAxis/YAxis dataKeys.
 *
 * @param {object} props
 * @param {object} props.spec - VisualizationSpec with chart_type "scatter"
 * @param {object} props.spec.encoding - { x, y, x_label, y_label }
 * @param {Array} props.spec.data - Array of row objects
 * @param {string} props.spec.title - Chart title
 */
export default function ScatterVisualization({ spec }) {
  const { encoding = {}, data = [] } = spec;
  const xKey = encoding.x;
  const yKey = encoding.y;
  const xLabel = encoding.x_label || xKey;
  const yLabel = encoding.y_label || yKey;

  if (!data.length || !xKey || !yKey) {
    return (
      <div className="ff-viz-chart ff-viz-chart--scatter">
        <p className="ff-viz-chart__empty">No data available</p>
      </div>
    );
  }

  return (
    <div className="ff-viz-chart ff-viz-chart--scatter">
      <ResponsiveContainer width="100%" height={360}>
        <ScatterChart margin={{ top: 20, right: 30, bottom: 44, left: 20 }}>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="var(--ff-border, rgba(122, 162, 255, 0.18))"
            className="ff-viz-chart__grid"
          />
          <XAxis
            dataKey={xKey}
            name={xLabel}
            type="number"
            tick={{ fill: "#ffffff", fontSize: 13 }}
            axisLine={{ stroke: "var(--ff-border, rgba(122, 162, 255, 0.18))" }}
            label={{
              value: xLabel,
              position: "insideBottom",
              offset: -12,
              fill: "var(--ff-yellow-ey)",
              fontSize: 15,
              fontWeight: 600,
            }}
          />
          <YAxis
            dataKey={yKey}
            name={yLabel}
            type="number"
            tick={{ fill: "#ffffff", fontSize: 13 }}
            axisLine={{ stroke: "var(--ff-border, rgba(122, 162, 255, 0.18))" }}
            label={{
              value: yLabel,
              angle: -90,
              position: "insideLeft",
              offset: -5,
              fill: "var(--ff-yellow-ey)",
              fontSize: 15,
              fontWeight: 600,
            }}
          />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            formatter={(value, name) => {
              const label = name === xKey ? xLabel : yLabel;
              return [value, label];
            }}
            contentStyle={{
              backgroundColor: "var(--ff-panel-strong, #0f1f36)",
              border: "1px solid var(--ff-border, rgba(122, 162, 255, 0.18))",
              borderRadius: "8px",
              color: "var(--ff-text, #e7eefc)",
            }}
          />
          <Scatter
            data={data}
            fill="var(--ff-yellow-ey, #ffe600)"
            fillOpacity={0.7}
            className="ff-viz-chart__scatter-dots"
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

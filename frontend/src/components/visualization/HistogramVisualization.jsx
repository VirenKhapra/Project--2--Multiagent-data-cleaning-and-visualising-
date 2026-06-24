import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

/**
 * HistogramVisualization — renders a Recharts BarChart in histogram mode
 * from a VisualizationSpec.
 *
 * Uses encoding.x for bin labels (category axis) and encoding.y for
 * frequencies (numeric axis). Bars are rendered edge-to-edge (no gap)
 * to visually represent a histogram distribution.
 *
 * @param {object} props
 * @param {object} props.spec - VisualizationSpec with chart_type "histogram"
 * @param {object} props.spec.encoding - { x, y, x_label, y_label }
 * @param {Array} props.spec.data - Array of row objects (bin data)
 * @param {string} props.spec.title - Chart title
 */
export default function HistogramVisualization({ spec }) {
  const { encoding = {}, data = [] } = spec;
  const xKey = encoding.x;
  const yKey = encoding.y;
  const xLabel = encoding.x_label || xKey;
  const yLabel = encoding.y_label || yKey;

  if (!data.length || !xKey || !yKey) {
    return (
      <div className="ff-viz-chart ff-viz-chart--histogram">
        <p className="ff-viz-chart__empty">No data available</p>
      </div>
    );
  }

  return (
    <div className="ff-viz-chart ff-viz-chart--histogram">
      <ResponsiveContainer width="100%" height={360}>
        <BarChart
          data={data}
          margin={{ top: 20, right: 30, bottom: 44, left: 20 }}
          barCategoryGap={0}
          barGap={0}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="var(--ff-border, rgba(122, 162, 255, 0.18))"
            className="ff-viz-chart__grid"
          />
          <XAxis
            dataKey={xKey}
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
            formatter={(value) => [value, yLabel]}
            labelFormatter={(label) => `${xLabel}: ${label}`}
            contentStyle={{
              backgroundColor: "var(--ff-panel-strong, #0f1f36)",
              border: "1px solid var(--ff-border, rgba(122, 162, 255, 0.18))",
              borderRadius: "8px",
              color: "var(--ff-text, #e7eefc)",
            }}
          />
          <Bar
            dataKey={yKey}
            fill="var(--ff-yellow-ey, #ffe600)"
            fillOpacity={0.85}
            stroke="#ffea79"
            strokeWidth={1}
            className="ff-viz-chart__bar"
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

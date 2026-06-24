import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

/**
 * BarVisualization — renders a Recharts BarChart bound to a VisualizationSpec.
 *
 * Uses encoding.x as XAxis dataKey and encoding.y as Bar dataKey.
 * Labels fall back to the field ID when x_label / y_label are not provided.
 *
 * @param {object} props
 * @param {object} props.spec - VisualizationSpec with chart_type "bar"
 */
export default function BarVisualization({ spec }) {
  const { encoding = {}, data = [], options = {} } = spec;

  const xField = encoding.x;
  const yField = encoding.y;
  const xLabel = encoding.x_label || xField;
  const yLabel = encoding.y_label || yField;

  // Theme colors aligned with FinFlow dark/glassmorphism
  const axisColor = "#ffffff";
  const gridColor = "var(--ff-border, rgba(122, 162, 255, 0.18))";
  const barColor = "var(--ff-yellow-ey, #ffe600)";
  const tooltipBg = "var(--ff-panel-strong, #0f1f36)";
  const tooltipBorder = "var(--ff-border, rgba(122, 162, 255, 0.18))";
  const textColor = "var(--ff-text, #e7eefc)";

  return (
    <div className="ff-viz-chart ff-viz-chart--bar" role="img" aria-label={spec.title || "Bar chart"}>
      <ResponsiveContainer width="100%" height={options.height || 320}>
        <BarChart
          data={data}
          margin={{ top: 16, right: 24, bottom: 54, left: 24 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
          <XAxis
            dataKey={xField}
            tick={{ fill: axisColor, fontSize: 13 }}
            axisLine={{ stroke: gridColor }}
            tickLine={{ stroke: gridColor }}
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
            tick={{ fill: axisColor, fontSize: 13 }}
            axisLine={{ stroke: gridColor }}
            tickLine={{ stroke: gridColor }}
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
            contentStyle={{
              backgroundColor: tooltipBg,
              border: `1px solid ${tooltipBorder}`,
              borderRadius: 8,
              color: textColor,
            }}
            labelStyle={{ color: textColor, fontWeight: 600 }}
            itemStyle={{ color: textColor }}
            labelFormatter={(value) => `${xLabel}: ${value}`}
          />
          <Legend
            verticalAlign="bottom"
            height={36}
            iconSize={12}
            wrapperStyle={{ color: textColor, fontSize: 13, paddingTop: 16 }}
          />
          <Bar
            dataKey={yField}
            name={yLabel}
            fill={barColor}
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

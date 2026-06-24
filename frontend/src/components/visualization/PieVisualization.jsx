import React from "react";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

/**
 * Default color palette for pie slices — FinFlow dark theme compatible.
 */
const COLORS = [
  "#ffe600", // EY Yellow
  "#00b4d8", // Teal Blue
  "#f26419", // Amber Orange
  "#06d6a0", // Mint
  "#8338ec", // Indigo Purple
  "#e76f51", // Coral Rose
  "#2a9d8f", // Slate Green
  "#457b9d", // Steel Blue
  "#ffd166", // Warm Gold
  "#ff006e", // Rose
];

/**
 * PieVisualization — renders a Recharts PieChart from a VisualizationSpec.
 *
 * Uses encoding.category as the name key and encoding.value as the
 * numeric value key for each pie slice.
 *
 * @param {object} props
 * @param {object} props.spec - VisualizationSpec with chart_type "pie"
 * @param {object} props.spec.encoding - { category, value, category_label, value_label }
 * @param {Array} props.spec.data - Array of row objects
 * @param {string} props.spec.title - Chart title
 */
export default function PieVisualization({ spec }) {
  const { encoding = {}, data = [] } = spec;
  const categoryKey = encoding.category;
  const valueKey = encoding.value;
  const categoryLabel = encoding.category_label || categoryKey;
  const valueLabel = encoding.value_label || valueKey;

  if (!data.length || !categoryKey || !valueKey) {
    return (
      <div className="ff-viz-chart ff-viz-chart--pie">
        <p className="ff-viz-chart__empty">No data available</p>
      </div>
    );
  }

  return (
    <div className="ff-viz-chart ff-viz-chart--pie">
      <ResponsiveContainer width="100%" height={360}>
        <PieChart>
          <Pie
            data={data}
            dataKey={valueKey}
            nameKey={categoryKey}
            cx="50%"
            cy="50%"
            outerRadius={110}
            label={({ cx, cy, midAngle, innerRadius, outerRadius, percent, name }) => {
              const RADIAN = Math.PI / 180;
              const radius = outerRadius + 24;
              const x = cx + radius * Math.cos(-midAngle * RADIAN);
              const y = cy + radius * Math.sin(-midAngle * RADIAN);
              return (
                <text
                  x={x}
                  y={y}
                  fill="#ffffff"
                  textAnchor={x > cx ? "start" : "end"}
                  dominantBaseline="central"
                  fontSize={13}
                  fontWeight={500}
                >
                  {`${name} (${(percent * 100).toFixed(1)}%)`}
                </text>
              );
            }}
            labelLine={{ stroke: "rgba(255, 255, 255, 0.4)" }}
          >
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={COLORS[index % COLORS.length]}
                className="ff-viz-chart__cell"
              />
            ))}
          </Pie>
          <Tooltip
            formatter={(value) => [value, valueLabel]}
            labelFormatter={(label) => `${categoryLabel}: ${label}`}
            contentStyle={{
              backgroundColor: "var(--ff-panel-strong, #0f1f36)",
              border: "1px solid var(--ff-border, rgba(122, 162, 255, 0.18))",
              borderRadius: "8px",
              color: "var(--ff-text, #e7eefc)",
            }}
          />
          <Legend
            wrapperStyle={{ color: "var(--ff-text, #e7eefc)", fontSize: 13 }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

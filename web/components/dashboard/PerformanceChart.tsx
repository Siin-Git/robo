"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fmtDate } from "@/lib/format";

export interface Series {
  key: string;
  label: string;
  color: string;
  width: number;
  dataKey: string;
}

export const MY_LINE = { color: "#74a8ff", width: 2.25 };
export const CORE_LINE = { color: "#c7d3e6", width: 1.5 };
export const NEUTRAL_LINE = { color: "#6b7280", width: 1.5 };
export const EQUAL_LINE = { color: "#9ca3af", width: 1.5 };

export function PerformanceChart({
  data,
  series,
  height = 360,
  yFormat = (v: number) => v.toFixed(1),
  animate = true,
  curve = "monotone",
  connectNulls = true,
  showPoints = false,
  framed = true,
  showLegend = true,
  yAxisWidth = 56,
}: {
  data: Record<string, number | string | null>[];
  series: Series[];
  height?: number;
  yFormat?: (v: number) => string;
  animate?: boolean;
  curve?: "monotone" | "linear";
  connectNulls?: boolean;
  showPoints?: boolean;
  framed?: boolean;
  showLegend?: boolean;
  yAxisWidth?: number;
}) {
  return (
    <div className={framed ? "border border-border bg-surface p-[20px]" : ""}>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 12, fill: "var(--text-secondary)" }}
              tickFormatter={(d: string) => fmtDate(String(d))}
              minTickGap={48}
            />
            <YAxis
              tick={{ fontSize: 12, fill: "var(--text-secondary)" }}
              tickFormatter={yFormat}
              width={yAxisWidth}
              domain={["auto", "auto"]}
            />
            <Tooltip
              formatter={(value, name) => [yFormat(Number(value)), name]}
              labelFormatter={(d) => fmtDate(String(d))}
            />
            {showLegend && <Legend verticalAlign="top" height={28} />}
            {series.map((s) => (
              <Line
                key={s.key}
                type={curve}
                dataKey={s.dataKey}
                name={s.label}
                stroke={s.color}
                strokeWidth={s.width}
                dot={showPoints ? {r:3, fill:s.color, stroke:"var(--surface)", strokeWidth:1.5} : false}
                activeDot={{ r: 4, fill:s.color }}
                connectNulls={connectNulls}
                isAnimationActive={animate}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

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

export const MY_LINE = { color: "#2563eb", width: 2.25 };
export const CORE_LINE = { color: "#374151", width: 1.5 };
export const NEUTRAL_LINE = { color: "#6b7280", width: 1.5 };
export const EQUAL_LINE = { color: "#9ca3af", width: 1.5 };

export function PerformanceChart({
  data,
  series,
  height = 360,
  yFormat = (v: number) => v.toFixed(1),
  animate = true,
  curve = "monotone",
}: {
  data: Record<string, number | string | null>[];
  series: Series[];
  height?: number;
  yFormat?: (v: number) => string;
  animate?: boolean;
  curve?: "monotone" | "linear";
}) {
  return (
    <div className="border border-border bg-white p-[20px]">
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#E5E7EB" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 12, fill: "#6B7280" }}
              tickFormatter={(d: string) => fmtDate(String(d))}
              minTickGap={48}
            />
            <YAxis
              tick={{ fontSize: 12, fill: "#6B7280" }}
              tickFormatter={yFormat}
              width={56}
              domain={["auto", "auto"]}
            />
            <Tooltip
              formatter={(value, name) => [yFormat(Number(value)), name]}
              labelFormatter={(d) => fmtDate(String(d))}
            />
            <Legend verticalAlign="top" height={28} />
            {series.map((s) => (
              <Line
                key={s.key}
                type={curve}
                dataKey={s.dataKey}
                name={s.label}
                stroke={s.color}
                strokeWidth={s.width}
                dot={false}
                activeDot={{ r: 3 }}
                connectNulls
                isAnimationActive={animate}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

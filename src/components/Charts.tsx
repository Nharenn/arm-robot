import { useMemo } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from "recharts";
import { HistoryEntry } from "../types";

export function ChartPID({ data }: { data: HistoryEntry[] }) {
  const d = useMemo(() => data.slice(-80), [data]);
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={d} margin={{ top: 4, right: 6, left: -26, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="t" tick={false} stroke="#e2e8f0" />
        <YAxis stroke="#e2e8f0" tick={{ fill: "#9ca3af", fontSize: 9 }} />
        <Tooltip contentStyle={{ background: "#ffffff", borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px", boxShadow: "0 4px 6px -1px rgba(0,0,0,0.1)" }} />
        <Line type="monotone" dataKey="sp" stroke="#10b981" strokeWidth={2} dot={false} name="Setpoint" isAnimationActive={false} />
        <Line type="monotone" dataKey="out" stroke="#3b82f6" strokeWidth={1.5} dot={false} name="Output" isAnimationActive={false} />
        <Line type="monotone" dataKey="err" stroke="#ef4444" strokeWidth={1} strokeDasharray="4 2" dot={false} name="Error" isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function ChartTerms({ data }: { data: HistoryEntry[] }) {
  const d = useMemo(() => data.slice(-80), [data]);
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={d} margin={{ top: 4, right: 6, left: -26, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="t" tick={false} stroke="#e2e8f0" />
        <YAxis stroke="#e2e8f0" tick={{ fill: "#9ca3af", fontSize: 9 }} />
        <Tooltip contentStyle={{ background: "#ffffff", borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "11px", boxShadow: "0 4px 6px -1px rgba(0,0,0,0.1)" }} />
        <Area type="monotone" dataKey="p" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.2} name="P" isAnimationActive={false} />
        <Area type="monotone" dataKey="i" stroke="#10b981" fill="#10b981" fillOpacity={0.2} name="I" isAnimationActive={false} />
        <Area type="monotone" dataKey="d" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.2} name="D" isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

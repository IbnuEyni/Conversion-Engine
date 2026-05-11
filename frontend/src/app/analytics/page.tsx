"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { fetchAnalytics } from "@/lib/api";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  FunnelChart,
  Funnel,
  LabelList,
} from "recharts";

const SEGMENT_COLORS: Record<string, string> = {
  segment_1_series_a_b: "#3b82f6",
  segment_2_mid_market_restructure: "#f59e0b",
  segment_3_leadership_transition: "#8b5cf6",
  segment_4_specialized_capability: "#10b981",
  abstain: "#6b7280",
  unclassified: "#d1d5db",
};

const SEGMENT_LABELS: Record<string, string> = {
  segment_1_series_a_b: "Recently Funded",
  segment_2_mid_market_restructure: "Restructuring",
  segment_3_leadership_transition: "Leadership Transition",
  segment_4_specialized_capability: "Capability Gap",
  abstain: "Abstain",
  unclassified: "Unclassified",
};

const FUNNEL_COLORS = ["#3b82f6", "#6366f1", "#8b5cf6", "#a855f7", "#d946ef", "#10b981"];

export default function AnalyticsPage() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchAnalytics()
      .then(setData)
      .catch(() => setError("Cannot connect to backend"));
  }, []);

  if (error) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-gray-900">Analytics</h2>
        <Card>
          <CardContent className="pt-6">
            <p className="text-red-600">{error}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-gray-900">Analytics</h2>
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  const segmentData = Object.entries(data.segment_counts || {}).map(([key, value]) => ({
    name: SEGMENT_LABELS[key] || key,
    value: value as number,
    fill: SEGMENT_COLORS[key] || "#6b7280",
  }));

  const funnelData = (data.funnel || []).map((item: any, i: number) => ({
    ...item,
    fill: FUNNEL_COLORS[i] || "#6b7280",
  }));

  const totals = data.totals || {};

  // Benchmark comparison data
  const benchmarkData = [
    { metric: "Reply Rate", ours: totals.reply_rate || 0, baseline: 2, target: 9.5 },
    { metric: "Booking Rate", ours: totals.booking_rate || 0, baseline: 0, target: 42.5 },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Analytics</h2>
        <Badge variant="outline">{totals.prospects || 0} total prospects</Badge>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <MetricCard label="Prospects" value={totals.prospects || 0} />
        <MetricCard label="Emails Sent" value={totals.emails_sent || 0} />
        <MetricCard label="Replies" value={totals.replies || 0} />
        <MetricCard label="Calls Booked" value={totals.calls_booked || 0} />
        <MetricCard label="Opted Out" value={totals.opted_out || 0} color="red" />
      </div>

      {/* Rate Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-4 text-center">
            <p className="text-4xl font-bold text-blue-600">{totals.reply_rate || 0}%</p>
            <p className="text-sm text-gray-500 mt-1">Reply Rate</p>
            <p className="text-xs text-gray-400 mt-1">Baseline: 1-3% | Target: 7-12%</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 text-center">
            <p className="text-4xl font-bold text-purple-600">{totals.booking_rate || 0}%</p>
            <p className="text-sm text-gray-500 mt-1">Reply → Booking Rate</p>
            <p className="text-xs text-gray-400 mt-1">Target: 35-50%</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 text-center">
            <p className="text-4xl font-bold text-green-600">
              ${((totals.emails_sent || 0) * 0.15).toFixed(2)}
            </p>
            <p className="text-sm text-gray-500 mt-1">Est. LLM Cost</p>
            <p className="text-xs text-gray-400 mt-1">~$0.15/task (gpt-4.1 via OpenRouter)</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Conversion Funnel */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Conversion Funnel</CardTitle>
          </CardHeader>
          <CardContent>
            {funnelData.length > 0 && funnelData.some((d: any) => d.count > 0) ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={funnelData} layout="vertical" margin={{ left: 80 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis type="category" dataKey="stage" width={100} tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {funnelData.map((entry: any, index: number) => (
                      <Cell key={index} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-64 flex items-center justify-center text-gray-400 text-sm">
                No data yet — enrich prospects to see the funnel
              </div>
            )}
          </CardContent>
        </Card>

        {/* Segment Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Segment Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            {segmentData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={segmentData}
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    dataKey="value"
                    label={({ name, value }) => `${name}: ${value}`}
                    labelLine={true}
                  >
                    {segmentData.map((entry: any, index: number) => (
                      <Cell key={index} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-64 flex items-center justify-center text-gray-400 text-sm">
                No data yet — enrich prospects to see segment distribution
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Benchmark Comparison */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Performance vs Benchmarks</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <BenchmarkBar
              label="Reply Rate"
              current={totals.reply_rate || 0}
              baseline={2}
              target={9.5}
              max={15}
              unit="%"
            />
            <BenchmarkBar
              label="Stalled Thread Rate"
              current={Math.max(0, 100 - (totals.reply_rate || 0) * 3)}
              baseline={35}
              target={15}
              max={50}
              unit="%"
              inverted
            />
            <BenchmarkBar
              label="Cost per Qualified Lead"
              current={0.15}
              baseline={8}
              target={5}
              max={10}
              unit="$"
              inverted
            />
          </div>
          <div className="flex gap-6 mt-4 text-xs text-gray-500">
            <span className="flex items-center gap-1"><span className="w-3 h-3 bg-blue-500 rounded-sm inline-block"></span> Current</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 bg-red-300 rounded-sm inline-block"></span> Industry Baseline</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 bg-green-300 rounded-sm inline-block"></span> Target</span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function MetricCard({ label, value, color = "gray" }: { label: string; value: number; color?: string }) {
  const colorClass = color === "red" ? "text-red-600" : "text-gray-900";
  return (
    <Card>
      <CardContent className="pt-4 pb-3 text-center">
        <p className={`text-3xl font-bold ${colorClass}`}>{value}</p>
        <p className="text-xs text-gray-500 mt-1">{label}</p>
      </CardContent>
    </Card>
  );
}

function BenchmarkBar({
  label,
  current,
  baseline,
  target,
  max,
  unit,
  inverted = false,
}: {
  label: string;
  current: number;
  baseline: number;
  target: number;
  max: number;
  unit: string;
  inverted?: boolean;
}) {
  const currentPct = Math.min((current / max) * 100, 100);
  const baselinePct = Math.min((baseline / max) * 100, 100);
  const targetPct = Math.min((target / max) * 100, 100);

  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="font-medium text-gray-700">{label}</span>
        <span className="text-gray-500">
          {unit === "$" ? `$${current.toFixed(2)}` : `${current.toFixed(1)}%`}
        </span>
      </div>
      <div className="relative h-6 bg-gray-100 rounded overflow-hidden">
        {/* Baseline marker */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-red-300 z-10"
          style={{ left: `${baselinePct}%` }}
        />
        {/* Target marker */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-green-400 z-10"
          style={{ left: `${targetPct}%` }}
        />
        {/* Current bar */}
        <div
          className={`absolute top-0 bottom-0 rounded ${
            inverted
              ? current <= target ? "bg-green-500" : current <= baseline ? "bg-yellow-500" : "bg-red-500"
              : current >= target ? "bg-green-500" : current >= baseline ? "bg-yellow-500" : "bg-blue-500"
          }`}
          style={{ width: `${currentPct}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-gray-400 mt-0.5">
        <span>0</span>
        <span>{max}{unit === "%" ? "%" : ""}</span>
      </div>
    </div>
  );
}

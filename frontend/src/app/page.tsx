"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { fetchHealth, fetchProspects, HealthData, ProspectSummary } from "@/lib/api";

const STATE_COLORS: Record<string, string> = {
  new: "bg-gray-100 text-gray-700",
  enriched: "bg-blue-100 text-blue-700",
  outreach_sent: "bg-yellow-100 text-yellow-700",
  engaged: "bg-green-100 text-green-700",
  qualified: "bg-purple-100 text-purple-700",
  call_booked: "bg-emerald-100 text-emerald-700",
  stalled: "bg-red-100 text-red-700",
  opted_out: "bg-gray-200 text-gray-500",
};

const SEGMENT_LABELS: Record<string, string> = {
  segment_1_series_a_b: "Recently Funded",
  segment_2_mid_market_restructure: "Restructuring",
  segment_3_leadership_transition: "Leadership Transition",
  segment_4_specialized_capability: "Capability Gap",
  abstain: "Abstain",
  unclassified: "Unclassified",
  none: "—",
};

export default function Dashboard() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [prospects, setProspects] = useState<ProspectSummary[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setError("Cannot connect to backend. Start the server: python3 -m agent.main"));
    fetchProspects()
      .then(setProspects)
      .catch(() => {});
  }, []);

  const stateCounts = prospects.reduce((acc, p) => {
    acc[p.state] = (acc[p.state] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const segmentCounts = prospects.reduce((acc, p) => {
    acc[p.segment] = (acc[p.segment] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  if (error) {
    return (
      <div className="flex items-center justify-center h-96">
        <Card className="max-w-md">
          <CardContent className="pt-6">
            <p className="text-red-600 font-medium mb-2">⚠️ Backend Unavailable</p>
            <p className="text-sm text-gray-600">{error}</p>
            <code className="block mt-4 p-3 bg-gray-100 rounded text-xs">
              python3 -m agent.main
            </code>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
        {health && (
          <div className="flex items-center gap-3">
            <Badge variant={health.live_mode ? "destructive" : "secondary"}>
              {health.live_mode ? "🔴 LIVE" : "🟢 SAFE MODE"}
            </Badge>
            <Badge variant="outline">HubSpot: {health.hubspot}</Badge>
          </div>
        )}
      </div>

      {/* Pipeline Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {["new", "enriched", "outreach_sent", "engaged", "qualified", "call_booked"].map((state) => (
          <Card key={state}>
            <CardContent className="pt-4 pb-3 text-center">
              <p className="text-3xl font-bold text-gray-900">{stateCounts[state] || 0}</p>
              <p className="text-xs text-gray-500 mt-1 capitalize">{state.replace(/_/g, " ")}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Segment Breakdown + System Health */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Segment Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            {Object.entries(segmentCounts).length === 0 ? (
              <p className="text-sm text-gray-500">No prospects yet. Enrich a company to get started.</p>
            ) : (
              <div className="space-y-3">
                {Object.entries(segmentCounts).map(([seg, count]) => (
                  <div key={seg} className="flex items-center justify-between">
                    <span className="text-sm text-gray-700">{SEGMENT_LABELS[seg] || seg}</span>
                    <Badge variant="outline">{count}</Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">System Health</CardTitle>
          </CardHeader>
          <CardContent>
            {health ? (
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Status</span>
                  <span className="font-medium text-green-600">{health.status}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Kill Switch</span>
                  <span className="font-medium">{health.kill_switch}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">HubSpot</span>
                  <span className="font-medium">{health.hubspot}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Live Mode</span>
                  <span className="font-medium">{health.live_mode ? "ON" : "OFF"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Last Check</span>
                  <span className="font-mono text-xs">{health.timestamp?.slice(0, 19)}</span>
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-500">Loading...</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Prospects */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Recent Prospects</CardTitle>
        </CardHeader>
        <CardContent>
          {prospects.length === 0 ? (
            <p className="text-sm text-gray-500">
              No prospects yet. Go to <a href="/enrich" className="text-blue-600 underline">Enrich</a> to add one.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="pb-2 font-medium">Company</th>
                    <th className="pb-2 font-medium">Segment</th>
                    <th className="pb-2 font-medium">State</th>
                    <th className="pb-2 font-medium">Emails</th>
                  </tr>
                </thead>
                <tbody>
                  {prospects.slice(0, 10).map((p) => (
                    <tr key={p.id} className="border-b last:border-0">
                      <td className="py-2">
                        <a href={`/prospects/${p.id}`} className="text-blue-600 hover:underline font-medium">
                          {p.company}
                        </a>
                      </td>
                      <td className="py-2 text-gray-600">{SEGMENT_LABELS[p.segment] || p.segment}</td>
                      <td className="py-2">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATE_COLORS[p.state] || ""}`}>
                          {p.state.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td className="py-2 text-gray-600">{p.emails_sent}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

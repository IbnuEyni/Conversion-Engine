"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { fetchProspects, ProspectSummary } from "@/lib/api";

const SEGMENT_LABELS: Record<string, string> = {
  segment_1_series_a_b: "Recently Funded",
  segment_2_mid_market_restructure: "Restructuring",
  segment_3_leadership_transition: "Leadership Transition",
  segment_4_specialized_capability: "Capability Gap",
  abstain: "Abstain",
  unclassified: "Unclassified",
  none: "—",
};

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

export default function ProspectsPage() {
  const [prospects, setProspects] = useState<ProspectSummary[]>([]);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    fetchProspects().then(setProspects).catch(() => {});
  }, []);

  const filtered = prospects.filter(
    (p) =>
      p.company.toLowerCase().includes(filter.toLowerCase()) ||
      p.segment.includes(filter.toLowerCase()) ||
      p.state.includes(filter.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Prospects</h2>
        <a href="/enrich">
          <button className="px-4 py-2 bg-slate-900 text-white text-sm rounded-md hover:bg-slate-700">
            + Enrich New
          </button>
        </a>
      </div>

      <input
        type="text"
        placeholder="Filter by company, segment, or state..."
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="w-full max-w-md px-3 py-2 border rounded-md text-sm"
      />

      <Card>
        <CardContent className="pt-4">
          {filtered.length === 0 ? (
            <p className="text-sm text-gray-500 py-8 text-center">
              No prospects found. <a href="/enrich" className="text-blue-600 underline">Enrich a company</a> to get started.
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-gray-500">
                  <th className="pb-2 font-medium">Company</th>
                  <th className="pb-2 font-medium">Segment</th>
                  <th className="pb-2 font-medium">State</th>
                  <th className="pb-2 font-medium">Emails Sent</th>
                  <th className="pb-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((p) => (
                  <tr key={p.id} className="border-b last:border-0 hover:bg-gray-50">
                    <td className="py-3">
                      <a href={`/prospects/${p.id}`} className="text-blue-600 hover:underline font-medium">
                        {p.company}
                      </a>
                      <p className="text-xs text-gray-400">{p.id}</p>
                    </td>
                    <td className="py-3 text-gray-600">{SEGMENT_LABELS[p.segment] || p.segment}</td>
                    <td className="py-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATE_COLORS[p.state] || ""}`}>
                        {p.state.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="py-3 text-gray-600">{p.emails_sent}</td>
                    <td className="py-3">
                      <a href={`/prospects/${p.id}`} className="text-xs text-blue-600 hover:underline">
                        View →
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

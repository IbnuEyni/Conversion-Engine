"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { fetchHealth, HealthData } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const BENCH_DATA = {
  total_engineers_on_bench: 36,
  stacks: {
    python: { available: 7, seniority: "3 junior, 3 mid, 1 senior", deploy_days: 7 },
    go: { available: 3, seniority: "1 junior, 1 mid, 1 senior", deploy_days: 14 },
    data: { available: 9, seniority: "4 junior, 4 mid, 1 senior", deploy_days: 7 },
    ml: { available: 5, seniority: "2 junior, 2 mid, 1 senior", deploy_days: 10 },
    infra: { available: 4, seniority: "1 junior, 2 mid, 1 senior", deploy_days: 14 },
    frontend: { available: 6, seniority: "3 junior, 2 mid, 1 senior", deploy_days: 7 },
    fullstack_nestjs: { available: 2, seniority: "0 junior, 2 mid, 0 senior", deploy_days: 14 },
  },
};

export default function SettingsPage() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setError("Cannot connect to backend"));
  }, []);

  return (
    <div className="space-y-6 max-w-4xl">
      <h2 className="text-2xl font-bold text-gray-900">Settings</h2>

      {/* Kill Switch */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-3">
            Kill Switch
            {health && (
              <Badge variant={health.live_mode ? "destructive" : "secondary"} className="text-sm">
                {health.live_mode ? "🔴 LIVE — Emails going to real inboxes" : "🟢 SAFE — All outbound to local sink"}
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3 text-sm">
            <p className="text-gray-600">
              When <code className="bg-gray-100 px-1 rounded">LIVE_MODE=false</code> (default), all outbound
              (email, SMS, bookings) routes to <code className="bg-gray-100 px-1 rounded">data/outbound_sink/</code> as JSON files.
              Nothing reaches real people.
            </p>
            <div className="p-3 bg-yellow-50 border border-yellow-200 rounded">
              <p className="text-yellow-800 text-sm font-medium">⚠️ To enable live mode:</p>
              <p className="text-yellow-700 text-xs mt-1">
                Set <code>LIVE_MODE=true</code> and <code>OUTBOUND_SINK=resend</code> in .env.
                Only after Tenacious executive approval.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4 mt-4">
              <div>
                <p className="text-xs text-gray-500 uppercase">Status</p>
                <p className="font-medium">{health?.status || "—"}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 uppercase">Kill Switch</p>
                <p className="font-medium">{health?.kill_switch || "—"}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 uppercase">HubSpot</p>
                <p className="font-medium">{health?.hubspot || "—"}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 uppercase">Last Check</p>
                <p className="font-mono text-xs">{health?.timestamp?.slice(0, 19) || "—"}</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* API Keys Status */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Integration Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <IntegrationRow
              name="OpenRouter (LLM)"
              description="Qwen 235B / GPT-4.1 for enrichment, composition, conversation"
              status={error ? "error" : "connected"}
              detail="Model: qwen/qwen3-235b-a22b"
            />
            <IntegrationRow
              name="Resend (Email)"
              description="Primary outreach channel — cold emails to prospects"
              status={health ? "connected" : "unknown"}
              detail="From: outreach@tenacious.dev"
            />
            <IntegrationRow
              name="Africa's Talking (SMS)"
              description="Secondary channel — warm lead scheduling only"
              status={health ? "connected" : "unknown"}
              detail="Sandbox mode, shortcode 4571"
            />
            <IntegrationRow
              name="HubSpot CRM"
              description="Contacts, companies, deals, notes — all synced"
              status={health?.hubspot === "connected" ? "connected" : "sink"}
              detail={`Portal: 148322728 | Mode: ${health?.hubspot || "unknown"}`}
            />
            <IntegrationRow
              name="Cal.com (Booking)"
              description="Discovery call scheduling — mock slots in safe mode"
              status={health ? "connected" : "unknown"}
              detail="Event type: Discovery Call (30 min)"
            />
            <IntegrationRow
              name="Langfuse (Observability)"
              description="Per-trace cost attribution, LLM call tracing"
              status={health ? "connected" : "unknown"}
              detail="Cloud free tier + local JSONL fallback"
            />
          </div>
        </CardContent>
      </Card>

      {/* Bench Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">
            Bench Summary
            <span className="text-sm font-normal text-gray-500 ml-2">
              ({BENCH_DATA.total_engineers_on_bench} engineers available)
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-gray-500 mb-4">
            The agent must never commit capacity not shown here. Updated weekly.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {Object.entries(BENCH_DATA.stacks).map(([stack, info]) => (
              <div key={stack} className="p-3 border rounded-lg">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-sm capitalize">{stack.replace(/_/g, " ")}</span>
                  <Badge variant="outline">{info.available} available</Badge>
                </div>
                <p className="text-xs text-gray-500">{info.seniority}</p>
                <p className="text-xs text-gray-400">Deploy in {info.deploy_days} days</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Style Guide Preview */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Tenacious Style Guide</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4 text-sm">
            <div>
              <p className="font-medium text-gray-700 mb-1">Tone Markers</p>
              <div className="flex flex-wrap gap-2">
                {["Direct", "Grounded", "Honest", "Professional", "Non-condescending"].map((t) => (
                  <Badge key={t} variant="secondary">{t}</Badge>
                ))}
              </div>
            </div>
            <Separator />
            <div>
              <p className="font-medium text-gray-700 mb-1">Banned Phrases</p>
              <div className="flex flex-wrap gap-2">
                {["leverage our expertise", "best-in-class", "synergy", "touch base", "circle back", "just following up"].map((p) => (
                  <Badge key={p} variant="destructive" className="text-xs">{p}</Badge>
                ))}
              </div>
            </div>
            <Separator />
            <div>
              <p className="font-medium text-gray-700 mb-1">Word Limits</p>
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="p-2 bg-gray-50 rounded">
                  <p className="font-medium">Engaged reply</p>
                  <p className="text-gray-500">Max 150 words</p>
                </div>
                <div className="p-2 bg-gray-50 rounded">
                  <p className="font-medium">Curious reply</p>
                  <p className="text-gray-500">Max 90 words</p>
                </div>
                <div className="p-2 bg-gray-50 rounded">
                  <p className="font-medium">Soft defer</p>
                  <p className="text-gray-500">Max 60 words</p>
                </div>
              </div>
            </div>
            <Separator />
            <div>
              <p className="font-medium text-gray-700 mb-1">Key Rules</p>
              <ul className="space-y-1 text-xs text-gray-600 list-disc list-inside">
                <li>Never claim capacity not shown in bench summary</li>
                <li>If signal confidence is low, ask rather than assert</li>
                <li>One clear ask per message</li>
                <li>No emojis in cold outreach</li>
                <li>Subject lines under 60 characters</li>
                <li>All outputs marked draft: true</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function IntegrationRow({
  name,
  description,
  status,
  detail,
}: {
  name: string;
  description: string;
  status: "connected" | "sink" | "error" | "unknown";
  detail: string;
}) {
  const statusConfig = {
    connected: { color: "bg-green-100 text-green-700", label: "Connected" },
    sink: { color: "bg-yellow-100 text-yellow-700", label: "Sink Mode" },
    error: { color: "bg-red-100 text-red-700", label: "Error" },
    unknown: { color: "bg-gray-100 text-gray-500", label: "Unknown" },
  };
  const cfg = statusConfig[status];

  return (
    <div className="flex items-center justify-between p-3 border rounded-lg">
      <div>
        <p className="font-medium text-sm">{name}</p>
        <p className="text-xs text-gray-500">{description}</p>
        <p className="text-xs text-gray-400 mt-0.5">{detail}</p>
      </div>
      <span className={`px-2 py-1 rounded text-xs font-medium ${cfg.color}`}>
        {cfg.label}
      </span>
    </div>
  );
}

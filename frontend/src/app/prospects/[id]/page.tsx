"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { fetchProspect, sendOutreach, sendReply } from "@/lib/api";

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

export default function ProspectDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [prospect, setProspect] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [replyText, setReplyText] = useState("");
  const [replyResult, setReplyResult] = useState<any>(null);
  const [actionLoading, setActionLoading] = useState("");

  useEffect(() => {
    if (id) {
      fetchProspect(id)
        .then(setProspect)
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  }, [id]);

  if (loading) return <p className="text-gray-500">Loading...</p>;
  if (!prospect) return <p className="text-red-600">Prospect not found.</p>;

  const brief = prospect.signal_brief;
  const gap = prospect.gap_brief;
  const classification = prospect.classification;

  async function handleOutreach() {
    setActionLoading("outreach");
    try {
      const res = await sendOutreach(id);
      alert(`✅ Email sent!\nSubject: ${res.email_subject}\nStatus: ${res.status}`);
      const updated = await fetchProspect(id);
      setProspect(updated);
    } catch (e) {
      alert("Failed to send outreach");
    }
    setActionLoading("");
  }

  async function handleReply() {
    if (!replyText.trim()) return;
    setActionLoading("reply");
    try {
      const res = await sendReply(id, replyText);
      setReplyResult(res);
      setReplyText("");
      const updated = await fetchProspect(id);
      setProspect(updated);
    } catch (e) {
      alert("Failed to handle reply");
    }
    setActionLoading("");
  }

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{prospect.company_name}</h2>
          <p className="text-gray-500 text-sm mt-1">
            {prospect.contact_name} • {prospect.contact_title} • {prospect.contact_email}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`px-3 py-1 rounded text-sm font-medium ${STATE_COLORS[prospect.state] || ""}`}>
            {prospect.state?.replace(/_/g, " ")}
          </span>
          <Badge variant="outline">{id}</Badge>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        {(prospect.state === "enriched" || prospect.state === "new") && (
          <Button onClick={handleOutreach} disabled={actionLoading === "outreach"}>
            {actionLoading === "outreach" ? "Sending..." : "Send Outreach Email"}
          </Button>
        )}
        <a href="/prospects">
          <Button variant="outline">← Back to List</Button>
        </a>
      </div>

      {/* Firmographics + Classification */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader><CardTitle className="text-lg">Firmographics</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Industry" value={prospect.industry} />
            <Row label="Employees" value={prospect.employee_count} />
            <Row label="Location" value={prospect.location} />
            <Row label="Website" value={prospect.website} />
            <Row label="Domain" value={prospect.domain} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-lg">ICP Classification</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Segment" value={classification?.segment} />
            <Row label="Confidence" value={classification?.confidence ? `${(classification.confidence * 100).toFixed(0)}%` : "—"} />
            <Row label="Reasoning" value={classification?.reasoning} />
            <Row label="Bench Match" value={classification?.bench_match ? "✅ Yes" : "❌ No"} />
            {classification?.bench_match_detail && (
              <Row label="Bench Detail" value={classification.bench_match_detail} />
            )}
          </CardContent>
        </Card>
      </div>

      {/* Hiring Signal Brief */}
      {brief && (
        <Card>
          <CardHeader><CardTitle className="text-lg">Hiring Signal Brief</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            {/* Buying Window Signals */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <SignalCard
                title="Funding"
                detected={brief.buying_window_signals?.funding_event?.detected}
                details={[
                  `Stage: ${brief.buying_window_signals?.funding_event?.stage || "none"}`,
                  `Amount: ${brief.buying_window_signals?.funding_event?.amount_usd ? `$${(brief.buying_window_signals.funding_event.amount_usd / 1e6).toFixed(1)}M` : "—"}`,
                  `Date: ${brief.buying_window_signals?.funding_event?.closed_at || "—"}`,
                ]}
              />
              <SignalCard
                title="Layoff"
                detected={brief.buying_window_signals?.layoff_event?.detected}
                details={[
                  `Headcount: ${brief.buying_window_signals?.layoff_event?.headcount_reduction || "—"}`,
                  `Percentage: ${brief.buying_window_signals?.layoff_event?.percentage_cut ? `${brief.buying_window_signals.layoff_event.percentage_cut}%` : "—"}`,
                  `Date: ${brief.buying_window_signals?.layoff_event?.date || "—"}`,
                ]}
              />
              <SignalCard
                title="Leadership Change"
                detected={brief.buying_window_signals?.leadership_change?.detected}
                details={[
                  `Role: ${brief.buying_window_signals?.leadership_change?.role || "—"}`,
                  `Name: ${brief.buying_window_signals?.leadership_change?.new_leader_name || "—"}`,
                  `Started: ${brief.buying_window_signals?.leadership_change?.started_at || "—"}`,
                ]}
              />
            </div>

            <Separator />

            {/* Hiring Velocity + AI Maturity */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <h4 className="font-medium text-sm text-gray-700 mb-2">Hiring Velocity</h4>
                <div className="space-y-1 text-sm">
                  <Row label="Open Roles Today" value={brief.hiring_velocity?.open_roles_today} />
                  <Row label="60 Days Ago" value={brief.hiring_velocity?.open_roles_60_days_ago} />
                  <Row label="Velocity" value={brief.hiring_velocity?.velocity_label?.replace(/_/g, " ")} />
                  <Row label="Confidence" value={brief.hiring_velocity?.signal_confidence?.toFixed(2)} />
                </div>
              </div>
              <div>
                <h4 className="font-medium text-sm text-gray-700 mb-2">AI Maturity</h4>
                <div className="flex items-center gap-3 mb-2">
                  <div className="text-3xl font-bold text-gray-900">{brief.ai_maturity?.score || 0}</div>
                  <div className="text-sm text-gray-500">/3</div>
                  <Badge variant="outline">confidence: {brief.ai_maturity?.confidence?.toFixed(2)}</Badge>
                </div>
                {brief.ai_maturity?.justifications?.length > 0 && (
                  <div className="space-y-1">
                    {brief.ai_maturity.justifications.slice(0, 4).map((j: any, i: number) => (
                      <p key={i} className="text-xs text-gray-600">
                        <span className="font-medium">[{j.weight?.toUpperCase()}]</span> {j.signal}: {j.status?.slice(0, 80)}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <Separator />

            {/* Tech Stack + Honesty Flags */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <h4 className="font-medium text-sm text-gray-700 mb-2">Tech Stack</h4>
                <div className="flex flex-wrap gap-1">
                  {(brief.tech_stack || []).map((s: string) => (
                    <Badge key={s} variant="secondary" className="text-xs">{s}</Badge>
                  ))}
                  {(!brief.tech_stack || brief.tech_stack.length === 0) && (
                    <span className="text-xs text-gray-400">No stack detected</span>
                  )}
                </div>
              </div>
              <div>
                <h4 className="font-medium text-sm text-gray-700 mb-2">Honesty Flags</h4>
                <div className="flex flex-wrap gap-1">
                  {(brief.honesty_flags || []).map((f: string) => (
                    <Badge key={f} variant="destructive" className="text-xs">{f}</Badge>
                  ))}
                  {(!brief.honesty_flags || brief.honesty_flags.length === 0) && (
                    <span className="text-xs text-gray-400">None — all signals strong</span>
                  )}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Competitor Gap Brief */}
      {gap && gap.gap_findings?.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-lg">Competitor Gap Brief</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-xs text-gray-500 uppercase">Sector</p>
                <p className="font-medium">{gap.prospect_sector}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 uppercase">AI Maturity vs Top Quartile</p>
                <p className="font-medium">{gap.prospect_ai_maturity_score}/3 vs {gap.sector_top_quartile_benchmark}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 uppercase">Pitch Shift</p>
                <p className="font-medium text-blue-700">{gap.suggested_pitch_shift}</p>
              </div>
            </div>

            <Separator />

            {/* Competitors */}
            {gap.competitors_analyzed?.length > 0 && (
              <div>
                <h4 className="font-medium text-sm text-gray-700 mb-2">Competitors Analyzed</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                  {gap.competitors_analyzed.map((c: any, i: number) => (
                    <div key={i} className="p-2 border rounded text-xs">
                      <p className="font-medium">{c.name}</p>
                      <p className="text-gray-500">AI: {c.ai_maturity_score}/3 • {c.headcount_band} • {c.top_quartile ? "⭐ Top Quartile" : ""}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <Separator />

            {/* Gap Findings */}
            <div>
              <h4 className="font-medium text-sm text-gray-700 mb-2">Gap Findings</h4>
              <div className="space-y-3">
                {gap.gap_findings.map((f: any, i: number) => (
                  <div key={i} className="p-3 border rounded bg-gray-50">
                    <div className="flex items-center justify-between mb-1">
                      <p className="font-medium text-sm">{f.practice}</p>
                      <Badge variant={f.confidence === "high" ? "default" : "secondary"} className="text-xs">
                        {f.confidence}
                      </Badge>
                    </div>
                    <p className="text-xs text-gray-600 mb-2">{f.prospect_state}</p>
                    {f.peer_evidence?.map((pe: any, j: number) => (
                      <p key={j} className="text-xs text-gray-500 ml-2">
                        • <span className="font-medium">{pe.competitor_name}:</span> {pe.evidence?.slice(0, 100)}
                      </p>
                    ))}
                  </div>
                ))}
              </div>
            </div>

            {/* Quality Self-Check */}
            {gap.gap_quality_self_check && (
              <>
                <Separator />
                <div className="flex gap-4 text-xs">
                  <span className={gap.gap_quality_self_check.all_peer_evidence_has_source_url ? "text-green-600" : "text-red-600"}>
                    {gap.gap_quality_self_check.all_peer_evidence_has_source_url ? "✅" : "❌"} All evidence sourced
                  </span>
                  <span className={gap.gap_quality_self_check.at_least_one_gap_high_confidence ? "text-green-600" : "text-red-600"}>
                    {gap.gap_quality_self_check.at_least_one_gap_high_confidence ? "✅" : "❌"} High-confidence gap
                  </span>
                  <span className={!gap.gap_quality_self_check.prospect_silent_but_sophisticated_risk ? "text-green-600" : "text-orange-600"}>
                    {!gap.gap_quality_self_check.prospect_silent_but_sophisticated_risk ? "✅" : "⚠️"} Silent-but-sophisticated risk
                  </span>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* Simulate Reply */}
      <Card>
        <CardHeader><CardTitle className="text-lg">Simulate Prospect Reply</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-3">
            <textarea
              value={replyText}
              onChange={(e) => setReplyText(e.target.value)}
              placeholder="Type a simulated prospect reply... e.g. 'This is interesting, tell me more about your ML team availability'"
              className="w-full px-3 py-2 border rounded-md text-sm h-24 resize-none"
            />
            <Button onClick={handleReply} disabled={!replyText.trim() || actionLoading === "reply"}>
              {actionLoading === "reply" ? "Processing..." : "Send Reply"}
            </Button>
          </div>

          {replyResult && (
            <div className="mt-4 p-4 bg-gray-50 rounded border space-y-2">
              <div className="flex gap-2">
                <Badge>{replyResult.reply_class}</Badge>
                <Badge variant="outline">{replyResult.state}</Badge>
                {replyResult.should_book_call && <Badge variant="default">📞 Book Call</Badge>}
                {replyResult.needs_human_handoff && <Badge variant="destructive">👤 Human Handoff</Badge>}
              </div>
              {replyResult.reply && (
                <div className="mt-2">
                  <p className="text-xs text-gray-500 mb-1">Agent Response:</p>
                  <p className="text-sm text-gray-800 whitespace-pre-wrap">{replyResult.reply}</p>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Metadata */}
      <Card>
        <CardHeader><CardTitle className="text-lg">Metadata</CardTitle></CardHeader>
        <CardContent className="text-sm space-y-2">
          <Row label="Prospect ID" value={prospect.id} />
          <Row label="Created" value={prospect.created_at} />
          <Row label="Updated" value={prospect.updated_at} />
          <Row label="Emails Sent" value={prospect.emails_sent} />
          <Row label="Last Contact" value={prospect.last_contact} />
          <Row label="HubSpot ID" value={prospect.hubspot_contact_id} />
          <Row label="Cal.com Booking" value={prospect.calcom_booking_id} />
          <Row label="Channel" value={prospect.channel} />
          <Row label="Synthetic" value={prospect.is_synthetic ? "Yes" : "No"} />
          <Row label="Draft" value={prospect.draft ? "Yes" : "No"} />
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ label, value }: { label: string; value: any }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-500">{label}</span>
      <span className="text-gray-900 text-right max-w-[60%] truncate">{value ?? "—"}</span>
    </div>
  );
}

function SignalCard({ title, detected, details }: { title: string; detected: boolean; details: string[] }) {
  return (
    <div className={`p-3 rounded border ${detected ? "border-green-200 bg-green-50" : "border-gray-200 bg-gray-50"}`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-sm">{detected ? "✅" : "⬜"}</span>
        <span className="font-medium text-sm">{title}</span>
      </div>
      <div className="space-y-0.5">
        {details.map((d, i) => (
          <p key={i} className="text-xs text-gray-600">{d}</p>
        ))}
      </div>
    </div>
  );
}

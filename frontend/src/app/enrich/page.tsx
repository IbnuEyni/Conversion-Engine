"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { enrichProspect } from "@/lib/api";

export default function EnrichPage() {
  const [form, setForm] = useState({
    company_name: "",
    contact_name: "",
    contact_email: "",
    contact_title: "",
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.company_name) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await enrichProspect(form);
      setResult(data);
    } catch (err) {
      setError("Failed to connect to backend. Is the server running?");
    }
    setLoading(false);
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <h2 className="text-2xl font-bold text-gray-900">Enrich Prospect</h2>
      <p className="text-gray-600">Enter a company name to run the full enrichment pipeline (Crunchbase, job posts, layoffs, leadership, AI maturity, gap analysis).</p>

      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Company Name *</label>
                <input
                  type="text"
                  value={form.company_name}
                  onChange={(e) => setForm({ ...form, company_name: e.target.value })}
                  className="w-full px-3 py-2 border rounded-md text-sm"
                  placeholder="e.g. Stripe, GitLab, Yellow.ai"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Contact Name</label>
                <input
                  type="text"
                  value={form.contact_name}
                  onChange={(e) => setForm({ ...form, contact_name: e.target.value })}
                  className="w-full px-3 py-2 border rounded-md text-sm"
                  placeholder="e.g. Jane Smith"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Contact Email</label>
                <input
                  type="email"
                  value={form.contact_email}
                  onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
                  className="w-full px-3 py-2 border rounded-md text-sm"
                  placeholder="e.g. jane@company.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Contact Title</label>
                <input
                  type="text"
                  value={form.contact_title}
                  onChange={(e) => setForm({ ...form, contact_title: e.target.value })}
                  className="w-full px-3 py-2 border rounded-md text-sm"
                  placeholder="e.g. VP Engineering"
                />
              </div>
            </div>
            <Button type="submit" disabled={loading || !form.company_name}>
              {loading ? "Enriching... (10-30s)" : "Run Enrichment Pipeline"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-4">
            <p className="text-red-700 text-sm">{error}</p>
          </CardContent>
        </Card>
      )}

      {loading && (
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-3">
              <p className="text-sm font-medium text-gray-700">Running enrichment pipeline...</p>
              <div className="space-y-2 text-sm text-gray-500">
                <p>⏳ Crunchbase firmographics + funding...</p>
                <p>⏳ Layoffs.fyi check...</p>
                <p>⏳ Job post scraping (Playwright)...</p>
                <p>⏳ Leadership detection...</p>
                <p>⏳ AI maturity scoring (LLM)...</p>
                <p>⏳ Competitor gap analysis (LLM)...</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {result && (
        <Card className="border-green-200">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-3">
              ✅ Enrichment Complete
              <Badge variant="outline">{result.prospect_id}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-3">
                <div>
                  <p className="text-xs text-gray-500 uppercase">Company</p>
                  <p className="font-medium">{result.company}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase">ICP Segment</p>
                  <p className="font-medium">{result.segment}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase">Confidence</p>
                  <p className="font-medium">{(result.confidence * 100).toFixed(0)}%</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase">State</p>
                  <Badge>{result.state}</Badge>
                </div>
              </div>
              <div className="space-y-3">
                <div>
                  <p className="text-xs text-gray-500 uppercase">AI Maturity</p>
                  <p className="font-medium">{result.ai_maturity ?? "N/A"}/3</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase">Hiring Velocity</p>
                  <p className="font-medium">{result.hiring_velocity ?? "N/A"}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase">Bench Match</p>
                  <p className="font-medium">{result.bench_match ? "✅ Yes" : "❌ No"}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase">Honesty Flags</p>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {(result.honesty_flags || []).map((f: string) => (
                      <Badge key={f} variant="secondary" className="text-xs">{f}</Badge>
                    ))}
                    {(!result.honesty_flags || result.honesty_flags.length === 0) && (
                      <span className="text-sm text-gray-500">None</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t flex gap-3">
              <a href={`/prospects/${result.prospect_id}`}>
                <Button variant="outline" size="sm">View Full Brief</Button>
              </a>
              <Button
                size="sm"
                onClick={async () => {
                  const res = await fetch(`http://localhost:8000/prospects/${result.prospect_id}/outreach`, { method: "POST" });
                  const data = await res.json();
                  alert(`Email sent! Subject: ${data.email_subject}`);
                }}
              >
                Send Outreach Email
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

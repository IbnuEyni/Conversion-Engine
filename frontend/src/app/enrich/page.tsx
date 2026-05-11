"use client";

import { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { enrichProspect } from "@/lib/api";

type StepStatus = "pending" | "running" | "done" | "error";

interface PipelineStep {
  id: string;
  label: string;
  description: string;
  status: StepStatus;
  duration?: number;
}

const INITIAL_STEPS: PipelineStep[] = [
  { id: "crunchbase", label: "Crunchbase Firmographics", description: "Company name, industry, employees, location, website", status: "pending" },
  { id: "funding", label: "Funding Signal", description: "Series A/B in last 180 days → buying window", status: "pending" },
  { id: "layoffs", label: "Layoffs.fyi Check", description: "Recent layoff → cost pressure → Segment 2", status: "pending" },
  { id: "job_posts", label: "Job Post Scraping", description: "Career page via Playwright → hiring velocity + tech stack", status: "pending" },
  { id: "leadership", label: "Leadership Detection", description: "New CTO/VP Eng in 90 days → Segment 3", status: "pending" },
  { id: "ai_maturity", label: "AI Maturity Scoring", description: "LLM scores 6 weighted signals → 0-3 score", status: "pending" },
  { id: "gap_analysis", label: "Competitor Gap Analysis", description: "LLM compares prospect vs sector top quartile", status: "pending" },
  { id: "classification", label: "ICP Classification", description: "Rule-based segment assignment + confidence", status: "pending" },
];

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
  const [steps, setSteps] = useState<PipelineStep[]>(INITIAL_STEPS);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  function resetSteps() {
    setSteps(INITIAL_STEPS.map((s) => ({ ...s, status: "pending" })));
  }

  function simulateProgress() {
    // Simulate step progression based on typical timing
    const timings = [500, 800, 1000, 1500, 3000, 8000, 10000, 500];
    let elapsed = 0;

    timings.forEach((delay, idx) => {
      elapsed += delay;
      setTimeout(() => {
        setSteps((prev) =>
          prev.map((s, i) => {
            if (i < idx) return { ...s, status: "done" as StepStatus, duration: timings[i] / 1000 };
            if (i === idx) return { ...s, status: "running" as StepStatus };
            return s;
          })
        );
      }, elapsed);
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.company_name) return;
    setLoading(true);
    setError("");
    setResult(null);
    resetSteps();

    // Start progress simulation
    setTimeout(() => {
      setSteps((prev) => prev.map((s, i) => (i === 0 ? { ...s, status: "running" } : s)));
    }, 100);
    simulateProgress();

    try {
      const data = await enrichProspect(form);
      // Mark all steps done
      setSteps((prev) => prev.map((s) => ({ ...s, status: "done" as StepStatus })));
      setResult(data);
    } catch (err: any) {
      setSteps((prev) =>
        prev.map((s) =>
          s.status === "running" ? { ...s, status: "error" as StepStatus } : s
        )
      );
      setError(err?.message || "Failed to connect to backend. Is the server running?");
    }
    setLoading(false);
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <h2 className="text-2xl font-bold text-gray-900">Enrich Prospect</h2>
      <p className="text-gray-600">
        Enter a company name to run the full enrichment pipeline. Try: Yellow.ai, Consolety, WISEiTECH, Prisma, Branch
      </p>

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
                  placeholder="e.g. Yellow.ai, Consolety, WISEiTECH"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Contact Name</label>
                <input
                  type="text"
                  value={form.contact_name}
                  onChange={(e) => setForm({ ...form, contact_name: e.target.value })}
                  className="w-full px-3 py-2 border rounded-md text-sm"
                  placeholder="e.g. Jane Smith (you make this up)"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Contact Email</label>
                <input
                  type="email"
                  value={form.contact_email}
                  onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
                  className="w-full px-3 py-2 border rounded-md text-sm"
                  placeholder="e.g. jane@company.com (synthetic)"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Contact Title</label>
                <input
                  type="text"
                  value={form.contact_title}
                  onChange={(e) => setForm({ ...form, contact_title: e.target.value })}
                  className="w-full px-3 py-2 border rounded-md text-sm"
                  placeholder="e.g. VP Engineering, CTO"
                />
              </div>
            </div>
            <Button type="submit" disabled={loading || !form.company_name}>
              {loading ? "Enriching..." : "Run Enrichment Pipeline"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Live Progress */}
      {(loading || result || error) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Pipeline Progress</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {steps.map((step) => (
                <div key={step.id} className="flex items-center gap-3">
                  <div className="w-6 text-center">
                    {step.status === "pending" && <span className="text-gray-300">○</span>}
                    {step.status === "running" && (
                      <span className="inline-block w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></span>
                    )}
                    {step.status === "done" && <span className="text-green-500">✓</span>}
                    {step.status === "error" && <span className="text-red-500">✗</span>}
                  </div>
                  <div className="flex-1">
                    <p className={`text-sm font-medium ${
                      step.status === "done" ? "text-green-700" :
                      step.status === "running" ? "text-blue-700" :
                      step.status === "error" ? "text-red-700" :
                      "text-gray-400"
                    }`}>
                      {step.label}
                    </p>
                    <p className="text-xs text-gray-400">{step.description}</p>
                  </div>
                  {step.status === "done" && step.duration && (
                    <span className="text-xs text-gray-400">{step.duration.toFixed(1)}s</span>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-4">
            <p className="text-red-700 text-sm font-medium">⚠️ Enrichment Failed</p>
            <p className="text-red-600 text-sm mt-1">{error}</p>
            <p className="text-gray-500 text-xs mt-2">Check that the backend is running and the OpenRouter API key is valid.</p>
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
                  <p className="font-medium">{result.segment?.replace(/_/g, " ")}</p>
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
                  <p className="font-medium text-2xl">{result.ai_maturity ?? "N/A"}<span className="text-sm text-gray-500">/3</span></p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase">Hiring Velocity</p>
                  <p className="font-medium">{result.hiring_velocity?.replace(/_/g, " ") ?? "N/A"}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase">Bench Match</p>
                  <p className="font-medium">{result.bench_match ? "✅ Yes" : "❌ No"}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase">Honesty Flags</p>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {(result.honesty_flags || []).map((f: string) => (
                      <Badge key={f} variant="secondary" className="text-xs">{f.replace(/_/g, " ")}</Badge>
                    ))}
                    {(!result.honesty_flags || result.honesty_flags.length === 0) && (
                      <span className="text-sm text-green-600">None — all signals strong</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
            <div className="mt-4 pt-4 border-t flex gap-3">
              <a href={`/prospects/${result.prospect_id}`}>
                <Button variant="outline" size="sm">View Full Brief →</Button>
              </a>
              <Button
                size="sm"
                onClick={async () => {
                  try {
                    const res = await fetch(`http://localhost:8000/prospects/${result.prospect_id}/outreach`, { method: "POST" });
                    const data = await res.json();
                    if (data.email_subject) {
                      alert(`✅ Email sent!\nSubject: ${data.email_subject}\nStatus: ${data.status}`);
                    } else {
                      alert(`❌ Failed: ${JSON.stringify(data)}`);
                    }
                  } catch (e) {
                    alert("Failed to send outreach — check backend logs");
                  }
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

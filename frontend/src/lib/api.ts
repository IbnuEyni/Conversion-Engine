const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchProspects() {
  const res = await fetch(`${API_BASE}/prospects`, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchProspect(id: string) {
  const res = await fetch(`${API_BASE}/prospects/${id}`);
  return res.json();
}

export async function enrichProspect(data: {
  company_name: string;
  contact_name?: string;
  contact_email?: string;
  contact_phone?: string;
  contact_title?: string;
}) {
  const res = await fetch(`${API_BASE}/prospects/enrich`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function sendOutreach(prospectId: string) {
  const res = await fetch(`${API_BASE}/prospects/${prospectId}/outreach`, {
    method: "POST",
  });
  return res.json();
}

export async function sendReply(prospectId: string, message: string, channel = "email") {
  const res = await fetch(`${API_BASE}/prospects/${prospectId}/reply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prospect_id: prospectId, message, channel }),
  });
  return res.json();
}

export async function fetchThread(prospectId: string) {
  const res = await fetch(`${API_BASE}/prospects/${prospectId}/thread`, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchThreads() {
  const res = await fetch(`${API_BASE}/threads`, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchAnalytics() {
  const res = await fetch(`${API_BASE}/stats/analytics`, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export type HealthData = {
  status: string;
  live_mode: boolean;
  kill_switch: string;
  hubspot: string;
  timestamp: string;
};

export type ProspectSummary = {
  id: string;
  company: string;
  segment: string;
  state: string;
  emails_sent: number;
};

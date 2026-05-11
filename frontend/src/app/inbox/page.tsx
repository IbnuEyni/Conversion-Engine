"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { fetchThreads, fetchThread, sendReply } from "@/lib/api";

const REPLY_CLASS_COLORS: Record<string, string> = {
  engaged: "bg-green-100 text-green-700",
  curious: "bg-blue-100 text-blue-700",
  hard_no: "bg-red-100 text-red-700",
  soft_defer: "bg-yellow-100 text-yellow-700",
  objection: "bg-orange-100 text-orange-700",
  ambiguous: "bg-gray-100 text-gray-700",
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

interface ThreadSummary {
  prospect_id: string;
  company: string;
  contact_name: string;
  state: string;
  message_count: number;
  last_message: { role: string; content: string; timestamp: string; channel: string } | null;
  segment: string;
}

interface Message {
  role: string;
  content: string;
  timestamp: string;
  channel: string;
}

export default function InboxPage() {
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [selectedThread, setSelectedThread] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [replyText, setReplyText] = useState("");
  const [replyResult, setReplyResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadThreads();
  }, []);

  async function loadThreads() {
    try {
      const data = await fetchThreads();
      setThreads(data);
    } catch {
      // Backend might not have threads yet
    }
  }

  async function selectThread(prospectId: string) {
    setSelectedThread(prospectId);
    setReplyResult(null);
    try {
      const thread = await fetchThread(prospectId);
      setMessages(thread);
    } catch {
      setMessages([]);
    }
  }

  async function handleSendReply() {
    if (!replyText.trim() || !selectedThread) return;
    setLoading(true);
    try {
      const result = await sendReply(selectedThread, replyText);
      setReplyResult(result);
      setReplyText("");
      // Reload thread
      const thread = await fetchThread(selectedThread);
      setMessages(thread);
      // Reload thread list
      await loadThreads();
    } catch {
      alert("Failed to send reply");
    }
    setLoading(false);
  }

  const selectedInfo = threads.find((t) => t.prospect_id === selectedThread);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Conversation Inbox</h2>
        <Badge variant="outline">{threads.length} active threads</Badge>
      </div>

      {threads.length === 0 ? (
        <Card>
          <CardContent className="pt-8 pb-8 text-center">
            <p className="text-gray-500 mb-2">No conversations yet.</p>
            <p className="text-sm text-gray-400">
              Enrich a prospect and send outreach first. Then simulate a reply from the{" "}
              <a href="/prospects" className="text-blue-600 underline">prospect detail page</a>.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Thread List */}
          <div className="lg:col-span-1 space-y-2">
            <p className="text-sm font-medium text-gray-500 mb-2">Threads</p>
            {threads.map((t) => (
              <div
                key={t.prospect_id}
                onClick={() => selectThread(t.prospect_id)}
                className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                  selectedThread === t.prospect_id
                    ? "border-blue-500 bg-blue-50"
                    : "border-gray-200 hover:bg-gray-50"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-sm">{t.company}</span>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATE_COLORS[t.state] || ""}`}>
                    {t.state.replace(/_/g, " ")}
                  </span>
                </div>
                <p className="text-xs text-gray-500">{t.contact_name || "Unknown contact"}</p>
                <div className="flex items-center justify-between mt-1">
                  <span className="text-xs text-gray-400">{t.message_count} messages</span>
                  {t.last_message && (
                    <span className="text-xs text-gray-400">
                      {t.last_message.timestamp?.slice(11, 16)}
                    </span>
                  )}
                </div>
                {t.last_message && (
                  <p className="text-xs text-gray-500 mt-1 truncate">
                    {t.last_message.role === "agent" ? "🤖 " : "👤 "}
                    {t.last_message.content?.slice(0, 60)}...
                  </p>
                )}
              </div>
            ))}
          </div>

          {/* Conversation View */}
          <div className="lg:col-span-2">
            {!selectedThread ? (
              <Card>
                <CardContent className="pt-8 pb-8 text-center">
                  <p className="text-gray-400">Select a thread to view the conversation</p>
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">
                      {selectedInfo?.company} — {selectedInfo?.contact_name}
                    </CardTitle>
                    <div className="flex gap-2">
                      <Badge variant="outline">{selectedInfo?.segment?.replace(/_/g, " ")}</Badge>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATE_COLORS[selectedInfo?.state || ""] || ""}`}>
                        {selectedInfo?.state?.replace(/_/g, " ")}
                      </span>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  {/* Messages */}
                  <div className="space-y-3 max-h-96 overflow-y-auto mb-4">
                    {messages.length === 0 ? (
                      <p className="text-sm text-gray-400 text-center py-4">No messages yet</p>
                    ) : (
                      messages.map((msg, i) => (
                        <div
                          key={i}
                          className={`p-3 rounded-lg ${
                            msg.role === "agent"
                              ? "bg-blue-50 border border-blue-100 ml-8"
                              : "bg-gray-50 border border-gray-100 mr-8"
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium text-gray-600">
                              {msg.role === "agent" ? "🤖 Agent" : "👤 Prospect"}
                            </span>
                            <div className="flex items-center gap-2">
                              <Badge variant="outline" className="text-xs">{msg.channel}</Badge>
                              <span className="text-xs text-gray-400">{msg.timestamp?.slice(11, 19)}</span>
                            </div>
                          </div>
                          <p className="text-sm text-gray-800 whitespace-pre-wrap">{msg.content}</p>
                        </div>
                      ))
                    )}
                  </div>

                  <Separator className="my-4" />

                  {/* Reply Classification Result */}
                  {replyResult && (
                    <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-sm font-medium text-green-800">Reply Processed</span>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${REPLY_CLASS_COLORS[replyResult.reply_class] || ""}`}>
                          {replyResult.reply_class}
                        </span>
                        {replyResult.should_book_call && (
                          <Badge className="bg-emerald-500 text-white text-xs">📞 Book Call</Badge>
                        )}
                        {replyResult.needs_human_handoff && (
                          <Badge variant="destructive" className="text-xs">👤 Human Handoff</Badge>
                        )}
                      </div>
                      <p className="text-xs text-gray-600">
                        State: {replyResult.state?.replace(/_/g, " ")}
                      </p>
                    </div>
                  )}

                  {/* Simulate Reply Input */}
                  <div className="space-y-2">
                    <p className="text-xs text-gray-500">Simulate a prospect reply:</p>
                    <div className="flex gap-2">
                      <textarea
                        value={replyText}
                        onChange={(e) => setReplyText(e.target.value)}
                        placeholder="Type a prospect reply... e.g. 'Tell me more about your ML team' or 'Not interested' or 'Too expensive'"
                        className="flex-1 px-3 py-2 border rounded-md text-sm h-20 resize-none"
                      />
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" onClick={handleSendReply} disabled={!replyText.trim() || loading}>
                        {loading ? "Processing..." : "Send as Prospect"}
                      </Button>
                      <div className="flex gap-1">
                        {["Tell me more", "Not interested", "Too expensive", "Let's schedule a call"].map((quick) => (
                          <button
                            key={quick}
                            onClick={() => setReplyText(quick)}
                            className="px-2 py-1 text-xs border rounded hover:bg-gray-50 text-gray-600"
                          >
                            {quick}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

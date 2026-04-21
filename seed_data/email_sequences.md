# Tenacious Outbound Email Sequences

## Sequence 1: Cold Outreach (Signal-Grounded)

### Email 1 — Day 0 (Initial Contact)

Subject: {{company_name}} + engineering capacity

Hi {{first_name}},

{{signal_paragraph}}

The pattern we see at companies in that position: recruiting capacity becomes the bottleneck before budget does. The typical time-to-hire for a senior engineer in {{their_stack}} is 45–60 days — and that's if the pipeline is already warm.

Tenacious runs dedicated {{matched_stack}} teams for companies at your stage. We have {{bench_count}} engineers available now who could start in two weeks. Worth a 30-minute conversation to see if the fit is there?

Best,
{{sender_name}}
Tenacious Consulting & Outsourcing

### Email 2 — Day 3 (Follow-up with Value)

Subject: Re: {{company_name}} + engineering capacity

Hi {{first_name}},

Following up on my note from {{day_0_date}}. I pulled together a quick comparison of how companies in {{their_sector}} at your stage are approaching {{relevant_capability}} — {{gap_brief_summary}}.

Happy to share the full brief on a call if it's useful. Would {{suggested_time}} work?

Best,
{{sender_name}}

### Email 3 — Day 7 (Final Touch)

Subject: Re: {{company_name}} + engineering capacity

Hi {{first_name}},

Last note on this — I know timing matters more than persistence. If engineering capacity isn't the constraint right now, no worries at all.

If it becomes one in the next quarter, here's my calendar link: {{calendar_link}}

Best,
{{sender_name}}

---

## Sequence 2: Warm Outreach (Referral or Inbound)

### Email 1 — Day 0

Subject: Following up — {{referral_source}} suggested we connect

Hi {{first_name}},

{{referral_source}} mentioned you might be looking at {{inferred_need}}. We work with several companies in {{their_sector}} on exactly that — typically {{engagement_type}} engagements with {{team_size}} engineers.

I put together a brief on your current hiring signals and how they compare to the top quartile in your sector. Happy to walk through it — would {{suggested_time}} work for 30 minutes?

Best,
{{sender_name}}

### Email 2 — Day 2

Subject: Re: Following up

Hi {{first_name}},

Quick follow-up — the brief I mentioned covers {{gap_brief_headline}}. It's based on public data so nothing proprietary, but the pattern is worth seeing.

Let me know if a quick call works this week.

Best,
{{sender_name}}

---

## Sequence 3: Re-Engagement (Stalled Thread)

### Email 1 — Day 0

Subject: {{company_name}} — checking in

Hi {{first_name}},

We spoke {{last_contact_timeframe}} about {{previous_topic}}. Since then, {{new_signal_paragraph}}.

Wanted to check if the situation has changed and whether it's worth reconnecting. No pressure either way.

Best,
{{sender_name}}

### Email 2 — Day 5

Subject: Re: {{company_name}} — checking in

Hi {{first_name}},

One more data point since my last note: {{additional_signal}}. If the timing is better now, I'm happy to pick up where we left off.

Calendar link if easier: {{calendar_link}}

Best,
{{sender_name}}

---

## Template Variables

| Variable | Source |
|---|---|
| `signal_paragraph` | Generated from hiring_signal_brief.json — must reference specific, verifiable data |
| `gap_brief_summary` | Generated from competitor_gap_brief.json — 1 sentence summary of top finding |
| `bench_count` | From bench_summary.json — actual available count for matched stack |
| `matched_stack` | From bench-to-brief matching — the stack that matches prospect's needs |
| `suggested_time` | From Cal.com availability — next 3 available slots |
| `calendar_link` | Cal.com public booking URL |

## Rules

1. NEVER send Email 2 or 3 if the prospect has replied (route to conversation manager)
2. NEVER send Email 3 if the prospect has not opened Email 1 (dead lead, archive)
3. Respect a 48-hour minimum gap between emails
4. All emails are marked 'draft' in metadata until Tenacious approves
5. SMS is ONLY used after a prospect has replied to at least one email

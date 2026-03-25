# Verdict Type Conventions

Each NthLayer component writes verdicts with a specific `subject.type`. Type-specific data goes in `metadata.custom` — the verdict schema stays generic.

## Verdict Types by Component

### `evaluation` — written by nthlayer-measure

An SLO evaluation result (traditional or judgment).

**`metadata.custom` fields:**
```
slo_type: "judgment" | "traditional"
slo_name: "reversal_rate" | "error_budget_burn" | "latency_p99" | etc.
target: float              — declared SLO target from spec
current_value: float       — measured value
breach: bool               — true if threshold crossed
consecutive: int           — consecutive evaluation windows in breach
autonomy_action: { previous: str, new: str } | null  — if ratchet triggered
related_signals: [{ type: str, detail: str }]         — compound context (optional)
```

### `correlation` — written by nthlayer-correlate

Root cause correlation from multiple signals.

**`metadata.custom` fields:**
```
trigger_verdict: str               — evaluation verdict ID that triggered this
root_causes: [{ service: str, type: str, confidence: float, evidence: str }]
blast_radius: [{ service: str, impact: "direct" | "downstream", slo_breached: bool }]
timeline: [{ timestamp: str, event: str, service: str }]
groups: int                        — number of correlation groups formed
events_gathered: int               — total events collected from Prometheus + verdict store
```

### `incident` — mapped to `subject.type = "triage"` or `"custom"` with `metadata.custom.incident_type = "incident"`

Written by nthlayer-respond when opening/closing incidents.

**`metadata.custom` fields:**
```
incident_id: str           — human-readable (INC-4821)
severity: int
status: "open" | "closed"
closed_at: str | null      — ISO 8601 timestamp
root_cause: { service: str, type: str, correlation_verdict_id: str }
blast_radius: [str]        — affected service names
actions_taken: [{ type: str, detail: str }]
```

### `retrospective` — written by nthlayer-learn

Post-incident analysis with the full verdict chain.

**`metadata.custom` fields:**
```
incident_verdict_id: str   — the incident verdict this analyses
duration_minutes: float
decisions_affected: int    — decisions made at degraded quality during incident
verdict_count: int         — total verdicts in the lineage chain
root_cause: { service: str, type: str, confidence: float } | null
blast_radius: [str]        — affected service names
timeline: [{ timestamp, type, service, action, summary }]  — capped at 20 entries
financial_impact: { estimated: float, currency: str, failure_mode: str, volume_source: str } | null
recommendations: [{ type: str, detail: str, spec_field: str }]
```

## Lineage Chain

For a single incident, the verdict chain:

```
evaluation (measure) → correlation (correlate) → incident (respond) → retrospective (learn)
```

Each verdict's `lineage.context` references the upstream verdict that triggered it. Walking from retrospective back to evaluation tells the complete story.

## Using `metadata.custom`

```python
from nthlayer_learn import create

verdict = create(
    subject={"type": "evaluation", "ref": "fraud-detect", "summary": "Reversal rate breach"},
    judgment={"action": "flag", "confidence": 0.95},
    producer={"system": "nthlayer-measure"},
    metadata={"custom": {
        "slo_type": "judgment",
        "slo_name": "reversal_rate",
        "target": 0.05,
        "current_value": 0.08,
        "breach": True,
        "consecutive": 3,
    }},
)
```

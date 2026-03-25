# tests/test_retrospective.py
"""Tests for the retrospective builder — verdict chain walking and analysis."""
from __future__ import annotations

import pytest

from nthlayer_learn import MemoryStore, create, link
from nthlayer_learn.retrospective import build_retrospective


def _build_chain(store):
    """Build a realistic verdict chain: evaluation → correlation → incident."""
    # Evaluation verdict (from measure)
    eval_v = create(
        subject={"type": "evaluation", "ref": "fraud-detect", "summary": "Reversal rate breach"},
        judgment={"action": "flag", "confidence": 0.9},
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
    store.put(eval_v)

    # Correlation verdict (from correlate)
    corr_v = create(
        subject={"type": "correlation", "ref": "fraud-detect", "summary": "1 group across 3 services"},
        judgment={"action": "flag", "confidence": 0.85},
        producer={"system": "sitrep"},
        metadata={"custom": {
            "trigger_verdict": eval_v.id,
            "root_causes": [{"service": "fraud-detect", "type": "model_deploy", "confidence": 0.9}],
            "blast_radius": [
                {"service": "fraud-detect", "impact": "direct"},
                {"service": "payment-api", "impact": "downstream"},
            ],
        }},
    )
    link(corr_v, context=[eval_v.id])
    store.put(corr_v)

    # Incident verdict (from respond triage)
    incident_v = create(
        subject={"type": "triage", "ref": "fraud-detect", "summary": "INC-4821"},
        judgment={"action": "flag", "confidence": 0.8},
        producer={"system": "nthlayer-respond"},
        metadata={"custom": {
            "incident_id": "INC-4821",
            "severity": 1,
            "blast_radius": [
                {"service": "fraud-detect", "impact": "direct"},
                {"service": "payment-api", "impact": "downstream"},
                {"service": "checkout", "impact": "downstream"},
                {"service": "loyalty", "impact": "downstream"},
            ],
            "root_causes": [{"service": "fraud-detect", "type": "model_deploy", "confidence": 0.9}],
        }},
    )
    link(incident_v, context=[corr_v.id])
    store.put(incident_v)

    return eval_v, corr_v, incident_v


def test_build_retrospective_produces_verdict():
    store = MemoryStore()
    _, _, incident = _build_chain(store)

    retro = build_retrospective(incident.id, store)
    assert retro.subject.type == "retrospective"
    assert retro.producer.system == "nthlayer-learn"
    assert incident.id in retro.lineage.context


def test_retrospective_walks_lineage():
    store = MemoryStore()
    eval_v, corr_v, incident = _build_chain(store)

    retro = build_retrospective(incident.id, store)
    custom = retro.metadata.custom

    # Should have found all verdicts in chain
    assert custom["verdict_count"] >= 3


def test_retrospective_computes_duration():
    store = MemoryStore()
    _, _, incident = _build_chain(store)

    retro = build_retrospective(incident.id, store)
    custom = retro.metadata.custom

    # Duration should be ≥ 0 (all created within the same test, so very small)
    assert custom["duration_minutes"] >= 0


def test_retrospective_generates_recommendations():
    store = MemoryStore()
    _, _, incident = _build_chain(store)

    retro = build_retrospective(incident.id, store)
    custom = retro.metadata.custom
    recs = custom["recommendations"]

    # Should recommend SLO gate (judgment SLO breach found)
    slo_gate_recs = [r for r in recs if r["type"] == "slo_gate"]
    assert len(slo_gate_recs) >= 1

    # Should recommend dependency review (blast radius > 3)
    dep_recs = [r for r in recs if r["type"] == "dependency_review"]
    assert len(dep_recs) >= 1

    # Should recommend change control (root cause was model_deploy)
    change_recs = [r for r in recs if r["type"] == "change_control"]
    assert len(change_recs) >= 1


def test_retrospective_raises_on_missing_verdict():
    store = MemoryStore()
    with pytest.raises(KeyError):
        build_retrospective("vrd-nonexistent", store)

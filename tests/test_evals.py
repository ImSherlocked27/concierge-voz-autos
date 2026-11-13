import math

import pytest

from evals.report import aggregate, percentile, render
from scripts.configure import build


def conversation(identifier, latency=None, outcome="success", medium="audio"):
    return {"conversation_id": identifier, "analysis": {"call_successful": outcome}, "transcript": [{"role": "user", "message": "synthetic fixture"}, {"role": "agent", "source_medium": medium, "tool_calls": [{"tool_name": "search_vehicles"}], "conversation_turn_metrics": {"metrics": {"convai_ttf_audio_since_silence": {"elapsed_time": latency}}}}]}


def test_empty_report_does_not_invent_numbers():
    result = aggregate([])
    assert result["success_rate"] is None
    assert result["p50_ms"] is None
    assert "Pendiente" in render(result)
    assert "0.0 ms" not in render(result)


def test_latency_units_percentiles_and_duplicates():
    first = conversation("a", .1)
    result = aggregate([first, first, conversation("b", .5, "failure"), conversation("c", 1)])
    assert result["conversations"] == 3
    assert result["p50_ms"] == 500
    assert result["p95_ms"] == pytest.approx(950)
    assert result["success_rate"] == pytest.approx(2 / 3)
    assert result["tool_calls"] == 3


def test_text_simulation_does_not_count_as_voice_latency():
    result = aggregate([conversation("text", .2, medium="text"), conversation("none", .3, medium=None)])
    assert result["latency_samples"] == 0
    assert result["p50_ms"] is None


@pytest.mark.parametrize("value", [None, "0.2", -1, math.nan, math.inf, True])
def test_invalid_latency_is_not_counted(value):
    assert aggregate([conversation("a", value)])["latency_samples"] == 0


def test_unknown_evaluations_have_separate_denominator():
    result = aggregate([conversation("a", .1), conversation("b", .2, "unknown")])
    assert result["success_rate"] == 1
    assert result["evaluated"] == 1
    assert result["unknown"] == 1


def test_missing_medium_requires_explicit_audio_metadata():
    value = conversation("audio-export", .5, medium=None)
    value["metadata"] = {"text_only": False}
    assert aggregate([value])["p50_ms"] == 500
    value["metadata"]["text_only"] = True
    assert aggregate([value])["latency_samples"] == 0


def test_greeting_is_not_response_latency():
    value = conversation("a", .5)
    value["transcript"] = value["transcript"][1:]
    assert aggregate([value])["latency_samples"] == 0


def test_deterministic_filter_verification_detects_over_budget_and_extra_filters():
    from scripts.evaluate import verify_filters
    scenario = {"tool": "search_vehicles", "parameters": {"max_price": "22000", "body": "suv"}}
    def run(params):
        import json
        return {"agent_responses": [{"tool_calls": [{"tool_name": "search_vehicles", "params_as_json": json.dumps(params)}]}]}
    assert verify_filters(run({"max_price": 22000, "body": "suv"}), scenario)[0]
    assert not verify_filters(run({"max_price": 23000, "body": "suv"}), scenario)[0]
    assert not verify_filters(run({"max_price": 22000, "body": "suv", "feature": "diesel"}), scenario)[0]


def test_public_evidence_preserves_metrics_without_private_content():
    from evals.report import sanitize
    original = conversation("a", .5)
    original["metadata"] = {"text_only": False, "private_email": "private@example.invalid"}
    original["transcript"][1]["message"] = "private text"
    original["transcript"][1]["tool_calls"][0]["params_as_json"] = "private payload"
    public = sanitize([original])
    import json
    assert "private" not in json.dumps(public)
    assert aggregate(public) == aggregate([original])


def test_sdk_configs_and_native_test_types():
    ids = {name: "test_" + name for name in ["search_vehicles", "get_vehicle", "schedule_visit"]}
    agent, tools, tests = build("https://example.invalid", "secret-placeholder", "voice-placeholder", ids, [], [])
    assert len(tools) == 3
    assert len(tests) == 10
    assert {test["type"] for test in tests} == {"llm", "tool", "simulation"}
    assert agent["platform_settings"]["auth"]["enable_auth"] is True
    assert agent["platform_settings"]["call_limits"]["bursting_enabled"] is False
    assert percentile([], .95) is None

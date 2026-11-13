"""Aggregate exported GET-conversation responses without publishing transcripts."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * p
    lo, hi = math.floor(rank), math.ceil(rank)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (rank - lo)


def sanitize(conversations: list[dict]) -> list[dict]:
    """Keep recomputable evidence, excluding messages, headers, tool args and user metadata."""
    evidence = []
    for conversation in conversations:
        analysis = conversation.get("analysis") or {}
        metadata = conversation.get("metadata") or {}
        evidence.append({
            "conversation_id": conversation.get("conversation_id"),
            "metadata": {key: metadata[key] for key in ("text_only", "start_time_unix_secs") if key in metadata},
            "analysis": {"call_successful": analysis.get("call_successful"), "evaluation_criteria_results": {
                key: {"result": (value or {}).get("result")} for key, value in (analysis.get("evaluation_criteria_results") or {}).items()}},
            "transcript": [{"role": turn.get("role"), "source_medium": turn.get("source_medium"),
                            "conversation_turn_metrics": {"metrics": {key: value for key, value in ((turn.get("conversation_turn_metrics") or {}).get("metrics") or {}).items() if key == "convai_ttf_audio_since_silence"}},
                            "tool_calls": [{"tool_name": call.get("tool_name")} for call in turn.get("tool_calls") or []]}
                           for turn in conversation.get("transcript") or []]})
    return evidence


def aggregate(conversations: list[dict]) -> dict:
    latency, outcomes = [], []
    tools = 0
    criteria = {}
    seen = set()
    for index, conversation in enumerate(conversations):
        identifier = conversation.get("conversation_id") or conversation.get("id") or f"missing-{index}"
        if identifier in seen:
            continue
        seen.add(identifier)
        analysis = conversation.get("analysis") or {}
        outcome = analysis.get("call_successful")
        outcomes.append(outcome if outcome in ("success", "failure") else "unknown")
        for name, result in (analysis.get("evaluation_criteria_results") or {}).items():
            status = (result or {}).get("result", "unknown")
            bucket = criteria.setdefault(name, {"success": 0, "failure": 0, "unknown": 0})
            bucket[status if status in bucket else "unknown"] += 1
        has_user_turn = False
        for turn in conversation.get("transcript") or []:
            tools += len(turn.get("tool_calls") or [])
            if turn.get("role") == "user":
                has_user_turn = True
            # Some audio exports omit per-turn source_medium. Require affirmative
            # audio evidence at turn or conversation level; never infer it from absence.
            medium = turn.get("source_medium")
            audio_turn = medium == "audio" or (medium is None and (conversation.get("metadata") or {}).get("text_only") is False)
            if turn.get("role") != "agent" or not audio_turn or not has_user_turn:
                continue
            metrics = (turn.get("conversation_turn_metrics") or {}).get("metrics") or {}
            record = metrics.get("convai_ttf_audio_since_silence") or {}
            value = record.get("elapsed_time")
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
                latency.append(value * 1000)
    successes, failures = outcomes.count("success"), outcomes.count("failure")
    evaluated = successes + failures
    return {"conversations": len(seen), "evaluated": evaluated, "unknown": outcomes.count("unknown"),
            "successes": successes, "failures": failures, "success_rate": successes / evaluated if evaluated else None,
            "latency_samples": len(latency), "p50_ms": percentile(latency, .5), "p95_ms": percentile(latency, .95),
            "tool_calls": tools, "criteria": criteria}


def render(result: dict) -> str:
    def ms(value):
        return f"{value:.1f} ms" if value is not None else "Pendiente · sin muestras de audio"
    rate = result["success_rate"]
    rate_text = f"{rate:.1%}" if rate is not None else "Pendiente · sin evaluaciones"
    lines = ["# Evidencia de conversaciones", "", "Datos agregados de exportaciones reales de ElevenLabs. Sin transcript ni audio en este informe.", "",
             "| Métrica | Resultado |", "| --- | --- |",
             f"| Conversaciones únicas | {result['conversations']} |",
             f"| Éxito de conversaciones evaluadas | {rate_text} |",
             f"| Evaluadas / sin resultado | {result['evaluated']} / {result['unknown']} |",
             f"| Latencia p50 | {ms(result['p50_ms'])} |", f"| Latencia p95 | {ms(result['p95_ms'])} |",
             f"| Turnos de audio con latencia válida | {result['latency_samples']} |", f"| Llamadas a herramientas | {result['tool_calls']} |", "",
             "Latencia: convai_ttf_audio_since_silence.elapsed_time (segundos → ms), desde el silencio del usuario hasta el primer audio del agente. Solo turnos posteriores al usuario con source_medium=audio o metadata.text_only=false cuando falta source_medium. Se excluye el saludo. Percentiles con interpolación lineal; no se mezclan simulaciones de texto.", "",
             "## Criterios", ""]
    if not result["criteria"]:
        lines.append("Pendiente · todavía no hay criterios evaluados.")
    for name, counts in result["criteria"].items():
        lines.append(f"- {name}: {counts['success']} éxitos, {counts['failure']} fallas, {counts['unknown']} sin resultado.")
    lines += ["", "La tasa de la suite nativa se informa por separado en evals/native-report.md. Este informe no estima calidad usando tests locales.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("evals/raw"))
    parser.add_argument("--output", type=Path, default=Path("evals/report.md"))
    parser.add_argument("--public-evidence", type=Path, default=Path("evals/evidence.json"))
    args = parser.parse_args()
    conversations = []
    paths = [args.input] if args.input.is_file() else sorted(args.input.glob("*.json"))
    for path in paths:
        value = json.loads(path.read_text(encoding="utf-8"))
        values = value if isinstance(value, list) else [value]
        for item in values:
            if not isinstance(item, dict) or not isinstance(item.get("transcript", []), list):
                raise SystemExit(f"Invalid conversation export: {path.name}")
            conversations.append(item)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(aggregate(conversations)), encoding="utf-8")
    args.public_evidence.parent.mkdir(parents=True, exist_ok=True)
    args.public_evidence.write_text(json.dumps(sanitize(conversations), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Report generated: {args.output} · {len(conversations)} input exports")


if __name__ == "__main__":
    main()

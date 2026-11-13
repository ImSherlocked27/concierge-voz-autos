"""Run native tests, wait for results and export only aggregate evidence."""
import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

ROOT = Path(__file__).resolve().parents[1]


def verify_filters(run: dict, scenario: dict) -> tuple[bool, str]:
    """Evaluate actual emitted calls, with numeric budget comparison and strict strings."""
    calls = [call for turn in run.get("agent_responses") or [] for call in turn.get("tool_calls") or []]
    selected = [call for call in calls if call.get("tool_name") == scenario.get("tool")]
    if scenario.get("verify_absence"):
        return not selected, "herramienta ausente" if not selected else "herramienta prohibida invocada"
    if not selected:
        return False, "no se observó la herramienta esperada"
    expected = scenario.get("parameters") or {}
    for call in selected:
        try:
            values = json.loads(call.get("params_as_json") or "{}")
        except (ValueError, TypeError):
            return False, "parámetros JSON inválidos"
        if not isinstance(values, dict):
            return False, "parámetros no son un objeto"
        if any(key not in expected for key in values):
            return False, "filtros no solicitados"
        for key, value in expected.items():
            actual = values.get(key)
            if key == "max_price":
                try:
                    equal = not isinstance(actual, bool) and float(actual) == float(value)
                except (TypeError, ValueError):
                    equal = False
            else:
                equal = actual == value
            if not equal:
                return False, f"filtro incorrecto: {key}"
    return True, "filtros exactos verificados sobre tool calls reales"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=1, choices=range(1, 6))
    parser.add_argument("--conversation", action="append", default=[], help="Consented audio conversation ID to include in the latency report")
    parser.add_argument("--export-only", action="store_true")
    parser.add_argument("--suite-id", help="Fetch an existing invocation instead of spending credits on a new run")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    if not os.getenv("ELEVENLABS_API_KEY"):
        raise SystemExit("Configure ELEVENLABS_API_KEY locally first")
    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    raw = ROOT / "evals/raw"
    raw.mkdir(parents=True, exist_ok=True)
    suite_failed = False
    if not args.export_only:
        state_path = ROOT / ".local/state.json"
        if not state_path.exists():
            raise SystemExit("Run python -m scripts.configure --apply first")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        invocation = (client.conversational_ai.tests.invocations.get(args.suite_id) if args.suite_id else
                      client.conversational_ai.agents.run_tests(state["agent_id"], tests=[{"test_id": value} for value in state["tests"].values()], repeat_count=args.repeat))
        (ROOT / ".local/last-suite-id.txt").write_text(invocation.id, encoding="utf-8")
        deadline = time.monotonic() + 600
        while any(run.status in ("pending", "running") for run in invocation.test_runs):
            if time.monotonic() > deadline:
                raise SystemExit("Suite still running; invocation ID saved in .local/last-suite-id.txt. No result claimed.")
            time.sleep(3)
            invocation = client.conversational_ai.tests.invocations.get(invocation.id)
        results = [run.model_dump(mode="json") for run in invocation.test_runs]
        (raw / "native-suite.json.private").write_text(json.dumps(results, indent=2), encoding="utf-8")
        scenarios = {s["name"]: s for s in json.loads((ROOT / "test_configs/scenarios.json").read_text(encoding="utf-8"))}
        filter_checks = []
        for run in results:
            scenario = scenarios.get(run.get("test_name"), {})
            if scenario.get("type") == "tool":
                ok, reason = verify_filters(run, scenario)
                filter_checks.append({"name": run.get("test_name"), "passed": ok, "reason": reason})
        passed = sum(run.get("status") == "passed" for run in results)
        failed = sum(run.get("status") == "failed" for run in results)
        other = len(results) - passed - failed
        lines = ["# Suite nativa de ElevenLabs", "", f"Invocación: `{invocation.id}`", f"Repeticiones solicitadas: {args.repeat}",
                 f"Ejecuciones: {len(results)} · pasadas: {passed} · falladas: {failed} · otras: {other}", ""]
        if results:
            lines.append(f"Tasa de pase sobre todas las ejecuciones: {passed / len(results):.1%}")
        for run in results:
            info = run.get("test_info") or {}
            name = run.get("test_name") or info.get("name") or run.get("test_id") or "test"
            lines.append(f"- {name}: {run.get('status', 'unknown')}")
        lines += ["", "## Verificación determinista de filtros", "", "La suite nativa evalúa la herramienta elegida. El harness valida por separado los parámetros JSON emitidos contra los filtros solicitados; no usa rutas de parámetros sin documentar del evaluador nativo.", ""]
        for check in filter_checks:
            lines.append(f"- {check['name']}: {'PASS' if check['passed'] else 'FAIL'} · {check['reason']}")
        (ROOT / "evals/native-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        evidence = {"suite_id": invocation.id, "repeat_count": invocation.repeat_count or args.repeat,
                    "runs": [{"test_name": run.get("test_name"), "test_id": run.get("test_id"), "status": run.get("status")} for run in results],
                    "deterministic_filter_checks": filter_checks}
        (ROOT / "evals/native-evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Native suite completed: {passed}/{len(results)} passed; {failed} failed; {other} other")
        suite_failed = bool(failed or other or not results or any(not check["passed"] for check in filter_checks))
    for identifier in args.conversation:
        conversation = client.conversational_ai.conversations.get(identifier)
        safe_id = "".join(char for char in identifier if char.isalnum() or char in "_-")
        if not safe_id:
            raise SystemExit("Invalid conversation ID")
        (raw / f"{safe_id}.json").write_text(conversation.model_dump_json(indent=2), encoding="utf-8")
    from evals.report import aggregate, render, sanitize
    exports = [json.loads(path.read_text(encoding="utf-8")) for path in raw.glob("*.json")]
    (ROOT / "evals/report.md").write_text(render(aggregate(exports)), encoding="utf-8")
    (ROOT / "evals/evidence.json").write_text(json.dumps(sanitize(exports), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if suite_failed:
        raise SystemExit("Native suite or filter assertions failed; inspect evals/native-report.md")


if __name__ == "__main__":
    main()

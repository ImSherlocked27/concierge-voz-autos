"""Validate offline; provision with --apply. Never stores credential values."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv, set_key
from pydantic import TypeAdapter
from elevenlabs.types import ConversationalConfig, AgentPlatformSettingsRequestModel, ToolRequestModel
from elevenlabs.conversational_ai.tests.client import TestsCreateRequestBody

ROOT = Path(__file__).resolve().parents[1]


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def native_tests(tool_ids: dict[str, str]) -> list[dict]:
    tests = []
    for scenario in read(ROOT / "test_configs/scenarios.json"):
        kind = scenario["type"]
        test = {"type": kind, "name": scenario["name"]}
        if kind != "simulation":
            test["chat_history"] = [{"role": "user", "message": scenario["message"], "time_in_call_secs": 0}]
        if kind == "tool":
            test["tool_call_parameters"] = {
                "referenced_tool": {"id": tool_ids[scenario["tool"]], "type": "webhook"},
                "verify_absence": scenario.get("verify_absence", False),
                # Native evaluator checks the selected tool. The harness separately
                # parses params_as_json and checks exact filters deterministically.
                # This avoids undocumented provider-specific parameter path syntax.
                "parameters": [],
            }
        else:
            test["success_condition"] = scenario["success_condition"]
        if kind == "simulation":
            test.update({key: scenario[key] for key in ("simulation_scenario", "simulation_max_turns")})
            # Full journey runs against the real fictional backend; no simulated tool success.
            test["tool_mock_config"] = {"mocking_strategy": "none", "fallback_strategy": "call_real_tool"}
        TypeAdapter(TestsCreateRequestBody).validate_python(test)
        tests.append(test)
    return tests


def build(api_base: str, secret_id: str, voice_id: str, tool_ids: dict[str, str], kb: list, test_ids: list):
    tools = {}
    for path in sorted((ROOT / "tool_configs").glob("*.json")):
        content = path.read_text(encoding="utf-8").replace("{{API_BASE}}", api_base).replace("{{TOOLS_SECRET_ID}}", secret_id)
        tool = json.loads(content)
        ToolRequestModel.model_validate({"tool_config": tool})
        tools[tool["name"]] = tool
    agent = read(ROOT / "agent_configs/concierge.json")
    agent["conversation_config"]["tts"]["voice_id"] = voice_id
    agent["conversation_config"]["conversation"]["max_duration_seconds"] = int(os.getenv("DEMO_MAX_DURATION_SECONDS", "180"))
    prompt = agent["conversation_config"]["agent"]["prompt"]
    prompt["prompt"] += "\n\n" + (ROOT / "agent_configs/clarification.md").read_text(encoding="utf-8")
    prompt["prompt"] += "\n\n" + (ROOT / "agent_configs/voice-grounding.md").read_text(encoding="utf-8")
    prompt["prompt"] += "\n\n" + (ROOT / "agent_configs/scope.md").read_text(encoding="utf-8")
    prompt.update(tool_ids=list(tool_ids.values()), knowledge_base=kb)
    agent["platform_settings"]["call_limits"]["daily_limit"] = int(os.getenv("DEMO_DAILY_SESSIONS", "10"))
    agent["platform_settings"]["testing"]["attached_tests"] = [{"test_id": test_id} for test_id in test_ids]
    ConversationalConfig.model_validate(agent["conversation_config"])
    AgentPlatformSettingsRequestModel.model_validate(agent["platform_settings"])
    return agent, tools, native_tests(tool_ids)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Creates/updates billable ElevenLabs resources; requires .env")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    dummy_ids = {name: f"placeholder_{name}" for name in ("search_vehicles", "get_vehicle", "schedule_visit")}
    build("https://example.invalid", "placeholder_secret", "placeholder_voice", dummy_ids, [], [])
    if not args.apply:
        print("Validated agent, 3 webhook tools and 10 native tests against ElevenLabs SDK 2.78.0. No network requests or paid tests.")
        return
    required = ["ELEVENLABS_API_KEY", "API_BASE", "TOOLS_SECRET", "VOICE_ID", "DEMO_ACCESS_CODE"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise SystemExit("Missing local settings: " + ", ".join(missing))
    base = os.environ["API_BASE"].rstrip("/")
    if not base.startswith("https://"):
        raise SystemExit("API_BASE must be a publicly reachable HTTPS origin, not localhost")
    # Check the deployed webhook authentication before provisioning any resource.
    with httpx.Client(timeout=30) as transport:
        probe = transport.get(base + "/vehicles", headers={"X-Tools-Secret": os.environ["TOOLS_SECRET"]}, params={"limit": 1})
        probe.raise_for_status()
        if probe.json().get("fictional") is not True:
            raise SystemExit("API_BASE did not return the fictional inventory")
    state_path = ROOT / ".local/state.json"
    state = read(state_path) if state_path.exists() else {"tools": {}, "documents": {}, "tests": {}}

    def save():
        write(state_path, state)

    with httpx.Client(base_url="https://api.elevenlabs.io/v1/convai/", headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]}, timeout=60) as client:
        def api(method, path, payload):
            response = client.request(method, path, json=payload)
            if response.is_error:
                # Do not print upstream bodies that may contain private configuration.
                details = response.json().get("detail", {})
                summary = ""
                if isinstance(details, list):
                    summary = "; ".join(f"{item.get('loc')}: {item.get('msg')}" for item in details)
                elif isinstance(details, dict):
                    summary = str(details.get("message") or details.get("status") or "")
                raise RuntimeError(f"ElevenLabs {method} {path}: HTTP {response.status_code}; {summary}")
            return response.json()

        if not state.get("secret_id"):
            result = api("POST", "secrets", {"type": "new", "name": "concierge-tools", "value": os.environ["TOOLS_SECRET"]})
            state["secret_id"] = result["secret_id"]
            save()
        # Documents are immutable in this script: edit a policy, then explicitly remove its local ID to reupload.
        for path in sorted((ROOT / "kb").glob("*.md")):
            if path.name not in state["documents"]:
                result = api("POST", "knowledge-base/text", {"name": path.stem, "text": path.read_text(encoding="utf-8")})
                state["documents"][path.name] = result["id"]
                save()
        _, tools, _ = build(base, state["secret_id"], os.environ["VOICE_ID"], dummy_ids, [], [])
        for name, tool in tools.items():
            existing = state["tools"].get(name)
            result = api("PATCH" if existing else "POST", f"tools/{existing}" if existing else "tools", {"tool_config": tool})
            state["tools"][name] = result["id"]
            save()
        _, _, tests = build(base, state["secret_id"], os.environ["VOICE_ID"], state["tools"], [], [])
        for index, test in enumerate(tests):
            existing = state["tests"].get(test["name"])
            result = api("PUT" if existing else "POST", f"agent-testing/{existing}" if existing else "agent-testing/create", test)
            state["tests"][test["name"]] = result["id"]
            write(ROOT / f".local/test_configs/{index:02}.json", test)
            save()
        kb = [{"id": doc_id, "name": name, "type": "text", "usage_mode": "prompt"} for name, doc_id in state["documents"].items()]
        agent, tools, _ = build(base, state["secret_id"], os.environ["VOICE_ID"], state["tools"], kb, list(state["tests"].values()))
        existing = state.get("agent_id") or os.getenv("AGENT_ID")
        result = api("PATCH" if existing else "POST", f"agents/{existing}" if existing else "agents/create", agent)
        state["agent_id"] = result.get("agent_id", existing)
        save()
        set_key(str(ROOT / ".env"), "AGENT_ID", state["agent_id"])
        write(ROOT / ".local/agent_configs/concierge.json", agent)
        write(ROOT / "agents.json", {"agents": [{"id": state["agent_id"], "config": ".local/agent_configs/concierge.json"}]})
        write(ROOT / "tools.json", {"tools": [{"id": state["tools"][name], "type": "webhook", "config": f".local/tool_configs/{name}.json"} for name in tools]})
        write(ROOT / "tests.json", {"tests": [{"id": state["tests"][test["name"]], "type": test["type"], "config": f".local/test_configs/{i:02}.json"} for i, test in enumerate(tests)]})
        for name, tool in tools.items():
            write(ROOT / f".local/tool_configs/{name}.json", tool)
    print(f"Configured private agent {state['agent_id']}. AGENT_ID saved in .env. Set it on your host and restart the server.")
    print("CLI: elevenlabs agents status | elevenlabs agents push --dry-run | elevenlabs agents test " + state["agent_id"])


if __name__ == "__main__":
    main()

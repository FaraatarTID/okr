"""Smoke-test migrated Supabase API mode routes through backend API.

Usage (PowerShell):
  $env:OKR_BACKEND_API_URL="http://127.0.0.1:8100"
  $env:OKR_BACKEND_SERVICE_TOKEN="local-development-secret-token"
  $env:OKR_SMOKE_ACTOR="admin"
  python scripts/smoke_supabase_api_mode.py
"""

from __future__ import annotations

import json
import os
import random
import string
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from pathlib import Path


@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ""


class BackendClient:
    def __init__(self, base_url: str, actor: str, service_token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.actor = actor
        self.service_token = service_token

    def request(self, method: str, path: str, payload: Optional[dict[str, Any]] = None) -> tuple[int, Any]:
        body = None
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-OKR-Actor": self.actor,
            "X-OKR-Service-Token": self.service_token,
        }
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = Request(f"{self.base_url}{path}", data=body, method=method.upper(), headers=headers)
        try:
            with urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                parsed = json.loads(raw) if raw.strip() else None
                return int(resp.status), parsed
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw.strip() else {"raw": raw}
            except Exception:
                parsed = {"raw": raw}
            return int(exc.code), parsed
        except URLError as exc:
            return 0, {"error": str(exc)}


def _rand_suffix(n: int = 6) -> str:
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(n))


def _read_env_file_value(env_path: Path, key: str) -> str:
    if not env_path.exists():
        return ""
    wanted = str(key or "").strip().upper()
    if not wanted:
        return ""
    try:
        lines = env_path.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
    except Exception:
        return ""
    for raw in lines:
        line = raw.strip()
        if (not line) or line.startswith("#") or ("=" not in line):
            continue
        k, v = line.split("=", 1)
        if k.strip().upper() != wanted:
            continue
        return v.strip().strip('"').strip("'")
    return ""


def _expect(status: int, expected: set[int], name: str, payload: Any) -> Result:
    if status in expected:
        return Result(name=name, ok=True, detail=f"status={status}")
    return Result(name=name, ok=False, detail=f"status={status} payload={payload}")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    docker_env = repo_root / "deploy" / "docker" / ".env"
    base_url = str(os.getenv("OKR_BACKEND_API_URL", "")).strip()
    if not base_url:
        base_url = _read_env_file_value(docker_env, "OKR_BACKEND_API_URL")
    if not base_url:
        base_url = "http://127.0.0.1:8100"

    token = str(os.getenv("OKR_BACKEND_SERVICE_TOKEN", "")).strip()
    if not token:
        token = _read_env_file_value(docker_env, "OKR_BACKEND_SERVICE_TOKEN")

    actor = str(os.getenv("OKR_SMOKE_ACTOR", "")).strip()
    if not actor:
        actor = _read_env_file_value(docker_env, "OKR_BACKEND_DEFAULT_ACTOR")
    if not actor:
        actor = "admin"
    if not token:
        print("[ERROR] OKR_BACKEND_SERVICE_TOKEN is required.")
        return 2

    client = BackendClient(base_url=base_url, actor=actor, service_token=token)
    results: list[Result] = []

    # Health check
    st, pl = client.request("GET", "/healthz")
    results.append(_expect(st, {200}, "healthz", pl))

    # Create entities
    sfx = _rand_suffix()
    username = f"smoke_{sfx}"
    password = f"S!moke{_rand_suffix(8)}A1"
    st, pl = client.request(
        "POST",
        "/v1/users",
        {
            "username": username,
            "password": password,
            "role": "member",
            "display_name": f"Smoke {sfx}",
            "must_change_password": False,
            "actor_username": actor,
        },
    )
    results.append(_expect(st, {201}, "create_user", pl))
    user_id = int((pl or {}).get("id") or 0) if st == 201 else 0

    st, pl = client.request(
        "POST",
        "/v1/teams",
        {"name": f"Smoke Team {sfx}", "description": "smoke", "actor_username": actor},
    )
    results.append(_expect(st, {201}, "create_team", pl))
    team_id = int((pl or {}).get("id") or 0) if st == 201 else 0

    now = datetime.now(timezone.utc)
    st, pl = client.request(
        "POST",
        "/v1/cycles",
        {
            "title": f"Smoke Cycle {sfx}",
            "start_date": (now - timedelta(days=1)).isoformat(),
            "end_date": (now + timedelta(days=30)).isoformat(),
            "is_active": True,
            "owner_manager_id": None,
            "actor_username": actor,
        },
    )
    results.append(_expect(st, {201}, "create_cycle", pl))
    cycle_id = int((pl or {}).get("id") or 0) if st == 201 else 0

    # Update user with created team
    if user_id and team_id:
        st, pl = client.request(
            "PATCH",
            f"/v1/users/{user_id}",
            {"team_id": team_id, "actor_username": actor},
        )
        results.append(_expect(st, {200}, "update_user", pl))

    # Node hierarchy create + mutations
    goal_id = objective_id = kr_id = task_id = 0
    if cycle_id:
        st, pl = client.request(
            "POST",
            "/v1/nodes/goal",
            {
                "user_id": username,
                "title": f"Smoke Goal {sfx}",
                "description": "smoke",
                "cycle_id": cycle_id,
                "actor_username": actor,
            },
        )
        results.append(_expect(st, {201}, "create_goal", pl))
        goal_id = int((pl or {}).get("id") or 0) if st == 201 else 0

    if goal_id:
        st, pl = client.request(
            "POST",
            "/v1/nodes/objective",
            {"goal_id": goal_id, "title": f"Smoke Obj {sfx}", "description": "smoke", "actor_username": actor},
        )
        results.append(_expect(st, {201}, "create_objective", pl))
        objective_id = int((pl or {}).get("id") or 0) if st == 201 else 0

    if objective_id:
        st, pl = client.request(
            "POST",
            "/v1/nodes/key_result",
            {
                "objective_id": objective_id,
                "title": f"Smoke KR {sfx}",
                "description": "smoke",
                "target_value": 100,
                "unit": "%",
                "actor_username": actor,
            },
        )
        results.append(_expect(st, {201}, "create_key_result", pl))
        kr_id = int((pl or {}).get("id") or 0) if st == 201 else 0

    if kr_id:
        st, pl = client.request(
            "POST",
            "/v1/nodes/task",
            {
                "key_result_id": kr_id,
                "title": f"Smoke Task {sfx}",
                "description": "smoke",
                "estimated_minutes": 25,
                "assignee_id": user_id if user_id else None,
                "actor_username": actor,
            },
        )
        results.append(_expect(st, {201}, "create_task", pl))
        task_id = int((pl or {}).get("id") or 0) if st == 201 else 0

    # timer start/stop
    if task_id:
        st, pl = client.request("POST", "/v1/timer/start", {"task_id": task_id, "user_id": actor})
        results.append(_expect(st, {200}, "timer_start", pl))
        st, pl = client.request(
            "POST",
            "/v1/timer/stop",
            {"task_id": task_id, "summary": "smoke session", "user_id": actor},
        )
        results.append(_expect(st, {200}, "timer_stop", pl))

    # check-in + experiments
    experiment_id = 0
    if kr_id:
        st, pl = client.request(
            "POST",
            "/v1/check-ins",
            {
                "kr_id": kr_id,
                "value": 10.0,
                "confidence": 7,
                "comment": "smoke",
                "variation_type": "COMMON_CAUSE",
                "actor_username": actor,
            },
        )
        results.append(_expect(st, {201}, "create_check_in", pl))

        st, pl = client.request(
            "POST",
            "/v1/experiments",
            {
                "key_result_id": kr_id,
                "cycle_id": cycle_id,
                "hypothesis": "smoke hypothesis",
                "change_description": "smoke change",
                "actor_username": actor,
            },
        )
        results.append(_expect(st, {201}, "create_experiment", pl))
        experiment_id = int((pl or {}).get("id") or 0) if st == 201 else 0

    if experiment_id:
        st, pl = client.request(
            "PATCH",
            f"/v1/experiments/{experiment_id}",
            {"updates": {"status": "RUNNING"}, "actor_username": actor},
        )
        results.append(_expect(st, {200}, "update_experiment", pl))
        st, pl = client.request(
            "POST",
            f"/v1/experiments/{experiment_id}/close",
            {"decision": "ITERATE", "rationale": "smoke", "actor_username": actor},
        )
        results.append(_expect(st, {200}, "close_experiment", pl))

    # retrospective + outcome
    retrospective_id = 0
    if user_id and cycle_id:
        week_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        st, pl = client.request(
            "POST",
            "/v1/retrospectives",
            {
                "user_id": user_id,
                "cycle_id": cycle_id,
                "week_start_date": week_start.isoformat(),
                "content": "smoke retrospective",
                "sentiment": "neutral",
                "actor_username": actor,
            },
        )
        results.append(_expect(st, {201}, "create_retrospective", pl))
        retrospective_id = int((pl or {}).get("id") or 0) if st == 201 else 0

    if retrospective_id and experiment_id:
        st, pl = client.request(
            "PUT",
            f"/v1/retrospectives/{retrospective_id}/experiment-outcomes",
            {
                "experiment_id": experiment_id,
                "decision": "ITERATE",
                "rationale": "smoke",
                "actor_username": actor,
            },
        )
        results.append(_expect(st, {200}, "upsert_retro_outcome", pl))

    # weekly plan
    if user_id:
        week_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        st, pl = client.request(
            "POST",
            "/v1/weekly-plans",
            {
                "user_id": user_id,
                "start_date": week_start.isoformat(),
                "end_date": (week_start + timedelta(days=6)).isoformat(),
                "p1": "Smoke priority",
                "p2": None,
                "p3": None,
                "actor_username": actor,
            },
        )
        results.append(_expect(st, {201}, "create_weekly_plan", pl))

    # alignments
    edge_id = 0
    if goal_id:
        st, pl = client.request(
            "POST",
            "/v1/nodes/objective",
            {"goal_id": goal_id, "title": f"Smoke Obj2 {sfx}", "description": "smoke", "actor_username": actor},
        )
        results.append(_expect(st, {201}, "create_objective_2", pl))
        objective2_id = int((pl or {}).get("id") or 0) if st == 201 else 0
        if objective_id and objective2_id:
            st, pl = client.request(
                "POST",
                "/v1/alignments",
                {
                    "parent_id": objective_id,
                    "child_id": objective2_id,
                    "alignment_type": "SUPPORTS",
                    "actor_username": actor,
                },
            )
            results.append(_expect(st, {201}, "create_alignment", pl))
            edge_id = int((pl or {}).get("id") or 0) if st == 201 else 0

    if edge_id:
        st, pl = client.request("DELETE", f"/v1/alignments/{edge_id}")
        results.append(_expect(st, {200}, "delete_alignment", pl))

    # cleanup nodes and admin entities
    for node_type, node_id in (("TASK", task_id), ("KEY_RESULT", kr_id), ("OBJECTIVE", objective_id), ("GOAL", goal_id)):
        if node_id:
            st, pl = client.request("DELETE", f"/v1/nodes/{node_type}/{node_id}")
            results.append(_expect(st, {200}, f"delete_{node_type.lower()}", pl))
    if team_id:
        st, pl = client.request("DELETE", f"/v1/teams/{team_id}")
        results.append(_expect(st, {200}, "delete_team", pl))
    if cycle_id:
        st, pl = client.request("DELETE", f"/v1/cycles/{cycle_id}")
        results.append(_expect(st, {200}, "delete_cycle", pl))

    # output
    failed = [r for r in results if not r.ok]
    for r in results:
        print(f"[{'PASS' if r.ok else 'FAIL'}] {r.name} :: {r.detail}")
    print(f"\nSummary: {len(results) - len(failed)}/{len(results)} passed")
    if failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

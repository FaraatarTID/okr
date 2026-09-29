"""supabase_api mode is frozen: no new read kinds and no new mutation functions.

`supabase_api` (HTTPS to Supabase) is an alpha/on-premise compatibility mode, not the SaaS
target (docs/runtime-entrypoint-contract.md). Every capability added to it has to be written
twice, once for the database path and once for HTTPS, and the two have already diverged. This
test pins what exists today. It fails on an ADDITION, so new work cannot quietly extend the
mode, and on a REMOVAL, so the baseline ratchets down as the mode is retired. See
docs/supabase-api-freeze.md for the rule and how to change the baseline on purpose.

The inventory is read from the source with `ast`, not by importing it, so it cannot be
satisfied by a mock and does not depend on configuration.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads(
    (ROOT / "tests" / "supabase_api_freeze_baseline.json").read_text(encoding="utf-8")
)
SERVICES = ROOT / "src" / "services"
READ_MODULE = SERVICES / "supabase_api_mode_read.py"
READ_HELPERS = ROOT / "backend_app" / "read_query_helpers.py"
SUFFIX = "_via_supabase_api"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def current_functions() -> set[str]:
    """Every `*_via_supabase_api` function defined, or aliased by assignment, in the mode."""
    names: set[str] = set()
    for path in sorted(SERVICES.glob("supabase_api_mode*.py")):
        for node in _parse(path).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.endswith(SUFFIX):
                    names.add(node.name)
            elif isinstance(node, ast.Assign):
                names.update(
                    t.id
                    for t in node.targets
                    if isinstance(t, ast.Name) and t.id.endswith(SUFFIX)
                )
    return names


def _string_constants(node: ast.AST) -> set[str]:
    return {
        c.value
        for c in ast.walk(node)
        if isinstance(c, ast.Constant) and isinstance(c.value, str)
    }


def current_read_kinds() -> set[str]:
    """Kinds `read_query_via_supabase_api` compares `kind` against.

    Handles `==` and `in {...}` on the normalised kind, the two shapes the dispatcher uses.
    """
    kinds: set[str] = set()
    for node in ast.walk(_parse(READ_MODULE)):
        if (
            isinstance(node, ast.Compare)
            and isinstance(node.left, ast.Name)
            and node.left.id == "normalized"
        ):
            for comparator in node.comparators:
                kinds |= _string_constants(comparator)
    return kinds


def helper_kinds() -> set[str]:
    """Kinds named in the routing tables of `backend_app/read_query_helpers.py`.

    A second, independent source, so a kind added only to the routing tables (or only to
    the transport) is still seen.
    """
    return {
        s
        for s in _string_constants(_parse(READ_HELPERS))
        if s.count(".") == 1
        and s.replace(".", "").replace("_", "").isalpha()
        and s.islower()
    }


def _diff(kind: str, current: set[str], baseline: set[str]) -> str:
    added, removed = sorted(current - baseline), sorted(baseline - current)
    return (
        f"{kind}: added={added} removed={removed}. supabase_api mode is frozen; see "
        "docs/supabase-api-freeze.md. If this is a deliberate retirement, delete the entry "
        "from tests/supabase_api_freeze_baseline.json in the same change."
    )


def test_no_new_supabase_api_functions() -> None:
    current, baseline = current_functions(), set(BASELINE["functions"])
    assert current == baseline, _diff("functions", current, baseline)


def test_no_new_supabase_api_read_kinds() -> None:
    current, baseline = current_read_kinds(), set(BASELINE["read_kinds"])
    assert current == baseline, _diff("read kinds", current, baseline)


def test_the_routing_tables_add_no_kind_the_transport_lacks() -> None:
    unknown = helper_kinds() - set(BASELINE["read_kinds"])
    assert not unknown, (
        f"read_query_helpers.py names kinds outside the frozen set: {sorted(unknown)}. "
        "See docs/supabase-api-freeze.md."
    )


def test_the_inventory_is_not_vacuous() -> None:
    """A scanner that finds nothing would 'freeze' nothing, so pin that it sees the mode."""
    assert len(current_functions()) >= 30
    assert len(current_read_kinds()) >= 20
    assert "ritual.snapshot" in current_read_kinds()
    assert "create_check_in_via_supabase_api" in current_functions()

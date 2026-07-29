import re
from pathlib import Path
from fastapi.routing import APIRoute


def _load_allowlist_entries() -> list[tuple[str, str, str]]:
    project_root = Path(__file__).resolve().parents[1]
    allowlist_file = project_root / "spa-bff" / "src" / "allowlist.ts"
    text = allowlist_file.read_text(encoding="utf-8")
    policy_block = text.split("const ACTOR_OPTIONAL_POLICY_ROUTES", 1)[0]

    path_re = re.compile(r'pathTemplate:\s*"([^"]+)"')
    methods_re = re.compile(r'\"(GET|POST|PUT|PATCH|DELETE)\"')
    regex_re = re.compile(r'pathRegex:\s*/\^([^\$]+)\$/')

    template_matches = list(path_re.finditer(policy_block))
    entries: list[tuple[str, str, str]] = []
    for idx, template_match in enumerate(template_matches):
        block_start = template_match.start()
        block_end = template_matches[idx + 1].start() if idx + 1 < len(template_matches) else len(
            policy_block
        )
        block_text = policy_block[block_start:block_end]
        path_template = template_match.group(1)
        methods_match = methods_re.findall(block_text)
        regex_match = regex_re.search(block_text)
        if not (methods_match and regex_match):
            continue
        regex = regex_match.group(1)
        for method in methods_match:
            entries.append((method, path_template, regex))

    return entries


def _normalize_template_path(path_template: str) -> str:
    replacements = {
        "{create_type}": "goal",
        "{node_type}": "task",
        "{node_id:int}": "11",
        "{cycle_id:int}": "11",
        "{team_id:int}": "11",
        "{user_id:int}": "11",
        "{job_id}": "abc",
        "{job_id:int}": "11",
        "{key_id:int}": "11",
        "{retrospective_id:int}": "11",
        "{edge_id:int}": "11",
        "{link_id:int}": "11",
        "{work_log_id:int}": "11",
        "{key}": "sample-key",
        "{node_id}": "11",
        "{experiment_id:int}": "11",
        "{experiment_id}": "11",
        "{goal_id}": "11",
        "{objective_id}": "11",
        "{user_id}": "11",
        "{cycle_id}": "11",
        "{team_id}": "11",
        "{task_id}": "11",
    }
    sample_path = path_template
    for token, sample in replacements.items():
        sample_path = sample_path.replace(token, sample)
    sample_path = re.sub(r"{[^}]+}", "11", sample_path)
    return sample_path


def _iter_api_routes(routes):
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
            continue
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            yield from _iter_api_routes(getattr(original_router, "routes", []))


def _backend_mutating_routes() -> set[tuple[str, str]]:
    import backend_app.main as backend_main

    routes: set[tuple[str, str]] = set()
    for route in _iter_api_routes(backend_main.app.routes):
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or set():
            if method in {"POST", "PUT", "PATCH", "DELETE"}:
                routes.add((method, route.path))
    return routes


def _normalize_mutation_signature(route: tuple[str, str]) -> tuple[str, str]:
    method, path = route
    normalized = re.sub(r"^/v1/nodes/(goal|objective|key_result|task)$", r"/v1/nodes/{create_type}", path)
    normalized = re.sub(r"{[^}]+}", "{param}", normalized)
    normalized = re.sub(r"/\d+", "/{param}", normalized)
    return method, normalized


def test_allowlist_policy_entries_are_unique_and_well_formed():
    entries = _load_allowlist_entries()
    signatures = [(method, path) for method, path, _ in entries]
    assert len(signatures) == len(set(signatures)), "Allowlist has duplicate method/path signatures"

    for method, path_template, regex in entries:
        assert method in {"GET", "POST", "PUT", "PATCH", "DELETE"}
        assert path_template.startswith("/v1/")
        assert path_template == path_template.strip()
        compiled = re.compile(regex)
        sample_path = _normalize_template_path(path_template)
        assert compiled.fullmatch(sample_path), (
            f"Allowlist regex does not match template sample path: {path_template}"
        )


def test_mutation_allowlist_and_backend_mutation_routes_are_in_sync():
    entries = _load_allowlist_entries()
    allowlist_mutating = {
        (method, path) for method, path, _ in entries if method in {"POST", "PUT", "PATCH", "DELETE"}
    }
    backend_routes = _backend_mutating_routes()

    normalized_backend = {_normalize_mutation_signature(route) for route in backend_routes}
    normalized_allowlist = {
        _normalize_mutation_signature((method, path)) for method, path in allowlist_mutating
    }

    missing_in_allowlist = sorted(
        normalized_backend - normalized_allowlist
    )
    missing_in_backend = sorted(normalized_allowlist - normalized_backend)

    assert not missing_in_allowlist, (
        "Mutating backend routes missing from allowlist: "
        + ", ".join(f"{method} {path}" for method, path in missing_in_allowlist)
    )
    assert not missing_in_backend, (
        "Mutating allowlist entries not present as backend routes: "
        + ", ".join(f"{method} {path}" for method, path in missing_in_backend)
    )

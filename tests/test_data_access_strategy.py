from __future__ import annotations

import pytest

from src.services.data_access_strategy import (
    DataAccessError,
    DataAccessResult,
    DirectDatabaseStrategy,
    IDataAccessStrategy,
    SupabaseApiStrategy,
    strategy_for_mode,
)


def test_direct_database_adapter_normalizes_dispatch_result():
    calls = []

    def dispatch(operation, **kwargs):
        calls.append((operation, kwargs))
        return {"id": 7}

    strategy = DirectDatabaseStrategy(dispatch)

    result = strategy.execute("get_goal", goal_id=7)

    assert isinstance(strategy, IDataAccessStrategy)
    assert result == DataAccessResult(
        data={"id": 7}, strategy="database", operation="get_goal"
    )
    assert calls == [("get_goal", {"goal_id": 7})]
    assert strategy.supports_mutations is True


def test_supabase_adapter_preserves_operation_errors_with_metadata():
    def dispatch(operation, **kwargs):
        raise TimeoutError("API unavailable")

    strategy = SupabaseApiStrategy(dispatch)

    with pytest.raises(DataAccessError) as exc_info:
        strategy.execute("create_goal", title="New goal")

    error = exc_info.value
    assert error.strategy == "supabase_api"
    assert error.operation == "create_goal"
    assert error.code == "data_access_error"
    assert error.metadata == {"exception_type": "TimeoutError"}


@pytest.mark.parametrize(
    ("mode", "expected_name"),
    [("database", "database"), ("supabase_api", "supabase_api")],
)
def test_factory_gives_both_modes_the_same_contract(mode, expected_name):
    strategy = strategy_for_mode(
        mode,
        database_dispatcher=lambda operation, **kwargs: "database-result",
        supabase_api_dispatcher=lambda operation, **kwargs: "api-result",
    )

    result = strategy.execute("read")

    assert isinstance(strategy, IDataAccessStrategy)
    assert result.strategy == expected_name
    assert result.operation == "read"
    assert result.data.endswith("result")


def test_factory_rejects_unknown_mode():
    with pytest.raises(DataAccessError, match="Unsupported data-access mode"):
        strategy_for_mode(
            "unknown",
            database_dispatcher=lambda *_args, **_kwargs: None,
            supabase_api_dispatcher=lambda *_args, **_kwargs: None,
        )


def test_empty_operation_fails_before_dispatch():
    strategy = DirectDatabaseStrategy(lambda *_args, **_kwargs: pytest.fail())

    with pytest.raises(DataAccessError, match="Operation name is required") as exc_info:
        strategy.execute(" ")

    assert exc_info.value.code == "invalid_operation"
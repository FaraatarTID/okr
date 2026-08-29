"""Common contract for direct-database and Supabase API data access.

The adapters intentionally wrap existing operation dispatchers. This provides a
stable seam for request-scoped selection while legacy CRUD helpers continue to
keep their current signatures and behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Mapping, Protocol, runtime_checkable

StrategyName = Literal["database", "supabase_api"]


@dataclass(frozen=True)
class DataAccessResult:
    """Normalized outcome returned by a strategy operation."""

    data: Any = None
    strategy: StrategyName | str = ""
    operation: str = ""
    fallback_used: bool = False
    fallback_reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class DataAccessError(RuntimeError):
    """Operation failure with strategy and operation metadata for observability."""

    def __init__(
        self,
        message: str,
        *,
        strategy: StrategyName | str,
        operation: str,
        code: str = "data_access_error",
        fallback_reason: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.strategy = strategy
        self.operation = operation
        self.code = code
        self.fallback_reason = fallback_reason
        self.metadata = dict(metadata or {})


@runtime_checkable
class IDataAccessStrategy(Protocol):
    """Minimal contract shared by all data-access implementations."""

    name: str
    supports_mutations: bool

    def execute(self, operation: str, **kwargs: Any) -> DataAccessResult:
        """Execute a named operation and return normalized result metadata."""


OperationDispatcher = Callable[..., Any]


class CallableDataAccessStrategy:
    """Adapt an existing named-operation dispatcher to ``IDataAccessStrategy``."""

    def __init__(
        self,
        *,
        name: str,
        dispatcher: OperationDispatcher,
        supports_mutations: bool,
    ) -> None:
        self.name = name
        self._dispatcher = dispatcher
        self.supports_mutations = supports_mutations

    def execute(self, operation: str, **kwargs: Any) -> DataAccessResult:
        operation_name = str(operation).strip()
        if not operation_name:
            raise DataAccessError(
                "Operation name is required.",
                strategy=self.name,
                operation=operation_name,
                code="invalid_operation",
            )
        try:
            data = self._dispatcher(operation_name, **kwargs)
        except DataAccessError:
            raise
        except Exception as exc:
            raise DataAccessError(
                str(exc) or "Data-access operation failed.",
                strategy=self.name,
                operation=operation_name,
                metadata={"exception_type": type(exc).__name__},
            ) from exc
        return DataAccessResult(
            data=data,
            strategy=self.name,
            operation=operation_name,
        )


class DirectDatabaseStrategy(CallableDataAccessStrategy):
    """Adapter for the existing direct PostgreSQL/SQLModel dispatcher."""

    def __init__(self, dispatcher: OperationDispatcher) -> None:
        super().__init__(
            name="database",
            dispatcher=dispatcher,
            supports_mutations=True,
        )


class SupabaseApiStrategy(CallableDataAccessStrategy):
    """Adapter for the existing Supabase REST/RPC dispatcher."""

    def __init__(self, dispatcher: OperationDispatcher) -> None:
        super().__init__(
            name="supabase_api",
            dispatcher=dispatcher,
            supports_mutations=True,
        )


def strategy_for_mode(
    mode: str,
    *,
    database_dispatcher: OperationDispatcher,
    supabase_api_dispatcher: OperationDispatcher,
) -> IDataAccessStrategy:
    """Build the adapter for an already-resolved mode.

    Mode resolution remains owned by ``backend_app.data_access_mode``. Keeping
    this factory independent of that module lets request-scoped selection adopt
    the contract later without coupling callers to resolver globals.
    """
    normalized_mode = str(mode).strip().lower()
    if normalized_mode == "database":
        return DirectDatabaseStrategy(database_dispatcher)
    if normalized_mode == "supabase_api":
        return SupabaseApiStrategy(supabase_api_dispatcher)
    raise DataAccessError(
        f"Unsupported data-access mode: {mode}",
        strategy=normalized_mode,
        operation="",
        code="unsupported_mode",
    )


__all__ = [
    "CallableDataAccessStrategy",
    "DataAccessError",
    "DataAccessResult",
    "DirectDatabaseStrategy",
    "IDataAccessStrategy",
    "StrategyName",
    "SupabaseApiStrategy",
    "strategy_for_mode",
]
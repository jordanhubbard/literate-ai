"""Local SDK lifecycle joins; serialized invocation records remain only DATA."""

import inspect
from concurrent.futures import Future
from contextvars import ContextVar
from typing import Protocol

from literate_ai.contracts import ContentIdentity


class NodeSDKLifecycleAdmission(Protocol):
    """Explicit trusted-host port; no default, remote or checkpoint admission.

    The adapter retains original provider/oracle custody and separately granted
    verification. These methods supply no model, build or worker permission.
    """

    def with_invocation(
        self, execution_plan, prepared, receipts, *, consume, expected=None
    ): ...

    def require_build_intent(
        self,
        invocation,
        execution_plan,
        prepared,
        candidate,
        providers,
        packages,
        intent,
    ): ...


_CURRENT = ContextVar("standard_local_node_sdk_operation", default=None)


def is_node_sdk(prepared):
    surface = getattr(prepared.recipe, "library_import_surface", None)
    return bool(
        getattr(surface, "node_sdk_exports", ())
        or getattr(prepared.recipe, "node_sdk_providers", ())
    )


class _Scope:
    def __init__(self, execution_plan, invocation, require_current, require_intent):
        self.execution = execution_plan.identity
        self.invocation = invocation
        self.invocation_identity = invocation.identity
        self.prepared = invocation.prepared
        self.recipe = self.prepared.recipe.identity
        self.manifest = self.prepared.request.request.context_manifest_identity
        self.owner = require_current
        self.require_intent = require_intent
        self.active = True

    def _values(self, execution_plan, prepared):
        if (
            not self.active
            or _CURRENT.get() is not self
            or execution_plan.identity != self.execution
            or self.invocation.identity != self.invocation_identity
            or prepared.plan != self.prepared.plan
            or prepared.recipe.identity != self.recipe
            or prepared.request.request.context_manifest_identity != self.manifest
            or not is_node_sdk(prepared)
        ):
            raise ValueError("SDK lifecycle requires its original live invocation")

    def guard(self):
        try:
            self._values_identity()
            returned = self.owner()
            if returned is not None:
                if inspect.iscoroutine(returned) or inspect.isgenerator(returned):
                    returned.close()
                raise TypeError("SDK lifecycle owner must return None synchronously")
            self._values_identity()
        except BaseException:
            self.active = False
            raise

    def _values_identity(self):
        if (
            not self.active
            or _CURRENT.get() is not self
            or self.invocation.identity != self.invocation_identity
            or self.prepared.recipe.identity != self.recipe
            or self.prepared.request.request.context_manifest_identity != self.manifest
        ):
            raise ValueError("SDK lifecycle operation ended or changed")

    def source(self, execution_plan, prepared):
        try:
            self.guard()
            self._values(execution_plan, prepared)
        except BaseException:
            self.active = False
            raise


def run_node_sdk_lifecycle(
    admission,
    execution_plan,
    prepared,
    receipts,
    operation,
    *,
    expected=None,
):
    """Ask the configured trusted host port to retain its original custody.

    There is no DATA/callback-only entry point. The explicit port must perform
    its full current provider/oracle/grant admission before invoking consume.
    """
    entered = False

    def consume(invocation, require_current):
        nonlocal entered
        if entered or _CURRENT.get() is not None:
            raise ValueError("SDK lifecycle consumer is nested or repeated")
        entered = True
        if (
            not isinstance(invocation.identity, ContentIdentity)
            or invocation.base_recipe.uri != prepared.recipe.identity
            or invocation.prepared.plan != prepared.plan
            or invocation.prepared.workspace != prepared.workspace
            or (expected is not None and invocation.identity != expected.identity)
        ):
            raise ValueError("SDK lifecycle invocation differs from original inputs")
        for callback in (require_current, admission.require_build_intent, operation):
            if not callable(callback) or any(
                inspect.iscoroutinefunction(target)
                or inspect.isasyncgenfunction(target)
                or inspect.isgeneratorfunction(target)
                for target in (callback, type(callback).__call__)
            ):
                raise TypeError("SDK lifecycle callbacks must be synchronous")
        scope = _Scope(
            execution_plan,
            invocation,
            require_current,
            admission.require_build_intent,
        )
        token = _CURRENT.set(scope)
        try:
            scope.source(execution_plan, invocation.prepared)
            result = operation(invocation, scope.guard)
            if (
                isinstance(result, Future)
                or inspect.isawaitable(result)
                or inspect.isgenerator(result)
                or inspect.isasyncgen(result)
            ):
                if inspect.iscoroutine(result) or inspect.isgenerator(result):
                    result.close()
                raise TypeError("SDK lifecycle operation must finish synchronously")
            scope.guard()
            return result
        finally:
            scope.active = False
            _CURRENT.reset(token)

    return admission.with_invocation(
        execution_plan,
        prepared,
        receipts,
        consume=consume,
        expected=expected,
    )


def require_node_sdk_source(execution_plan, prepared):
    """Return False without a live operation; DATA alone cannot open a gate."""
    scope = _CURRENT.get()
    if scope is None:
        return False
    scope.source(execution_plan, prepared)
    return True


def _capture_node_sdk_lifecycle():
    """Retain original guard/closing checks without running owner callbacks."""
    scope = _CURRENT.get()
    return None if scope is None else (scope.guard, scope._values_identity)


def capture_node_sdk_lifecycle():
    """Retain an existing operation across blocking publisher preparation."""
    captured = _capture_node_sdk_lifecycle()
    if captured is None:
        return None
    guard, _closing = captured
    guard()
    return guard


def consume_node_sdk_build(consumer, candidate, providers, operation):
    """Supply original bound facts within custody, never a build execution grant."""
    scope = _CURRENT.get()
    if scope is None:
        raise ValueError("SDK build requires original live invocation admission")

    def guard():
        try:
            scope.guard()
            invocation = scope.invocation
            if (
                consumer.component_revision
                != invocation.prepared.plan.component_revision
                or candidate.component_revision != consumer.component_revision
                or candidate.recipe_identity.uri != scope.recipe
                or dict(invocation.prepared.recipe.resolved_inputs).get(
                    "node_sdk_command_contract"
                )
                != consumer.identity.uri
                or tuple(sorted((p.identity for p in providers), key=lambda p: p.uri))
                != tuple(
                    sorted(
                        (
                            p.artifact.identity
                            for p in invocation.prepared.recipe.node_sdk_providers
                        ),
                        key=lambda p: p.uri,
                    )
                )
            ):
                raise ValueError("SDK build differs from its original source/providers")
        except BaseException:
            scope.active = False
            raise

    guard()
    result = operation(scope.invocation, guard)
    if (
        isinstance(result, Future)
        or inspect.isawaitable(result)
        or inspect.isgenerator(result)
        or inspect.isasyncgen(result)
    ):
        if inspect.iscoroutine(result) or inspect.isgenerator(result):
            result.close()
        scope.active = False
        raise TypeError("SDK build must complete synchronously")
    guard()
    return result


def require_node_sdk_build_intent(
    execution_plan, prepared, candidate, providers, packages, intent
):
    if not is_node_sdk(prepared):
        return
    scope = _CURRENT.get()
    if scope is None:
        raise ValueError("SDK build intent lacks its original live invocation")
    scope.source(execution_plan, prepared)
    try:
        returned = scope.require_intent(
            scope.invocation,
            execution_plan,
            prepared,
            candidate,
            providers,
            packages,
            intent,
        )
        if returned is not None:
            if inspect.iscoroutine(returned) or inspect.isgenerator(returned):
                returned.close()
            raise TypeError("SDK build admission must return None synchronously")
        scope.source(execution_plan, prepared)
    except BaseException:
        scope.active = False
        raise


def capture_node_sdk_finalization(execution_plan, invocation):
    """Capture an already-live exact invocation for blocking and finite closes.

    Neither callback opens an operation or grants execution. The first retains
    the full original owner; the second only closes original scope/identity after
    the caller's final potentially blocking reads and clock.
    """
    scope = _CURRENT.get()
    if scope is None:
        raise ValueError("SDK finalization lacks original invocation ownership")
    expected = invocation.identity
    execution = execution_plan.identity

    def close():
        try:
            scope._values_identity()
            if (
                execution_plan.identity != execution
                or scope.execution != execution
                or invocation.identity != expected
                or scope.invocation.identity != expected
            ):
                raise ValueError("SDK finalization invocation changed")
        except BaseException:
            scope.active = False
            raise

    scope.guard()
    scope._values(execution_plan, invocation.prepared)
    close()
    return scope.guard, close

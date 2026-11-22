"""Actual normal or terminal read inventories; these descriptions grant no writes."""

from __future__ import annotations

from dataclasses import dataclass

from .retained_layout_forest_observation import _record
from .retained_layout_recovery_roles import _CREATED_ROLES, _RecoveryRoleLease


def _fail(message):
    raise ValueError("layout.forest-control-inventory: " + message)


@dataclass(frozen=True, slots=True)
class _ControlInventory:
    issuer: object
    key: object
    seed: object
    git: object
    recovered: tuple
    incoming: object
    inventory: tuple
    missing: tuple


def control_inventory(value, owner):
    if type(owner) is not _RecoveryRoleLease:
        from .retained_layout_forest_terminal_replay import _terminal_inventory

        return _terminal_inventory(value, owner)
    owner._require_created()
    binding = _CREATED_ROLES[owner]
    value.ledger.charge_records(32, 4096)
    facts = _ControlInventory(
        owner,
        binding,
        binding[6],
        binding[7],
        binding[8],
        binding[9],
        binding[10],
        binding[0].missing,
    )
    close_control_inventory(value, owner, facts)
    return facts


def close_control_inventory(value, owner, facts):
    if type(owner) is not _RecoveryRoleLease:
        from .retained_layout_forest_terminal_replay import _close_terminal_inventory

        return _close_terminal_inventory(value, owner, facts)
    owner._require_created()
    binding = _CREATED_ROLES.get(owner)
    if (
        type(facts) is not _ControlInventory
        or facts.issuer is not owner
        or binding is None
        or facts.key is not binding
        or facts.seed is not binding[6]
        or facts.git is not binding[7]
        or facts.recovered is not binding[8]
        or facts.incoming is not binding[9]
        or facts.inventory is not binding[10]
        or facts.missing is not binding[0].missing
        or owner._pool is not value.pool
        or owner._seed.root != value.root
        or _record(value.owner, reading=True) is not value
    ):
        _fail("actual creating canonical inventory changed")


def require_control_inputs(value, owner, facts, *, initial=False):
    close_control_inventory(value, owner, facts)
    if type(owner) is _RecoveryRoleLease:
        if initial:
            owner.require_initial_inputs()
        else:
            owner.require_current()
    else:
        from .retained_layout_forest_terminal_replay import _require_terminal_inputs

        _require_terminal_inputs(value, owner, facts)
    close_control_inventory(value, owner, facts)

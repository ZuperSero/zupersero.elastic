# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+
"""Shared reconciliation for conventional named Elasticsearch resources."""

from __future__ import annotations

import copy
from typing import Any, Iterable, Mapping

from .elasticsearch import fail_api_error, sanitize_data


def _canonical(value: Any) -> Any:
    """Normalize API stringification of scalar settings for comparison."""
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    return value


def reconcile_named_resource(
    module: Any,
    service: Any,
    *,
    fields: Iterable[str],
    result_key: str,
    put_options: Mapping[str, Any] | None = None,
    required_on_create: Iterable[str] = (),
    required_one_on_create: Iterable[str] = (),
) -> None:
    """Reconcile a named JSON object exposed through get/put/delete methods."""
    name = module.params["name"]
    response, current = service.get(name)
    path = service.path(name)
    if response.status not in (200, 404):
        fail_api_error(
            module,
            operation=f"read {result_key.replace('_', ' ')}",
            path=path,
            response=response,
            success_codes=[200, 404],
        )
    state = module.params["state"]
    if state == "absent":
        diff = {"before": sanitize_data(current or {}), "after": {}}
        if current is None or module.check_mode:
            module.exit_json(
                changed=current is not None,
                **{result_key: current},
                status=response.status,
                diff=diff,
            )
        mutation = service.delete(name)
        if mutation.status not in (200, 204):
            fail_api_error(
                module,
                operation=f"delete {result_key.replace('_', ' ')}",
                path=path,
                response=mutation,
                success_codes=[200, 204],
            )
        module.exit_json(
            changed=True, **{result_key: current}, status=mutation.status, diff=diff
        )

    if current is None:
        missing = [
            field for field in required_on_create if module.params.get(field) is None
        ]
        if missing:
            module.fail_json(
                msg=f"{', '.join(missing)} required when creating {result_key.replace('_', ' ')}"
            )
        alternatives = tuple(required_one_on_create)
        if alternatives and not any(module.params.get(field) for field in alternatives):
            module.fail_json(
                msg=f"one of {' or '.join(alternatives)} is required when creating "
                f"{result_key.replace('_', ' ')}"
            )

    supplied = {
        field: copy.deepcopy(module.params[field])
        for field in fields
        if module.params.get(field) is not None
    }
    if current is None or module.params.get("replace", False):
        desired = supplied
    else:
        desired = {
            field: copy.deepcopy(current[field]) for field in fields if field in current
        }
        desired.update(supplied)
    current_managed = {
        field: copy.deepcopy(current[field])
        for field in fields
        if current and field in current
    }
    changed = current is None or _canonical(current_managed) != _canonical(desired)
    diff = {"before": sanitize_data(current_managed), "after": sanitize_data(desired)}
    if not changed or module.check_mode:
        module.exit_json(
            changed=changed,
            **{result_key: desired if changed else current},
            status=response.status,
            diff=diff,
        )
    mutation = service.put(name, desired, **dict(put_options or {}))
    if mutation.status not in (200, 201):
        fail_api_error(
            module,
            operation=f"write {result_key.replace('_', ' ')}",
            path=path,
            response=mutation,
            success_codes=[200, 201],
        )
    module.exit_json(
        changed=True, **{result_key: desired}, status=mutation.status, diff=diff
    )

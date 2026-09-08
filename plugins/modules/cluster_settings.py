# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+
from __future__ import annotations

DOCUMENTATION = r"""
---
module: cluster_settings
short_description: Manage Elasticsearch cluster settings
description:
  - Reconciles persistent and transient dynamic cluster settings.
  - Omitted settings are preserved unless I(replace=true).
version_added: "1.0.0"
author: [Zupersero (@zupersero)]
extends_documentation_fragment: [zupersero.elastic.elasticsearch]
options:
  persistent:
    description: Persistent dynamic settings in flat or nested form.
    type: dict
  transient:
    description: Transient dynamic settings in flat or nested form.
    type: dict
  replace:
    description: Clear settings omitted from the supplied dictionaries.
    type: bool
    default: false
"""
EXAMPLES = r"""
- name: Configure allocation awareness
  zupersero.elastic.cluster_settings:
    persistent:
      cluster.routing.allocation.awareness.attributes: zone
- name: Authoritatively clear all transient settings
  zupersero.elastic.cluster_settings:
    transient: {}
    replace: true
"""
RETURN = r"""
cluster_settings:
  description: Current or predicted managed cluster settings.
  returned: always
  type: dict
status:
  description: HTTP status code.
  returned: always
  type: int
diff:
  description: State before and after reconciliation.
  returned: always
  type: dict
"""

from typing import Any, Mapping  # noqa: E402

from ansible.module_utils.basic import AnsibleModule  # noqa: E402
from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch import (  # noqa: E402
    ElasticsearchClient,
    elasticsearch_argument_spec,
    elasticsearch_mutually_exclusive,
    elasticsearch_required_together,
    fail_api_error,
    sanitize_data,
)


def _flatten(value: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(item, Mapping):
            result.update(_flatten(item, path))
        else:
            if isinstance(item, bool):
                result[path] = str(item).lower()
            elif isinstance(item, (int, float)):
                result[path] = str(item)
            else:
                result[path] = item
    return result


def run_module(
    module: AnsibleModule, client: ElasticsearchClient | None = None
) -> None:
    client = client or ElasticsearchClient(module)
    response = client.cluster_settings.get()
    if response.status != 200 or not isinstance(response.data, Mapping):
        fail_api_error(
            module,
            operation="read cluster settings",
            path=client.cluster_settings.path,
            response=response,
            success_codes=[200],
        )
    current = {
        kind: _flatten(response.data.get(kind) or {})
        for kind in ("persistent", "transient")
    }
    desired = {kind: dict(current[kind]) for kind in current}
    payload: dict[str, dict[str, Any]] = {}
    for kind in ("persistent", "transient"):
        supplied = module.params.get(kind)
        if supplied is None:
            continue
        supplied_flat = _flatten(supplied)
        if module.params["replace"]:
            payload[kind] = {
                key: None for key in set(current[kind]) - set(supplied_flat)
            }
            desired[kind] = {}
        else:
            payload[kind] = {}
        payload[kind].update(supplied_flat)
        desired[kind].update(supplied_flat)
    changed = _flatten(current) != _flatten(desired)
    diff = {"before": sanitize_data(current), "after": sanitize_data(desired)}
    if not changed or module.check_mode:
        module.exit_json(
            changed=changed,
            cluster_settings=desired if changed else current,
            status=response.status,
            diff=diff,
        )
    mutation = client.cluster_settings.update(payload)
    if mutation.status != 200:
        fail_api_error(
            module,
            operation="update cluster settings",
            path=client.cluster_settings.path,
            response=mutation,
            success_codes=[200],
        )
    module.exit_json(
        changed=True, cluster_settings=desired, status=mutation.status, diff=diff
    )


def main() -> None:
    spec = elasticsearch_argument_spec()
    spec.pop("state")
    spec.update(
        persistent=dict(type="dict"),
        transient=dict(type="dict"),
        replace=dict(type="bool", default=False),
    )
    module = AnsibleModule(
        argument_spec=spec,
        required_one_of=[["persistent", "transient"]],
        required_together=elasticsearch_required_together(),
        mutually_exclusive=elasticsearch_mutually_exclusive(),
        supports_check_mode=True,
    )
    run_module(module)


if __name__ == "__main__":
    main()

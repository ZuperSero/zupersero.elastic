# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+
from __future__ import annotations

DOCUMENTATION = r"""
---
module: index_alias
short_description: Manage an Elasticsearch index alias
description:
  - Reconciles one alias and its complete set of index memberships.
version_added: "1.0.0"
author: [Zupersero (@zupersero)]
extends_documentation_fragment: [zupersero.elastic.elasticsearch]
options:
  name:
    description: Alias name.
    type: str
    required: true
  indices:
    description: Complete mapping of index names to alias options such as C(filter), C(routing), C(index_routing), C(search_routing), and C(is_write_index).
    type: dict
  state:
    description: Whether the alias should exist.
    type: str
    choices: [present, absent]
    default: present
"""
EXAMPLES = r"""
- name: Point an alias at two indices
  zupersero.elastic.index_alias:
    name: logs-current
    indices:
      logs-000001: {}
      logs-000002:
        is_write_index: true
- name: Remove an alias
  zupersero.elastic.index_alias:
    name: logs-current
    state: absent
"""
RETURN = r"""
alias:
  description: Current or predicted alias definition.
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

from ansible.module_utils.basic import AnsibleModule  # noqa: E402
from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch import (  # noqa: E402
    ElasticsearchClient,
    elasticsearch_argument_spec,
    elasticsearch_mutually_exclusive,
    elasticsearch_required_together,
    fail_api_error,
    sanitize_data,
)


def run_module(
    module: AnsibleModule, client: ElasticsearchClient | None = None
) -> None:
    client = client or ElasticsearchClient(module)
    name = module.params["name"]
    response, current = client.index_alias.get(name)
    if response.status not in (200, 404):
        fail_api_error(
            module,
            operation="read index alias",
            path=client.index_alias.path(name),
            response=response,
            success_codes=[200, 404],
        )
    desired = module.params.get("indices") or {}
    if module.params["state"] == "present" and not desired:
        module.fail_json(
            msg="indices must contain at least one index when state is present"
        )
    if module.params["state"] == "absent":
        desired = {}
    changed = current != desired
    diff = {"before": sanitize_data(current), "after": sanitize_data(desired)}
    if not changed or module.check_mode:
        module.exit_json(
            changed=changed,
            alias=desired if changed else current,
            status=response.status,
            diff=diff,
        )
    mutation = client.index_alias.update(name, current, desired)
    if mutation.status != 200:
        fail_api_error(
            module,
            operation="update index alias",
            path="_aliases",
            response=mutation,
            success_codes=[200],
        )
    module.exit_json(changed=True, alias=desired, status=mutation.status, diff=diff)


def main() -> None:
    spec = elasticsearch_argument_spec()
    spec.update(name=dict(type="str", required=True), indices=dict(type="dict"))
    module = AnsibleModule(
        argument_spec=spec,
        required_together=elasticsearch_required_together(),
        mutually_exclusive=elasticsearch_mutually_exclusive(),
        supports_check_mode=True,
    )
    run_module(module)


if __name__ == "__main__":
    main()

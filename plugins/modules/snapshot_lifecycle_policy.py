# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+
from __future__ import annotations
# ruff: noqa: E402

DOCUMENTATION = r"""
---
module: snapshot_lifecycle_policy
short_description: Manage an Elasticsearch snapshot lifecycle policy
description: [Creates, updates, or deletes an SLM policy.]
version_added: "1.0.0"
author: [Zupersero (@zupersero)]
extends_documentation_fragment: [zupersero.elastic.elasticsearch]
options:
  name: {description: Policy name., type: str, required: true}
  schedule: {description: Cron schedule., type: str}
  repository: {description: Registered snapshot repository name., type: str}
  snapshot_name: {description: Snapshot name expression., type: str}
  config: {description: Snapshot configuration., type: dict}
  retention: {description: Retention configuration., type: dict}
  replace: {description: Remove omitted writable fields., type: bool, default: false}
  state: {description: Whether the policy should exist., type: str, choices: [present, absent], default: present}
"""
EXAMPLES = r"""
- name: Create a daily snapshot policy
  zupersero.elastic.snapshot_lifecycle_policy:
    name: daily
    schedule: "0 30 1 * * ?"
    repository: backups
    snapshot_name: "<daily-{now/d}>"
    retention: {expire_after: 30d, min_count: 5, max_count: 50}
- name: Delete a policy
  zupersero.elastic.snapshot_lifecycle_policy: {name: daily, state: absent}
"""
RETURN = r"""
policy: {description: Current or predicted policy., returned: always, type: dict}
status: {description: HTTP status code., returned: always, type: int}
diff: {description: State before and after reconciliation., returned: always, type: dict}
"""

from ansible.module_utils.basic import AnsibleModule  # noqa: E402
from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch import (
    ElasticsearchClient,
    elasticsearch_argument_spec,
    elasticsearch_mutually_exclusive,
    elasticsearch_required_together,
)  # noqa: E402
from ansible_collections.zupersero.elastic.plugins.module_utils.resource import (
    reconcile_named_resource,
)  # noqa: E402


def run_module(
    module: AnsibleModule, client: ElasticsearchClient | None = None
) -> None:
    client = client or ElasticsearchClient(module)
    reconcile_named_resource(
        module,
        client.snapshot_lifecycle_policy,
        fields=("schedule", "repository", "snapshot_name", "config", "retention"),
        result_key="policy",
        required_on_create=("schedule", "repository", "snapshot_name"),
    )


def main() -> None:
    spec = elasticsearch_argument_spec()
    spec.update(
        name=dict(type="str", required=True),
        schedule=dict(type="str"),
        repository=dict(type="str"),
        snapshot_name=dict(type="str"),
        config=dict(type="dict"),
        retention=dict(type="dict"),
        replace=dict(type="bool", default=False),
    )
    module = AnsibleModule(
        argument_spec=spec,
        required_together=elasticsearch_required_together(),
        mutually_exclusive=elasticsearch_mutually_exclusive(),
        supports_check_mode=True,
    )
    run_module(module)


if __name__ == "__main__":
    main()

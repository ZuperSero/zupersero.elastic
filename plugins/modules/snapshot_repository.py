# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+
from __future__ import annotations
# ruff: noqa: E402

DOCUMENTATION = r"""
---
module: snapshot_repository
short_description: Manage an Elasticsearch snapshot repository
description: [Creates, updates, verifies, or deletes a snapshot repository.]
version_added: "1.0.0"
author: [Zupersero (@zupersero)]
extends_documentation_fragment: [zupersero.elastic.elasticsearch]
options:
  name: {description: Repository name., type: str, required: true}
  type: {description: Repository plugin type., type: str}
  settings: {description: Repository-specific settings. Mark the task C(no_log) when these contain secrets., type: dict}
  verify: {description: Verify the repository after registration., type: bool, default: true}
  replace: {description: Remove omitted writable fields., type: bool, default: false}
  state: {description: Whether the repository should exist., type: str, choices: [present, absent], default: present}
"""
EXAMPLES = r"""
- name: Register a filesystem repository
  zupersero.elastic.snapshot_repository:
    name: backups
    type: fs
    settings: {location: /mnt/backups, compress: true}
- name: Remove a repository
  zupersero.elastic.snapshot_repository: {name: backups, state: absent}
"""
RETURN = r"""
repository: {description: Current or predicted repository., returned: always, type: dict}
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
        client.snapshot_repository,
        fields=("type", "settings"),
        result_key="repository",
        put_options={"verify": module.params["verify"]},
        required_on_create=("type",),
    )


def main() -> None:
    spec = elasticsearch_argument_spec()
    spec.update(
        name=dict(type="str", required=True),
        type=dict(type="str"),
        settings=dict(type="dict"),
        verify=dict(type="bool", default=True),
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

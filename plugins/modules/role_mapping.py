# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+
from __future__ import annotations
# ruff: noqa: E402

DOCUMENTATION = r"""
---
module: role_mapping
short_description: Manage an Elasticsearch security role mapping
description: [Reconciles native role mappings used by external realms.]
version_added: "1.0.0"
author: [Zupersero (@zupersero)]
extends_documentation_fragment: [zupersero.elastic.elasticsearch]
options:
  name: {description: Role mapping name., type: str, required: true}
  enabled: {description: Whether the mapping is enabled., type: bool}
  roles: {description: Role names assigned by the mapping., type: list, elements: str}
  role_templates: {description: Mustache role templates assigned by the mapping., type: list, elements: dict}
  rules: {description: Elasticsearch role-mapping rules expression., type: dict}
  metadata: {description: Arbitrary mapping metadata., type: dict}
  replace: {description: Remove omitted writable fields., type: bool, default: false}
  state: {description: Whether the mapping should exist., type: str, choices: [present, absent], default: present}
"""
EXAMPLES = r"""
- name: Map an LDAP group
  zupersero.elastic.role_mapping:
    name: operations
    enabled: true
    roles: [monitoring_user]
    rules: {field: {groups: "cn=ops,dc=example,dc=com"}}
- name: Delete a mapping
  zupersero.elastic.role_mapping: {name: operations, state: absent}
"""
RETURN = r"""
role_mapping: {description: Current or predicted mapping., returned: always, type: dict}
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
        client.role_mapping,
        fields=("enabled", "roles", "role_templates", "rules", "metadata"),
        result_key="role_mapping",
        required_on_create=("rules",),
        required_one_on_create=("roles", "role_templates"),
    )


def main() -> None:
    spec = elasticsearch_argument_spec()
    spec.update(
        name=dict(type="str", required=True),
        enabled=dict(type="bool"),
        roles=dict(type="list", elements="str"),
        role_templates=dict(type="list", elements="dict"),
        rules=dict(type="dict"),
        metadata=dict(type="dict"),
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

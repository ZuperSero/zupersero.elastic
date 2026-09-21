# Copyright (c) 2025, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later
# pylint: disable=disallowed-name

from __future__ import annotations

DOCUMENTATION = r'''
---
module: user_role
short_description: Manage Elasticsearch security roles
description:
  - Create, update, or delete roles via the Elasticsearch C(_security/role) API.
  - Idempotently reconciles cluster, index, application, and run-as privileges along with metadata.
version_added: "1.0.0"
author:
  - Zupersero (@zupersero)
extends_documentation_fragment:
  - zupersero.elastic.elasticsearch
options:
  name:
    description:
      - Name of the role to manage.
    required: true
    type: str
  cluster:
    description:
      - Cluster privileges to assign.
    required: false
    type: list
    elements: str
  indices:
    description:
      - Index privilege assignments.
    required: false
    type: list
    elements: dict
    suboptions:
      names:
        description:
          - Index or index pattern names.
        required: true
        type: list
        elements: str
      privileges:
        description:
          - Privileges for the listed indices.
        required: true
        type: list
        elements: str
      field_security:
        description:
          - Field-level security settings.
        required: false
        type: dict
      query:
        description:
          - Document-level security query.
        required: false
        type: str
      allow_restricted_indices:
        description:
          - Whether to allow access to restricted indices.
        required: false
        type: bool
        default: false
  applications:
    description:
      - Application privilege assignments.
    required: false
    type: list
    elements: dict
    suboptions:
      application:
        description:
          - Application name.
        required: true
        type: str
      privileges:
        description:
          - Privileges for the application.
        required: true
        type: list
        elements: str
      resources:
        description:
          - Resource identifiers.
        required: true
        type: list
        elements: str
  run_as:
    description:
      - Users that can be impersonated via the run-as mechanism.
    required: false
    type: list
    elements: str
  metadata:
    description:
      - Arbitrary metadata to attach to the role.
    required: false
    type: dict
  transient_metadata:
    description:
      - Transient metadata such as the enabled flag.
    required: false
    type: dict
  global_privileges:
    description:
      - Global privileges definition.
    required: false
    type: dict
  state:
    description:
      - Whether the role should exist.
    choices: [ present, absent ]
    default: present
    type: str
notes:
  - Authentication uses I(api_key), I(bearer_token), or I(username)+I(password).
  - Check mode predicts creation, updates, and deletion without sending mutating requests.
'''

EXAMPLES = r'''
- name: Create a role with cluster and index privileges
  zupersero.elastic.user_role:
    url: http://localhost:9200
    username: elastic
    password: changeme
    name: data_reader
    cluster:
      - monitor
    indices:
      - names: ["logs-*"]
        privileges: ["read"]
        allow_restricted_indices: false

- name: Manage application privileges
  zupersero.elastic.user_role:
    url: http://localhost:9200
    username: elastic
    password: changeme
    name: kibana_reader
    applications:
      - application: kibana-.kibana
        privileges: ["read"]
        resources: ["*"]
    run_as:
      - analyst
    state: present

- name: Delete a role
  zupersero.elastic.user_role:
    url: http://localhost:9200
    username: elastic
    password: changeme
    name: old_role
    state: absent
'''

RETURN = r'''
role:
  description: The role object returned by Elasticsearch.
  returned: always
  type: dict
changed:
  description: Whether any change was made.
  returned: always
  type: bool
diff:
  description: Desired-field projection before and after reconciliation.
  returned: always
  type: dict
  contains:
    before:
      description: Current values for fields under management.
      type: dict
    after:
      description: Desired values for fields under management.
      type: dict
'''

from typing import Any  # noqa: E402

from ansible.module_utils.basic import AnsibleModule  # noqa: E402

from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch import (  # noqa: E402
    ElasticsearchClient,
    elasticsearch_argument_spec,
    elasticsearch_mutually_exclusive,
    elasticsearch_required_together,
    fail_api_error,
    sanitize_data,
)


def _desired_role(module: AnsibleModule) -> dict[str, Any]:
    """Build the sparse role fields explicitly set by this task."""
    desired: dict[str, Any] = {}
    for field in ("cluster", "indices", "applications", "run_as", "metadata", "transient_metadata"):
        if module.params.get(field) is not None:
            desired[field] = module.params[field]
    if module.params.get("global_privileges") is not None:
        desired["global"] = module.params["global_privileges"]
    return desired


def run_module(
    module: AnsibleModule,
    client: ElasticsearchClient | None = None,
) -> None:
    """Reconcile an Elasticsearch security role."""
    client = client or ElasticsearchClient(module)
    name = module.params["name"]
    state = module.params["state"]

    read_response, current = client.role.get(name)
    if read_response.status not in (200, 404):
        fail_api_error(
            module,
            operation="read role",
            path=client.role.path(name),
            response=read_response,
            success_codes=[200, 404],
        )

    if state == "absent":
        diff = {"before": sanitize_data(current or {}), "after": {}}
        if current is None:
            module.exit_json(changed=False, role=None, diff=diff)
        if module.check_mode:
            module.exit_json(changed=True, role=sanitize_data(current), diff=diff)
        response = client.role.delete(name)
        if response.status not in (200, 404):
            fail_api_error(
                module,
                operation="delete role",
                path=client.role.path(name),
                response=response,
                success_codes=[200, 404],
            )
        module.exit_json(changed=True, role=sanitize_data(current), diff=diff)

    desired = _desired_role(module)

    if current is None:
        predicted = client.role.payload(None, desired)
        predicted["name"] = name
        diff = {"before": {}, "after": sanitize_data(predicted)}
        if module.check_mode:
            module.exit_json(changed=True, role=sanitize_data(predicted), diff=diff)

        response = client.role.create_or_update(name, current=None, desired=desired)
        if response.status not in (200, 201):
            fail_api_error(
                module,
                operation="create role",
                path=client.role.path(name),
                response=response,
                success_codes=[200, 201],
            )
        _, current = client.role.get(name)
        module.exit_json(changed=True, role=sanitize_data(current), diff=diff)
        return

    changed, diff = client.role.compare(current, desired)

    if not changed:
        module.exit_json(changed=False, role=sanitize_data(current), diff=diff)

    if module.check_mode:
        predicted = client.role.payload(current, desired)
        predicted["name"] = name
        module.exit_json(changed=True, role=sanitize_data(predicted), diff=diff)

    response = client.role.create_or_update(name, current=current, desired=desired)
    if response.status not in (200, 201):
        fail_api_error(
            module,
            operation="update role",
            path=client.role.path(name),
            response=response,
            success_codes=[200, 201],
        )
    _, current = client.role.get(name)
    module.exit_json(changed=True, role=sanitize_data(current), diff=diff)


def main() -> None:
    argument_spec = elasticsearch_argument_spec()

    argument_spec.update(
        name=dict(type='str', required=True),
        cluster=dict(type='list', elements='str', required=False, default=None),
        indices=dict(
            type='list',
            elements='dict',
            required=False,
            default=None,
            options=dict(
                names=dict(type='list', elements='str', required=True),
                privileges=dict(type='list', elements='str', required=True),
                field_security=dict(type='dict', required=False, default=None),
                query=dict(type='str', required=False, default=None),
                allow_restricted_indices=dict(type='bool', required=False, default=False),
            ),
        ),
        applications=dict(
            type='list',
            elements='dict',
            required=False,
            default=None,
            options=dict(
                application=dict(type='str', required=True),
                privileges=dict(type='list', elements='str', required=True),
                resources=dict(type='list', elements='str', required=True),
            ),
        ),
        run_as=dict(type='list', elements='str', required=False, default=None),
        metadata=dict(type='dict', required=False, default=None),
        transient_metadata=dict(type='dict', required=False, default=None),
        global_privileges=dict(type='dict', required=False, default=None),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_together=elasticsearch_required_together(),
        mutually_exclusive=elasticsearch_mutually_exclusive(),
    )

    run_module(module)


if __name__ == '__main__':
    main()

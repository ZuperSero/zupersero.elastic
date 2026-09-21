# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

DOCUMENTATION = r"""
---
module: component_template
short_description: Manage an Elasticsearch component template
description:
  - Creates, reads, updates, and deletes an Elasticsearch component template.
  - Component templates provide reusable settings, mappings, and aliases to composable index templates.
  - Updates preserve fields omitted from the task, including unknown writable fields returned by Elasticsearch.
version_added: "1.0.0"
author:
  - Zupersero (@zupersero)
extends_documentation_fragment:
  - zupersero.elastic.elasticsearch
options:
  name:
    description:
      - Name of the component template to manage.
      - The name is URL-quoted as one path component.
    type: str
    required: true
  settings:
    description:
      - Index settings contributed by this component template.
      - The optional C(index) namespace and dotted setting names are accepted.
      - Existing settings omitted here are preserved.
    type: dict
  mappings:
    description:
      - Index mappings contributed by this component template.
      - Existing mapping fields omitted here are preserved.
    type: dict
  aliases:
    description:
      - Index or data-stream aliases contributed by this component template.
      - Existing aliases omitted here are preserved.
    type: dict
  version:
    description:
      - External version number used to manage the component template.
      - Elasticsearch does not generate or increment this value.
    type: int
  metadata:
    description:
      - User metadata stored as the Elasticsearch C(_meta) field.
      - Existing metadata keys omitted here are preserved.
    type: dict
  deprecated:
    description:
      - Whether Elasticsearch should mark the component template as deprecated.
    type: bool
  replace:
    description:
      - Whether an existing component template should be fully replaced.
      - By default, updates preserve existing fields omitted from the task.
      - When C(true), only the requested writable fields are sent.
      - Empty I(settings), I(mappings), I(aliases), or I(metadata) dictionaries clear existing values, and omitted optional top-level fields are removed.
    type: bool
    default: false
  state:
    description:
      - Whether the component template should exist.
    type: str
    choices: [present, absent]
    default: present
notes:
  - Changes affect only indices and data streams created after the component template is updated.
  - Supplying only I(name) and I(state=present) ensures that the component template exists and returns its current definition.
  - Use I(replace=true) only when the task declares the complete desired component-template state.
  - Check mode predicts creation, updates, and deletion without sending mutating requests.
"""

EXAMPLES = r"""
- name: Create a reusable mappings component
  zupersero.elastic.component_template:
    url: https://es.example.invalid:9200
    api_key: "{{ vault_elasticsearch_api_key }}"
    name: application-mappings
    mappings:
      properties:
        event_id:
          type: keyword
        occurred_at:
          type: date
    version: 1
    metadata:
      owner: platform

- name: Add a dynamic setting and mapped field
  zupersero.elastic.component_template:
    name: application-mappings
    settings:
      refresh_interval: 5s
    mappings:
      properties:
        environment:
          type: keyword

- name: Read a component template using environment authentication
  zupersero.elastic.component_template:
    name: application-mappings
  register: application_component

- name: Replace a component template and clear aliases and metadata
  zupersero.elastic.component_template:
    name: application-mappings
    replace: true
    settings:
      number_of_replicas: 1
    mappings:
      properties:
        event_id:
          type: keyword
    aliases: {}
    metadata: {}

- name: Delete a component template
  zupersero.elastic.component_template:
    name: obsolete-component
    state: absent
"""

RETURN = r"""
component_template:
  description:
    - Current component-template definition returned by Elasticsearch after reconciliation.
    - In update check mode, this is the predicted definition.
    - For deletion, this is the last observed definition. It is C(null) when already absent.
  returned: always
  type: dict
  sample:
    name: application-mappings
    template:
      mappings:
        properties:
          event_id:
            type: keyword
    version: 1
    _meta:
      owner: platform
status:
  description: HTTP status of the mutation, or current-state read when unchanged or in check mode.
  returned: always
  type: int
  sample: 200
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
"""

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


def _desired_component_template(module: AnsibleModule) -> dict[str, Any]:
    """Build the user-managed component-template view."""
    desired: dict[str, Any] = {
        "name": module.params["name"],
        "template": {},
    }
    for field in ("settings", "mappings", "aliases"):
        if module.params.get(field) is not None:
            desired["template"][field] = module.params[field]
    if module.params.get("version") is not None:
        desired["version"] = module.params["version"]
    if module.params.get("metadata") is not None:
        desired["_meta"] = module.params["metadata"]
    if module.params.get("deprecated") is not None:
        desired["deprecated"] = module.params["deprecated"]
    return desired


def _read_managed_template(
    module: AnsibleModule,
    client: ElasticsearchClient,
    name: str,
) -> tuple[Any, dict[str, Any] | None]:
    """Read a component template or fail with sanitized API context."""
    response, current = client.component_template.get(name)
    path = client.component_template.path(name)
    if response.status not in (200, 404):
        fail_api_error(
            module,
            operation="read component template",
            path=path,
            response=response,
            success_codes=[200, 404],
        )
    if response.status == 200 and current is None:
        module.fail_json(
            msg=(
                f"Elasticsearch read component template request to {path!r} "
                f"returned HTTP {response.status} with no matching template definition"
            ),
            status=response.status,
            response=sanitize_data(response.data),
        )
    return response, current


def _predicted_template(
    client: ElasticsearchClient,
    current: dict[str, Any] | None,
    desired: dict[str, Any],
    *,
    replace: bool,
) -> dict[str, Any]:
    predicted = client.component_template.payload(
        current,
        desired,
        replace=replace,
    )
    predicted["name"] = desired["name"]
    return predicted


def run_module(
    module: AnsibleModule,
    client: ElasticsearchClient | None = None,
) -> None:
    """Reconcile an Elasticsearch component template."""
    client = client or ElasticsearchClient(module)
    name = module.params["name"]
    desired = _desired_component_template(module)
    replace = module.params["replace"]
    read_response, current = _read_managed_template(module, client, name)

    if module.params["state"] == "absent":
        diff = {"before": sanitize_data(current or {}), "after": {}}
        if current is None:
            module.exit_json(
                changed=False,
                component_template=None,
                status=read_response.status,
                diff=diff,
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                component_template=sanitize_data(current),
                status=read_response.status,
                diff=diff,
            )
        response = client.component_template.delete(name)
        if response.status != 200:
            fail_api_error(
                module,
                operation="delete component template",
                path=client.component_template.path(name),
                response=response,
                success_codes=[200],
            )
        module.exit_json(
            changed=True,
            component_template=sanitize_data(current),
            status=response.status,
            diff=diff,
        )

    if current is None:
        diff = {"before": {}, "after": sanitize_data(desired)}
        if module.check_mode:
            module.exit_json(
                changed=True,
                component_template=sanitize_data(desired),
                status=read_response.status,
                diff=diff,
            )
        response = client.component_template.create_or_update(
            name,
            current=None,
            desired=desired,
            replace=replace,
        )
        if response.status != 200:
            fail_api_error(
                module,
                operation="create component template",
                path=client.component_template.path(name),
                response=response,
                success_codes=[200],
            )
        managed = _read_managed_template(module, client, name)[1]
        module.exit_json(
            changed=True,
            component_template=sanitize_data(managed),
            status=response.status,
            diff=diff,
        )

    changed, diff = client.component_template.compare(
        current,
        desired,
        replace=replace,
    )
    if not changed:
        module.exit_json(
            changed=False,
            component_template=sanitize_data(current),
            status=read_response.status,
            diff=diff,
        )
    if module.check_mode:
        module.exit_json(
            changed=True,
            component_template=sanitize_data(
                _predicted_template(
                    client,
                    current,
                    desired,
                    replace=replace,
                )
            ),
            status=read_response.status,
            diff=diff,
        )

    response = client.component_template.create_or_update(
        name,
        current=current,
        desired=desired,
        replace=replace,
    )
    if response.status != 200:
        fail_api_error(
            module,
            operation="update component template",
            path=client.component_template.path(name),
            response=response,
            success_codes=[200],
        )
    managed = _read_managed_template(module, client, name)[1]
    module.exit_json(
        changed=True,
        component_template=sanitize_data(managed),
        status=response.status,
        diff=diff,
    )


def component_template_argument_spec() -> dict[str, dict[str, Any]]:
    """Return the component-template module argument specification."""
    argument_spec = elasticsearch_argument_spec()
    argument_spec.update(
        name=dict(type="str", required=True),
        settings=dict(type="dict"),
        mappings=dict(type="dict"),
        aliases=dict(type="dict"),
        version=dict(type="int"),
        metadata=dict(type="dict"),
        deprecated=dict(type="bool"),
        replace=dict(type="bool", default=False),
    )
    return argument_spec


def main() -> None:
    module = AnsibleModule(
        argument_spec=component_template_argument_spec(),
        required_together=elasticsearch_required_together(),
        mutually_exclusive=elasticsearch_mutually_exclusive(),
        supports_check_mode=True,
    )
    run_module(module)


if __name__ == "__main__":
    main()

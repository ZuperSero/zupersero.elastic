# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

DOCUMENTATION = r"""
---
module: index
short_description: Manage an Elasticsearch index
description:
  - Creates, reads, updates, and deletes an Elasticsearch index.
  - Existing mappings are extended through the update-mapping API.
  - Only changed dynamic settings are sent through the update-settings API.
  - Unknown and server-managed settings and mapping fields are preserved.
version_added: "1.0.0"
author:
  - Zupersero (@zupersero)
extends_documentation_fragment:
  - zupersero.elastic.elasticsearch
options:
  name:
    description:
      - Name of the index to manage.
      - The name is URL-quoted as one path component.
    type: str
    required: true
  settings:
    description:
      - Index settings used when creating the index.
      - On an existing index, only settings whose desired values differ are updated.
      - Elasticsearch rejects updates to static settings such as C(number_of_shards).
      - The optional C(index) namespace and dotted setting names are accepted.
    type: dict
  mappings:
    description:
      - Index mappings used when creating the index.
      - On an existing index, the mapping is merged through the update-mapping API.
      - Existing fields omitted here are preserved; Elasticsearch does not allow incompatible field type changes.
    type: dict
  state:
    description:
      - Whether the index should exist.
    type: str
    choices: [present, absent]
    default: present
notes:
  - Deleting an index permanently deletes its documents.
  - Supplying only I(name) and I(state=present) ensures that the index exists and returns its current definition.
  - Check mode predicts creation, settings and mapping updates, and deletion without sending mutating requests.
"""

EXAMPLES = r"""
- name: Create an index
  zupersero.elastic.index:
    url: https://es.example.invalid:9200
    api_key: "{{ vault_elasticsearch_api_key }}"
    name: application-events
    settings:
      number_of_shards: 1
      number_of_replicas: 1
    mappings:
      properties:
        event_id:
          type: keyword
        occurred_at:
          type: date

- name: Update a dynamic setting and add a mapped field
  zupersero.elastic.index:
    name: application-events
    settings:
      refresh_interval: 5s
    mappings:
      properties:
        environment:
          type: keyword

- name: Read an existing index using environment authentication
  zupersero.elastic.index:
    name: application-events
  register: application_events_index

- name: Delete an index
  zupersero.elastic.index:
    name: obsolete-events
    state: absent
"""

RETURN = r"""
index:
  description:
    - The index definition returned by Elasticsearch after reconciliation.
    - For deletion, this is the last observed definition. It is C(null) when the index was already absent.
  returned: always
  type: dict
  sample:
    name: application-events
    settings:
      index:
        number_of_shards: "1"
        number_of_replicas: "1"
    mappings:
      properties:
        event_id:
          type: keyword
    aliases: {}
status:
  description: HTTP status of the mutation, or the current-state read when unchanged or in check mode.
  returned: always
  type: int
  sample: 200
diff:
  description: Desired-field projection before and after reconciliation.
  returned: always
  type: dict
  contains:
    before:
      description: Current values for the fields under management.
      type: dict
    after:
      description: Desired values for the fields under management.
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


def _desired_index(module: AnsibleModule) -> dict[str, Any]:
    """Build the user-managed view of the index."""
    desired: dict[str, Any] = {"name": module.params["name"]}
    if module.params.get("settings") is not None:
        desired["settings"] = module.params["settings"]
    if module.params.get("mappings") is not None:
        desired["mappings"] = module.params["mappings"]
    return desired


def _fail_malformed_read(
    module: AnsibleModule,
    *,
    name: str,
    status: int,
    response: Any,
) -> None:
    module.fail_json(
        msg=(
            f"Elasticsearch read index request for {name!r} returned HTTP "
            f"{status} with no matching index definition"
        ),
        status=status,
        response=sanitize_data(response),
    )


def _read_managed_index(
    module: AnsibleModule,
    client: ElasticsearchClient,
    name: str,
) -> tuple[Any, dict[str, Any] | None]:
    response, current = client.index.get(name)
    if response.status not in (200, 404):
        fail_api_error(
            module,
            operation="read index",
            path=client.index.path(name),
            response=response,
            success_codes=[200, 404],
        )
    if response.status == 200 and current is None:
        _fail_malformed_read(
            module,
            name=name,
            status=response.status,
            response=response.data,
        )
    return response, current


def run_module(
    module: AnsibleModule,
    client: ElasticsearchClient | None = None,
) -> None:
    """Reconcile an Elasticsearch index."""
    client = client or ElasticsearchClient(module)
    name = module.params["name"]
    desired = _desired_index(module)
    read_response, current = _read_managed_index(module, client, name)
    exists = current is not None

    if module.params["state"] == "absent":
        diff = {
            "before": sanitize_data(current or {}),
            "after": {},
        }
        if not exists:
            module.exit_json(
                changed=False,
                index=None,
                status=read_response.status,
                diff=diff,
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                index=sanitize_data(current),
                status=read_response.status,
                diff=diff,
            )
        response = client.index.delete(name)
        if response.status != 200:
            fail_api_error(
                module,
                operation="delete index",
                path=client.index.path(name),
                response=response,
                success_codes=[200],
            )
        module.exit_json(
            changed=True,
            index=sanitize_data(current),
            status=response.status,
            diff=diff,
        )

    if not exists:
        diff = {"before": {}, "after": sanitize_data(desired)}
        if module.check_mode:
            module.exit_json(
                changed=True,
                index=sanitize_data(desired),
                status=read_response.status,
                diff=diff,
            )
        response = client.index.create(
            name,
            settings=module.params.get("settings"),
            mappings=module.params.get("mappings"),
        )
        if response.status not in (200, 201):
            fail_api_error(
                module,
                operation="create index",
                path=client.index.path(name),
                response=response,
                success_codes=[200, 201],
            )
        managed = _read_managed_index(module, client, name)[1]
        module.exit_json(
            changed=True,
            index=sanitize_data(managed),
            status=response.status,
            diff=diff,
        )

    before: dict[str, Any] = {"name": name}
    after: dict[str, Any] = {"name": name}
    settings_changed = False
    settings_update: dict[str, Any] = {}
    mappings_changed = False

    if module.params.get("settings") is not None:
        settings_changed, settings_diff, settings_update = client.index.compare_settings(
            current.get("settings"),
            module.params["settings"],
        )
        before["settings"] = settings_diff["before"]
        after["settings"] = settings_diff["after"]
    if module.params.get("mappings") is not None:
        mappings_changed, mappings_diff = client.index.compare_mappings(
            current.get("mappings"),
            module.params["mappings"],
        )
        before["mappings"] = mappings_diff["before"]
        after["mappings"] = mappings_diff["after"]

    changed = settings_changed or mappings_changed
    diff = {"before": sanitize_data(before), "after": sanitize_data(after)}
    if not changed:
        module.exit_json(
            changed=False,
            index=sanitize_data(current),
            status=read_response.status,
            diff=diff,
        )
    if module.check_mode:
        module.exit_json(
            changed=True,
            index=sanitize_data(desired),
            status=read_response.status,
            diff=diff,
        )

    mutation_status = read_response.status
    if settings_changed:
        response = client.index.update_settings(name, settings_update)
        mutation_status = response.status
        if response.status != 200:
            fail_api_error(
                module,
                operation="update index settings",
                path=client.index.settings_path(name),
                response=response,
                success_codes=[200],
            )
    if mappings_changed:
        response = client.index.update_mapping(name, module.params["mappings"])
        mutation_status = response.status
        if response.status != 200:
            fail_api_error(
                module,
                operation="update index mapping",
                path=client.index.mapping_path(name),
                response=response,
                success_codes=[200],
            )

    managed = _read_managed_index(module, client, name)[1]
    module.exit_json(
        changed=True,
        index=sanitize_data(managed),
        status=mutation_status,
        diff=diff,
    )


def index_argument_spec() -> dict[str, dict[str, Any]]:
    """Return the index module argument specification."""
    argument_spec = elasticsearch_argument_spec()
    argument_spec.update(
        name=dict(type="str", required=True),
        settings=dict(type="dict"),
        mappings=dict(type="dict"),
    )
    return argument_spec


def main() -> None:
    module = AnsibleModule(
        argument_spec=index_argument_spec(),
        required_together=elasticsearch_required_together(),
        mutually_exclusive=elasticsearch_mutually_exclusive(),
        supports_check_mode=True,
    )
    run_module(module)


if __name__ == "__main__":
    main()

# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

DOCUMENTATION = r"""
---
module: data_stream
short_description: Manage an Elasticsearch data stream
description:
  - Creates, reads, and deletes an Elasticsearch data stream.
  - Creation uses the matching composable index template, which must have data stream support enabled.
  - Data stream lifecycle attachment is managed separately with M(zupersero.elastic.data_stream_lifecycle).
version_added: "1.0.0"
author:
  - Zupersero (@zupersero)
extends_documentation_fragment:
  - zupersero.elastic.elasticsearch
options:
  name:
    description:
      - Name of the data stream to manage.
      - Elasticsearch validates data stream naming rules and the matching template.
      - The name is URL-quoted as one path component.
    type: str
    required: true
  state:
    description:
      - Whether the data stream and its backing indices should exist.
    type: str
    choices: [present, absent]
    default: present
notes:
  - Deleting a data stream also deletes its backing indices and stored data.
  - Check mode predicts creation and deletion without sending mutating requests.
  - Elasticsearch 7.9.0 or newer is required.
"""

EXAMPLES = r"""
- name: Create a data stream from a matching data stream template
  zupersero.elastic.data_stream:
    url: https://es.example.invalid:9200
    api_key: "{{ vault_elasticsearch_api_key }}"
    name: application-events

- name: Read an existing data stream using environment authentication
  zupersero.elastic.data_stream:
    name: application-events
  register: application_stream

- name: Delete a data stream and all of its backing indices
  zupersero.elastic.data_stream:
    name: obsolete-events
    state: absent
"""

RETURN = r"""
data_stream:
  description:
    - Current data stream returned by Elasticsearch after reconciliation.
    - In creation check mode, this contains the predicted name.
    - For deletion, this is the last observed stream. It is C(null) when already absent.
  returned: always
  type: dict
  sample:
    name: application-events
    timestamp_field:
      name: '@timestamp'
    indices:
      - index_name: .ds-application-events-2026.07.27-000001
        index_uuid: JLh7KzvVQbSzsYQ3sQavdA
        managed_by: Data stream lifecycle
        prefer_ilm: true
        index_mode: standard
    generation: 1
    status: GREEN
    template: application-events-template
    next_generation_managed_by: Data stream lifecycle
    prefer_ilm: true
    hidden: false
    system: false
    allow_custom_routing: false
    replicated: false
    rollover_on_write: false
status:
  description: HTTP status of the mutation, or current-state read when unchanged or in check mode.
  returned: always
  type: int
  sample: 200
diff:
  description: Data stream existence before and after reconciliation.
  returned: always
  type: dict
  contains:
    before:
      description: Last observed data stream, or an empty dictionary.
      type: dict
    after:
      description: Predicted existence state.
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


def _require_data_stream_api(
    module: AnsibleModule,
    client: ElasticsearchClient,
) -> None:
    """Fail before using an API unavailable on the target deployment."""
    if not client.supports_feature("data_stream"):
        module.fail_json(
            msg=(
                "data stream management requires Elasticsearch 7.9.0 or newer "
                "or an Elasticsearch Serverless deployment"
            )
        )


def _read_managed_data_stream(
    module: AnsibleModule,
    client: ElasticsearchClient,
    name: str,
) -> tuple[Any, dict[str, Any] | None]:
    """Read a data stream or fail with sanitized API context."""
    response, current = client.data_stream.get(name)
    path = client.data_stream.path(name)
    if response.status not in (200, 404):
        fail_api_error(
            module,
            operation="read data stream",
            path=path,
            response=response,
            success_codes=[200, 404],
        )
    if response.status == 200 and current is None:
        module.fail_json(
            msg=(
                f"Elasticsearch read data stream request to {path!r} returned "
                f"HTTP {response.status} with no matching data stream definition"
            ),
            status=response.status,
            response=sanitize_data(response.data),
        )
    return response, current


def run_module(
    module: AnsibleModule,
    client: ElasticsearchClient | None = None,
) -> None:
    """Reconcile Elasticsearch data stream existence."""
    client = client or ElasticsearchClient(module)
    _require_data_stream_api(module, client)
    name = module.params["name"]
    read_response, current = _read_managed_data_stream(module, client, name)

    if module.params["state"] == "absent":
        diff = {"before": sanitize_data(current or {}), "after": {}}
        if current is None:
            module.exit_json(
                changed=False,
                data_stream=None,
                status=read_response.status,
                diff=diff,
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                data_stream=sanitize_data(current),
                status=read_response.status,
                diff=diff,
            )
        response = client.data_stream.delete(name)
        if response.status != 200:
            fail_api_error(
                module,
                operation="delete data stream",
                path=client.data_stream.path(name),
                response=response,
                success_codes=[200],
            )
        module.exit_json(
            changed=True,
            data_stream=sanitize_data(current),
            status=response.status,
            diff=diff,
        )

    desired = {"name": name}
    if current is not None:
        diff = {
            "before": sanitize_data(desired),
            "after": sanitize_data(desired),
        }
        module.exit_json(
            changed=False,
            data_stream=sanitize_data(current),
            status=read_response.status,
            diff=diff,
        )

    diff = {"before": {}, "after": sanitize_data(desired)}
    if module.check_mode:
        module.exit_json(
            changed=True,
            data_stream=sanitize_data(desired),
            status=read_response.status,
            diff=diff,
        )
    response = client.data_stream.create(name)
    if response.status != 200:
        fail_api_error(
            module,
            operation="create data stream",
            path=client.data_stream.path(name),
            response=response,
            success_codes=[200],
        )
    refresh_response, managed = _read_managed_data_stream(module, client, name)
    if managed is None:
        module.fail_json(
            msg=(
                f"Elasticsearch reported successful data stream creation for "
                f"{name!r}, but the stream was not observable during refresh"
            ),
            status=refresh_response.status,
            mutation_status=response.status,
            response=sanitize_data(refresh_response.data),
        )
    module.exit_json(
        changed=True,
        data_stream=sanitize_data(managed),
        status=response.status,
        diff=diff,
    )


def data_stream_argument_spec() -> dict[str, dict[str, Any]]:
    """Return the data stream argument specification."""
    argument_spec = elasticsearch_argument_spec()
    argument_spec.update(name=dict(type="str", required=True))
    return argument_spec


def main() -> None:
    module = AnsibleModule(
        argument_spec=data_stream_argument_spec(),
        required_together=elasticsearch_required_together(),
        mutually_exclusive=elasticsearch_mutually_exclusive(),
        supports_check_mode=True,
    )
    run_module(module)


if __name__ == "__main__":
    main()

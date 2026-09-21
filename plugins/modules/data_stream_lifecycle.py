# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

DOCUMENTATION = r"""
---
module: data_stream_lifecycle
short_description: Manage lifecycle attachment on an Elasticsearch data stream
description:
  - Creates, reads, updates, and detaches data stream lifecycle configuration.
  - The data stream itself must already exist and is never deleted by this module.
  - Partial updates preserve omitted retention and downsampling configuration.
version_added: "1.0.0"
author:
  - Zupersero (@zupersero)
extends_documentation_fragment:
  - zupersero.elastic.elasticsearch
options:
  name:
    description:
      - Name of the existing data stream whose lifecycle attachment is managed.
      - The name is URL-quoted as one path component.
    type: str
    required: true
  enabled:
    description:
      - Whether the attached data stream lifecycle actively manages the stream.
      - Omitting this option preserves the current value during partial updates.
      - Elasticsearch defaults this value to C(true) for a new attachment.
    type: bool
  data_retention:
    description:
      - Minimum duration for which documents in the data stream are retained.
      - Elasticsearch validates the duration syntax and target-version constraints.
      - The effective value may be limited by cluster-level global retention.
      - Omit this option with I(replace=true) to clear a configured retention period.
    type: str
  downsampling:
    description:
      - Ordered downsampling rounds for backing indices after rollover.
      - Elasticsearch validates duration syntax, ordering, and version-specific constraints.
      - An empty list explicitly clears configured rounds during a partial update.
    type: list
    elements: dict
    suboptions:
      after:
        description:
          - Duration since rollover after which this round runs.
        type: str
        required: true
      fixed_interval:
        description:
          - Fixed interval used to downsample this round.
        type: str
        required: true
  replace:
    description:
      - Whether the lifecycle configuration is authoritative.
      - By default, updates preserve I(enabled), I(data_retention), and I(downsampling) when omitted.
      - When C(true), omitted retention and downsampling fields are removed.
      - Use replacement mode to clear I(data_retention), because Elasticsearch does not accept a null retention value.
    type: bool
    default: false
  state:
    description:
      - Whether data stream lifecycle is attached to the existing data stream.
      - C(absent) detaches lifecycle management without deleting the stream.
    type: str
    choices: [present, absent]
    default: present
notes:
  - A name-only C(present) task attaches the Elasticsearch default lifecycle when none exists and otherwise reads the attachment.
  - The returned effective retention and retention source are derived by Elasticsearch and are never sent in update requests.
  - Check mode predicts attachment, updates, replacement, and detachment without sending mutating requests.
  - Elasticsearch 8.11.0 or newer is required.
"""

EXAMPLES = r"""
- name: Attach retention and downsampling to a data stream
  zupersero.elastic.data_stream_lifecycle:
    url: https://es.example.invalid:9200
    api_key: "{{ vault_elasticsearch_api_key }}"
    name: application-events
    data_retention: 30d
    downsampling:
      - after: 7d
        fixed_interval: 1h
      - after: 30d
        fixed_interval: 1d

- name: Change retention while preserving downsampling
  zupersero.elastic.data_stream_lifecycle:
    name: application-events
    data_retention: 14d

- name: Clear retention and downsampling authoritatively
  zupersero.elastic.data_stream_lifecycle:
    name: application-events
    replace: true
    enabled: true

- name: Disable lifecycle without removing its configuration
  zupersero.elastic.data_stream_lifecycle:
    name: application-events
    enabled: false

- name: Detach lifecycle while keeping the data stream
  zupersero.elastic.data_stream_lifecycle:
    name: application-events
    state: absent
"""

RETURN = r"""
data_stream_lifecycle:
  description:
    - Current lifecycle attachment returned by Elasticsearch after reconciliation.
    - In check mode, this contains the predicted writable configuration without derived retention values.
    - It is C(null) when lifecycle is detached or was already absent.
  returned: always
  type: dict
  sample:
    name: application-events
    enabled: true
    data_retention: 30d
    effective_retention: 30d
    retention_determined_by: data_stream_configuration
    downsampling:
      - after: 7d
        fixed_interval: 1h
data_stream_exists:
  description: Whether the target data stream exists independently of lifecycle attachment.
  returned: always
  type: bool
  sample: true
global_retention:
  description:
    - Cluster-level data stream retention limits returned by Elasticsearch.
    - This is response-only state and is not managed by this module.
  returned: always
  type: dict
  sample:
    default_retention: 30d
    max_retention: 90d
status:
  description: HTTP status of the mutation, or current-state read when unchanged or in check mode.
  returned: always
  type: int
  sample: 200
diff:
  description: Writable lifecycle configuration before and after reconciliation.
  returned: always
  type: dict
  contains:
    before:
      description: Current values for lifecycle fields under management.
      type: dict
    after:
      description: Desired lifecycle values after preservation or replacement.
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


def _desired_lifecycle(module: AnsibleModule) -> dict[str, Any]:
    """Build the user-managed lifecycle view."""
    desired: dict[str, Any] = {"name": module.params["name"]}
    for field in ("enabled", "data_retention", "downsampling"):
        if module.params.get(field) is not None:
            desired[field] = module.params[field]
    return desired


def _require_lifecycle_api(
    module: AnsibleModule,
    client: ElasticsearchClient,
) -> None:
    """Fail before using an API unavailable on the target deployment."""
    if not client.supports_feature("data_stream_lifecycle"):
        module.fail_json(
            msg=(
                "data stream lifecycle management requires Elasticsearch "
                "8.11.0 or newer or an Elasticsearch Serverless deployment"
            )
        )


def _read_managed_lifecycle(
    module: AnsibleModule,
    client: ElasticsearchClient,
    name: str,
) -> tuple[Any, bool, dict[str, Any] | None, dict[str, Any]]:
    """Read lifecycle attachment or fail with sanitized API context."""
    response, stream_exists, current, global_retention = (
        client.data_stream_lifecycle.get(name)
    )
    path = client.data_stream_lifecycle.path(name)
    if response.status not in (200, 404):
        fail_api_error(
            module,
            operation="read data stream lifecycle",
            path=path,
            response=response,
            success_codes=[200, 404],
        )
    if response.status == 200 and not stream_exists:
        module.fail_json(
            msg=(
                f"Elasticsearch read data stream lifecycle request to {path!r} "
                f"returned HTTP {response.status} with no matching data stream"
            ),
            status=response.status,
            response=sanitize_data(response.data),
        )
    return response, stream_exists, current, global_retention


def _predicted_lifecycle(
    client: ElasticsearchClient,
    current: dict[str, Any] | None,
    desired: dict[str, Any],
    *,
    replace: bool,
) -> dict[str, Any]:
    predicted = client.data_stream_lifecycle.payload(
        current,
        desired,
        replace=replace,
    )
    predicted.setdefault("enabled", True)
    predicted["name"] = desired["name"]
    return predicted


def run_module(
    module: AnsibleModule,
    client: ElasticsearchClient | None = None,
) -> None:
    """Reconcile lifecycle attachment on an Elasticsearch data stream."""
    client = client or ElasticsearchClient(module)
    _require_lifecycle_api(module, client)
    name = module.params["name"]
    desired = _desired_lifecycle(module)
    replace = module.params["replace"]
    read_response, stream_exists, current, global_retention = (
        _read_managed_lifecycle(module, client, name)
    )

    if module.params["state"] == "absent":
        diff = {"before": sanitize_data(current or {}), "after": {}}
        if current is None:
            module.exit_json(
                changed=False,
                data_stream_lifecycle=None,
                data_stream_exists=stream_exists,
                global_retention=sanitize_data(global_retention),
                status=read_response.status,
                diff=diff,
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                data_stream_lifecycle=None,
                data_stream_exists=True,
                global_retention=sanitize_data(global_retention),
                status=read_response.status,
                diff=diff,
            )
        response = client.data_stream_lifecycle.delete(name)
        if response.status != 200:
            fail_api_error(
                module,
                operation="detach data stream lifecycle",
                path=client.data_stream_lifecycle.path(name),
                response=response,
                success_codes=[200],
            )
        refreshed = _read_managed_lifecycle(
            module,
            client,
            name,
        )
        if not refreshed[1]:
            module.fail_json(
                msg=(
                    "Elasticsearch reported successful data stream lifecycle "
                    f"detachment for {name!r}, but the data stream was not "
                    "observable during refresh"
                ),
                status=refreshed[0].status,
                mutation_status=response.status,
                response=sanitize_data(refreshed[0].data),
            )
        if refreshed[2] is not None:
            module.fail_json(
                msg=(
                    "Elasticsearch reported successful data stream lifecycle "
                    f"detachment for {name!r}, but the lifecycle attachment "
                    "remained observable during refresh"
                ),
                status=refreshed[0].status,
                mutation_status=response.status,
                response=sanitize_data(refreshed[0].data),
            )
        module.exit_json(
            changed=True,
            data_stream_lifecycle=None,
            data_stream_exists=True,
            global_retention=sanitize_data(refreshed[3]),
            status=response.status,
            diff=diff,
        )

    if not stream_exists:
        module.fail_json(
            msg=(
                f"data stream {name!r} does not exist; create it from a matching "
                "data stream index template before attaching lifecycle management"
            ),
            status=read_response.status,
        )

    if current is None:
        predicted = _predicted_lifecycle(
            client,
            None,
            desired,
            replace=replace,
        )
        diff = {"before": {}, "after": sanitize_data(predicted)}
        if module.check_mode:
            module.exit_json(
                changed=True,
                data_stream_lifecycle=sanitize_data(predicted),
                data_stream_exists=True,
                global_retention=sanitize_data(global_retention),
                status=read_response.status,
                diff=diff,
            )
        response = client.data_stream_lifecycle.create_or_update(
            name,
            current=None,
            desired=desired,
            replace=replace,
        )
        if response.status != 200:
            fail_api_error(
                module,
                operation="attach data stream lifecycle",
                path=client.data_stream_lifecycle.path(name),
                response=response,
                success_codes=[200],
            )
        refreshed = _read_managed_lifecycle(
            module,
            client,
            name,
        )
        managed = refreshed[2]
        refreshed_retention = refreshed[3]
        if managed is None:
            module.fail_json(
                msg=(
                    "Elasticsearch reported successful data stream lifecycle "
                    f"attachment for {name!r}, but no attachment was observable "
                    "during refresh"
                ),
                status=refreshed[0].status,
                mutation_status=response.status,
                response=sanitize_data(refreshed[0].data),
            )
        module.exit_json(
            changed=True,
            data_stream_lifecycle=sanitize_data(managed),
            data_stream_exists=True,
            global_retention=sanitize_data(refreshed_retention),
            status=response.status,
            diff=diff,
        )

    changed, diff = client.data_stream_lifecycle.compare(
        current,
        desired,
        replace=replace,
    )
    if not changed:
        module.exit_json(
            changed=False,
            data_stream_lifecycle=sanitize_data(current),
            data_stream_exists=True,
            global_retention=sanitize_data(global_retention),
            status=read_response.status,
            diff=diff,
        )
    if module.check_mode:
        module.exit_json(
            changed=True,
            data_stream_lifecycle=sanitize_data(
                _predicted_lifecycle(
                    client,
                    current,
                    desired,
                    replace=replace,
                )
            ),
            data_stream_exists=True,
            global_retention=sanitize_data(global_retention),
            status=read_response.status,
            diff=diff,
        )

    response = client.data_stream_lifecycle.create_or_update(
        name,
        current=current,
        desired=desired,
        replace=replace,
    )
    if response.status != 200:
        fail_api_error(
            module,
            operation="update data stream lifecycle",
            path=client.data_stream_lifecycle.path(name),
            response=response,
            success_codes=[200],
        )
    refreshed = _read_managed_lifecycle(
        module,
        client,
        name,
    )
    managed = refreshed[2]
    refreshed_retention = refreshed[3]
    if managed is None:
        module.fail_json(
            msg=(
                "Elasticsearch reported a successful data stream lifecycle "
                f"update for {name!r}, but no attachment was observable during "
                "refresh"
            ),
            status=refreshed[0].status,
            mutation_status=response.status,
            response=sanitize_data(refreshed[0].data),
        )
    module.exit_json(
        changed=True,
        data_stream_lifecycle=sanitize_data(managed),
        data_stream_exists=True,
        global_retention=sanitize_data(refreshed_retention),
        status=response.status,
        diff=diff,
    )


def data_stream_lifecycle_argument_spec() -> dict[str, dict[str, Any]]:
    """Return the data stream lifecycle argument specification."""
    argument_spec = elasticsearch_argument_spec()
    argument_spec.update(
        name=dict(type="str", required=True),
        enabled=dict(type="bool"),
        data_retention=dict(type="str"),
        downsampling=dict(
            type="list",
            elements="dict",
            options=dict(
                after=dict(type="str", required=True),
                fixed_interval=dict(type="str", required=True),
            ),
        ),
        replace=dict(type="bool", default=False),
    )
    return argument_spec


def main() -> None:
    module = AnsibleModule(
        argument_spec=data_stream_lifecycle_argument_spec(),
        required_together=elasticsearch_required_together(),
        mutually_exclusive=elasticsearch_mutually_exclusive(),
        supports_check_mode=True,
    )
    run_module(module)


if __name__ == "__main__":
    main()

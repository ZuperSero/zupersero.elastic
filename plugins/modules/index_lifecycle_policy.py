# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

DOCUMENTATION = r"""
---
module: index_lifecycle_policy
short_description: Manage an Elasticsearch index lifecycle policy
description:
  - Creates, reads, updates, and deletes an Elasticsearch index lifecycle management (ILM) policy.
  - The stable phase envelope is typed and validated while action-specific options are passed to Elasticsearch for version-aware validation.
  - Partial updates preserve phases, actions, metadata, and unknown writable fields omitted from the task.
version_added: "1.0.0"
author:
  - Zupersero (@zupersero)
extends_documentation_fragment:
  - zupersero.elastic.elasticsearch
options:
  name:
    description:
      - Name of the lifecycle policy to manage.
      - The name is URL-quoted as one path component.
    type: str
    required: true
  phases:
    description:
      - Lifecycle phase definitions keyed by C(hot), C(warm), C(cold), C(frozen), or C(delete).
      - Each phase accepts C(min_age) and an C(actions) dictionary.
      - Action names and action-specific options are validated by the target Elasticsearch version.
      - Existing phases and nested action options omitted here are preserved unless I(replace=true).
    type: dict
  metadata:
    description:
      - Arbitrary policy metadata stored as the Elasticsearch C(_meta) field.
      - Existing metadata keys omitted here are preserved unless I(replace=true).
    type: dict
  replace:
    description:
      - Whether an existing lifecycle policy should be authoritatively replaced.
      - By default, updates preserve writable policy fields omitted from the task.
      - When C(true), only I(phases) and I(metadata) supplied by the task are sent.
      - Use replacement mode to remove omitted phases or actions or to clear metadata with an empty dictionary.
      - I(phases) is required when replacing an existing policy.
    type: bool
    default: false
  state:
    description:
      - Whether the lifecycle policy should exist.
    type: str
    choices: [present, absent]
    default: present
notes:
  - Supplying only I(name) and I(state=present) reads an existing policy, but I(phases) is required if it does not exist.
  - Elasticsearch increments its server-generated policy version whenever an update is sent.
  - A policy cannot be deleted while it is in use by an index.
  - Check mode predicts creation, updates, and deletion without sending mutating requests.
"""

EXAMPLES = r"""
- name: Create a rollover and retention policy
  zupersero.elastic.index_lifecycle_policy:
    url: https://es.example.invalid:9200
    api_key: "{{ vault_elasticsearch_api_key }}"
    name: application-events
    phases:
      hot:
        actions:
          rollover:
            max_primary_shard_size: 40gb
            max_age: 7d
      delete:
        min_age: 30d
        actions:
          delete: {}
    metadata:
      owner: platform

- name: Add a warm-phase force merge while preserving other phases
  zupersero.elastic.index_lifecycle_policy:
    name: application-events
    phases:
      warm:
        min_age: 1d
        actions:
          forcemerge:
            max_num_segments: 1

- name: Read a lifecycle policy using environment authentication
  zupersero.elastic.index_lifecycle_policy:
    name: application-events
  register: application_lifecycle

- name: Authoritatively replace a policy and clear metadata
  zupersero.elastic.index_lifecycle_policy:
    name: application-events
    replace: true
    phases:
      delete:
        min_age: 14d
        actions:
          delete: {}
    metadata: {}

- name: Delete a lifecycle policy
  zupersero.elastic.index_lifecycle_policy:
    name: obsolete-policy
    state: absent
"""

RETURN = r"""
lifecycle_policy:
  description:
    - Current lifecycle policy returned by Elasticsearch after reconciliation.
    - In update check mode, this is the predicted policy definition.
    - For deletion, this is the last observed policy. It is C(null) when already absent.
  returned: always
  type: dict
  sample:
    name: application-events
    version: 2
    modified_date: '2026-07-27T12:00:00.000Z'
    phases:
      hot:
        min_age: 0ms
        actions:
          rollover:
            max_age: 7d
      delete:
        min_age: 30d
        actions:
          delete:
            delete_searchable_snapshot: true
    _meta:
      owner: platform
    in_use_by:
      indices: []
      data_streams: []
      composable_templates:
        - application-events
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
from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch_services.lifecycle import (  # noqa: E402
    validate_lifecycle_phases,
)


def _desired_policy(module: AnsibleModule) -> dict[str, Any]:
    """Build the user-managed lifecycle policy view."""
    desired: dict[str, Any] = {"name": module.params["name"]}
    if module.params.get("phases") is not None:
        desired["phases"] = module.params["phases"]
    if module.params.get("metadata") is not None:
        desired["_meta"] = module.params["metadata"]
    return desired


def _read_managed_policy(
    module: AnsibleModule,
    client: ElasticsearchClient,
    name: str,
) -> tuple[Any, dict[str, Any] | None]:
    """Read a lifecycle policy or fail with sanitized API context."""
    response, current = client.lifecycle.get(name)
    path = client.lifecycle.path(name)
    if response.status not in (200, 404):
        fail_api_error(
            module,
            operation="read index lifecycle policy",
            path=path,
            response=response,
            success_codes=[200, 404],
        )
    if response.status == 200 and current is None:
        module.fail_json(
            msg=(
                f"Elasticsearch read index lifecycle policy request to {path!r} "
                f"returned HTTP {response.status} with no matching policy definition"
            ),
            status=response.status,
            response=sanitize_data(response.data),
        )
    return response, current


def _predicted_policy(
    client: ElasticsearchClient,
    current: dict[str, Any] | None,
    desired: dict[str, Any],
    *,
    replace: bool,
) -> dict[str, Any]:
    predicted = client.lifecycle.payload(current, desired, replace=replace)
    predicted["name"] = desired["name"]
    return predicted


def _validate_policy(module: AnsibleModule) -> None:
    phases = module.params.get("phases")
    if phases is None:
        return
    try:
        validate_lifecycle_phases(phases)
    except ValueError as exc:
        module.fail_json(msg=str(exc))


def run_module(
    module: AnsibleModule,
    client: ElasticsearchClient | None = None,
) -> None:
    """Reconcile an Elasticsearch index lifecycle policy."""
    _validate_policy(module)
    client = client or ElasticsearchClient(module)
    name = module.params["name"]
    desired = _desired_policy(module)
    replace = module.params["replace"]
    read_response, current = _read_managed_policy(module, client, name)

    if module.params["state"] == "absent":
        diff = {"before": sanitize_data(current or {}), "after": {}}
        if current is None:
            module.exit_json(
                changed=False,
                lifecycle_policy=None,
                status=read_response.status,
                diff=diff,
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                lifecycle_policy=sanitize_data(current),
                status=read_response.status,
                diff=diff,
            )
        response = client.lifecycle.delete(name)
        if response.status != 200:
            fail_api_error(
                module,
                operation="delete index lifecycle policy",
                path=client.lifecycle.path(name),
                response=response,
                success_codes=[200],
            )
        module.exit_json(
            changed=True,
            lifecycle_policy=sanitize_data(current),
            status=response.status,
            diff=diff,
        )

    if (current is None or replace) and module.params.get("phases") is None:
        module.fail_json(
            msg=(
                "phases is required when creating or replacing index lifecycle "
                f"policy {name!r}"
            )
        )

    if current is None:
        diff = {"before": {}, "after": sanitize_data(desired)}
        if module.check_mode:
            module.exit_json(
                changed=True,
                lifecycle_policy=sanitize_data(desired),
                status=read_response.status,
                diff=diff,
            )
        response = client.lifecycle.create_or_update(
            name,
            current=None,
            desired=desired,
            replace=replace,
        )
        if response.status != 200:
            fail_api_error(
                module,
                operation="create index lifecycle policy",
                path=client.lifecycle.path(name),
                response=response,
                success_codes=[200],
            )
        managed = _read_managed_policy(module, client, name)[1]
        module.exit_json(
            changed=True,
            lifecycle_policy=sanitize_data(managed),
            status=response.status,
            diff=diff,
        )

    changed, diff = client.lifecycle.compare(current, desired, replace=replace)
    if not changed:
        module.exit_json(
            changed=False,
            lifecycle_policy=sanitize_data(current),
            status=read_response.status,
            diff=diff,
        )
    if module.check_mode:
        module.exit_json(
            changed=True,
            lifecycle_policy=sanitize_data(
                _predicted_policy(client, current, desired, replace=replace)
            ),
            status=read_response.status,
            diff=diff,
        )

    response = client.lifecycle.create_or_update(
        name,
        current=current,
        desired=desired,
        replace=replace,
    )
    if response.status != 200:
        fail_api_error(
            module,
            operation="update index lifecycle policy",
            path=client.lifecycle.path(name),
            response=response,
            success_codes=[200],
        )
    managed = _read_managed_policy(module, client, name)[1]
    module.exit_json(
        changed=True,
        lifecycle_policy=sanitize_data(managed),
        status=response.status,
        diff=diff,
    )


def lifecycle_policy_argument_spec() -> dict[str, dict[str, Any]]:
    """Return the index lifecycle policy argument specification."""
    argument_spec = elasticsearch_argument_spec()
    argument_spec.update(
        name=dict(type="str", required=True),
        phases=dict(type="dict"),
        metadata=dict(type="dict"),
        replace=dict(type="bool", default=False),
    )
    return argument_spec


def main() -> None:
    module = AnsibleModule(
        argument_spec=lifecycle_policy_argument_spec(),
        required_together=elasticsearch_required_together(),
        mutually_exclusive=elasticsearch_mutually_exclusive(),
        supports_check_mode=True,
    )
    run_module(module)


if __name__ == "__main__":
    main()

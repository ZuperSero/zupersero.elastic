# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later
# pylint: disable=disallowed-name

from __future__ import annotations

DOCUMENTATION = r"""
---
module: enrich_policy
short_description: Manage an Elasticsearch enrich policy
description:
  - Creates, reads, updates, deletes, and explicitly executes an Elasticsearch enrich policy.
  - Partial updates preserve fields omitted from the task, including unknown fields returned by Elasticsearch.
  - Enrich policy execution is never performed implicitly after ordinary CRUD operations.
version_added: "1.0.0"
author:
  - Zupersero (@zupersero)
extends_documentation_fragment:
  - zupersero.elastic.elasticsearch
options:
  name:
    description:
      - Name of the enrich policy to manage.
      - The name is URL-quoted as one path component.
    type: str
    required: true
  policy_type:
    description:
      - Enrich policy strategy.
      - Required when creating or replacing a policy and optional when reading or partially updating one.
    type: str
    choices: [match, range, geo_match]
  source_indices:
    description:
      - Non-empty list of source indices containing the enrich data.
      - Required when creating or replacing a policy.
    type: list
    elements: str
  match_field:
    description:
      - Field used to match an incoming enrich value.
      - Required when creating or replacing a policy.
    type: str
  enrich_fields:
    description:
      - Non-empty list of fields copied from the matching source document.
      - Required when creating or replacing a policy.
    type: list
    elements: str
  replace:
    description:
      - Whether an existing policy should be authoritatively replaced.
      - By default, updates preserve writable fields omitted from the task.
      - When C(true), all policy fields must be supplied and omitted server fields are removed.
    type: bool
    default: false
  execute:
    description:
      - Explicitly execute the policy after reconciliation.
      - Execution materializes the enrich index and can be expensive.
      - In check mode, the execute request is skipped and only the preview is returned.
    type: bool
    default: false
  state:
    description:
      - Whether the enrich policy should exist.
      - C(absent) cannot be combined with I(execute=true).
    type: str
    choices: [present, absent]
    default: present
notes:
  - Supplying only I(name) and I(state=present) reads an existing policy, but all policy fields are required if it does not exist.
  - I(execute=true) requires the policy to exist before this task; use a separate task to create it first.
  - Check mode predicts creation, updates, deletion, and explicit execution without sending mutating requests.
"""

EXAMPLES = r"""
- name: Create a match enrich policy
  zupersero.elastic.enrich_policy:
    url: https://es.example.invalid:9200
    api_key: "{{ vault_elasticsearch_api_key }}"
    name: company-lookup
    policy_type: match
    source_indices:
      - companies
    match_field: id
    enrich_fields:
      - name
      - address

- name: Update only the source indices while preserving other fields
  zupersero.elastic.enrich_policy:
    name: company-lookup
    source_indices:
      - companies
      - companies-archive

- name: Execute the existing policy explicitly
  zupersero.elastic.enrich_policy:
    name: company-lookup
    execute: true

- name: Authoritatively replace a range policy
  zupersero.elastic.enrich_policy:
    name: geo-lookup
    policy_type: range
    source_indices:
      - postal-ranges
    match_field: range
    enrich_fields:
      - region
    replace: true

- name: Delete an enrich policy
  zupersero.elastic.enrich_policy:
    name: obsolete-policy
    state: absent
"""

RETURN = r"""
enrich_policy:
  description:
    - Current enrich policy returned by Elasticsearch after reconciliation.
    - In check mode, this is the predicted policy definition.
    - It is C(null) when the policy is absent.
  returned: always
  type: dict
  sample:
    name: company-lookup
    policy_type: match
    source_indices:
      - companies
    match_field: id
    enrich_fields:
      - name
      - address
status:
  description: HTTP status of the mutation, or current-state read when unchanged or in check mode.
  returned: always
  type: int
  sample: 200
execution:
  description:
    - Result of an explicit policy execution.
    - In check mode, contains C(would_execute=true) without contacting the execute endpoint.
  returned: always
  type: dict
  sample:
    acknowledged: true
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
from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch_services.enrich import (  # noqa: E402
    validate_enrich_policy,
)


def _desired_policy(module: AnsibleModule) -> dict[str, Any]:
    """Build the user-managed canonical policy view."""
    desired: dict[str, Any] = {"name": module.params["name"]}
    for field in (
        "policy_type",
        "source_indices",
        "match_field",
        "enrich_fields",
    ):
        if module.params.get(field) is not None:
            desired[field] = module.params[field]
    return desired


def _validate_policy(module: AnsibleModule) -> None:
    """Validate supplied fields before contacting Elasticsearch."""
    try:
        validate_enrich_policy(
            module.params.get("policy_type"),
            module.params.get("source_indices"),
            module.params.get("match_field"),
            module.params.get("enrich_fields"),
        )
    except ValueError as exc:
        module.fail_json(msg=str(exc))


def _read_managed_policy(
    module: AnsibleModule,
    client: ElasticsearchClient,
    name: str,
) -> tuple[Any, dict[str, Any] | None]:
    """Read an enrich policy or fail with sanitized API context."""
    response, current = client.enrich_policy.get(name)
    path = client.enrich_policy.path(name)
    if response.status not in (200, 404):
        fail_api_error(
            module,
            operation="read enrich policy",
            path=path,
            response=response,
            success_codes=[200, 404],
        )
    empty_policy_list = (
        isinstance(response.data, dict) and response.data.get("policies") == []
    )
    if response.status == 200 and current is None and not empty_policy_list:
        module.fail_json(
            msg=(
                f"Elasticsearch read enrich policy request to {path!r} "
                "returned an unrecognized policy response"
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
    """Build the canonical policy predicted by a check-mode update."""
    payload = client.enrich_policy.payload(current, desired, replace=replace)
    predicted = client.enrich_policy._from_wire(desired["name"], payload)
    return predicted or desired


def run_module(
    module: AnsibleModule,
    client: ElasticsearchClient | None = None,
) -> None:
    """Reconcile an Elasticsearch enrich policy and optionally execute it."""
    _validate_policy(module)
    if module.params["state"] == "absent" and module.params["execute"]:
        module.fail_json(msg="execute=true cannot be combined with state=absent")

    client = client or ElasticsearchClient(module)
    name = module.params["name"]
    desired = _desired_policy(module)
    replace = module.params["replace"]
    execute_requested = module.params["execute"]
    read_response, current = _read_managed_policy(module, client, name)

    if module.params["state"] == "absent":
        diff = {"before": sanitize_data(current or {}), "after": {}}
        if current is None:
            module.exit_json(
                changed=False,
                enrich_policy=None,
                execution={},
                status=read_response.status,
                diff=diff,
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                enrich_policy=sanitize_data(current),
                execution={},
                status=read_response.status,
                diff=diff,
            )
        response = client.enrich_policy.delete(name)
        if response.status != 200:
            fail_api_error(
                module,
                operation="delete enrich policy",
                path=client.enrich_policy.path(name),
                response=response,
                success_codes=[200],
            )
        module.exit_json(
            changed=True,
            enrich_policy=sanitize_data(current),
            execution={},
            status=response.status,
            diff=diff,
        )

    required_fields = ("policy_type", "source_indices", "match_field", "enrich_fields")
    if current is None and any(module.params.get(field) is None for field in required_fields):
        module.fail_json(
            msg=(
                "policy_type, source_indices, match_field, and enrich_fields "
                f"are required when creating enrich policy {name!r}"
            )
        )
    if current is not None and replace and any(
        module.params.get(field) is None for field in required_fields
    ):
        module.fail_json(
            msg=(
                "policy_type, source_indices, match_field, and enrich_fields "
                f"are required when replace=true for enrich policy {name!r}"
            )
        )
    if current is None and execute_requested:
        module.fail_json(
            msg=f"enrich policy {name!r} must exist before execute=true can run"
        )

    changed = False
    mutation_status = read_response.status
    if current is None:
        predicted = _predicted_policy(client, None, desired, replace=replace)
        diff = {"before": {}, "after": sanitize_data(predicted)}
        changed = True
        if module.check_mode:
            execution = {"would_execute": True} if execute_requested else {}
            module.exit_json(
                changed=True,
                enrich_policy=sanitize_data(predicted),
                execution=execution,
                status=read_response.status,
                diff=diff,
            )
        response = client.enrich_policy.create_or_update(
            name,
            current=None,
            desired=desired,
            replace=replace,
        )
        if response.status != 200:
            fail_api_error(
                module,
                operation="create enrich policy",
                path=client.enrich_policy.path(name),
                response=response,
                success_codes=[200],
            )
        mutation_status = response.status
        _, current = _read_managed_policy(module, client, name)
    else:
        policy_changed, diff = client.enrich_policy.compare(
            current,
            desired,
            replace=replace,
        )
        changed = policy_changed
        if policy_changed and module.check_mode:
            predicted = _predicted_policy(client, current, desired, replace=replace)
            execution = {"would_execute": True} if execute_requested else {}
            module.exit_json(
                changed=True,
                enrich_policy=sanitize_data(predicted),
                execution=execution,
                status=read_response.status,
                diff=diff,
            )
        if policy_changed:
            response = client.enrich_policy.create_or_update(
                name,
                current=current,
                desired=desired,
                replace=replace,
            )
            if response.status != 200:
                fail_api_error(
                    module,
                    operation="update enrich policy",
                    path=client.enrich_policy.path(name),
                    response=response,
                    success_codes=[200],
                )
            mutation_status = response.status
            _, current = _read_managed_policy(module, client, name)

    execution: dict[str, Any] = {}
    if execute_requested:
        changed = True
        if module.check_mode:
            execution = {"would_execute": True}
        else:
            response = client.enrich_policy.execute(name)
            if response.status not in (200, 202):
                fail_api_error(
                    module,
                    operation="execute enrich policy",
                    path=client.enrich_policy.execute_path(name),
                    response=response,
                    success_codes=[200, 202],
                )
            execution = sanitize_data(response.data)
            mutation_status = response.status

    module.exit_json(
        changed=changed,
        enrich_policy=sanitize_data(current),
        execution=execution,
        status=mutation_status,
        diff=diff,
    )


def enrich_policy_argument_spec() -> dict[str, dict[str, Any]]:
    """Return the enrich-policy argument specification."""
    argument_spec = elasticsearch_argument_spec()
    argument_spec.update(
        name=dict(type="str", required=True),
        policy_type=dict(type="str", choices=["match", "range", "geo_match"]),
        source_indices=dict(type="list", elements="str"),
        match_field=dict(type="str"),
        enrich_fields=dict(type="list", elements="str"),
        replace=dict(type="bool", default=False),
        execute=dict(type="bool", default=False),
    )
    return argument_spec


def main() -> None:
    module = AnsibleModule(
        argument_spec=enrich_policy_argument_spec(),
        required_together=elasticsearch_required_together(),
        mutually_exclusive=elasticsearch_mutually_exclusive(),
        supports_check_mode=True,
    )
    run_module(module)


if __name__ == "__main__":
    main()

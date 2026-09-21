# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later
# pylint: disable=unsupported-binary-operation

"""Manage Elasticsearch ingest pipelines."""

DOCUMENTATION = r"""
---
module: ingest_pipeline
short_description: Manage an Elasticsearch ingest pipeline
description:
  - Creates, reads, updates, and deletes a named Elasticsearch ingest pipeline.
  - Processor definitions are passed as dictionaries so the target Elasticsearch version validates processor-specific options.
  - Partial updates preserve fields omitted from the task, including unknown writable fields returned by Elasticsearch.
version_added: "1.0.0"
author:
  - Zupersero (@zupersero)
extends_documentation_fragment:
  - zupersero.elastic.elasticsearch
options:
  name:
    description:
      - Name of the ingest pipeline to manage.
      - The name is URL-quoted as one path component.
    type: str
    required: true
  description:
    description:
      - Human-readable pipeline description.
    type: str
  processors:
    description:
      - Ordered list of ingest processor definitions.
      - Each item must be a dictionary containing one processor name and its options.
    type: list
    elements: dict
  on_failure:
    description:
      - Processors to run when a processor in the main list fails.
    type: list
    elements: dict
  version:
    description:
      - Optional user-managed pipeline version.
    type: int
  metadata:
    description:
      - Arbitrary metadata stored in the Elasticsearch C(_meta) field.
    type: dict
  replace:
    description:
      - Whether an existing pipeline should be authoritatively replaced.
      - By default, updates preserve writable fields omitted from the task.
      - When C(true), only fields supplied by the task are sent.
    type: bool
    default: false
  state:
    description:
      - Whether the ingest pipeline should exist.
    type: str
    choices: [present, absent]
    default: present
notes:
  - Supplying only I(name) and I(state=present) reads an existing pipeline, but I(processors) is required if it does not exist.
  - I(processors) is also required when replacing an existing pipeline because Elasticsearch requires a complete pipeline definition.
  - Check mode predicts creation, updates, and deletion without sending mutating requests.
"""

EXAMPLES = r"""
- name: Create an application ingest pipeline
  zupersero.elastic.ingest_pipeline:
    url: https://es.example.invalid:9200
    api_key: "{{ vault_elasticsearch_api_key }}"
    name: application-events
    description: Normalize application events
    processors:
      - set:
          field: event.ingested
          copy_from: '@timestamp'
      - rename:
          field: message
          target_field: event.original
    on_failure:
      - set:
          field: error.pipeline
          value: application-events
    metadata:
      owner: platform

- name: Add a processor while preserving the existing pipeline
  zupersero.elastic.ingest_pipeline:
    name: application-events
    processors:
      - set:
          field: event.ingested
          copy_from: '@timestamp'
      - rename:
          field: message
          target_field: event.original
      - set:
          field: event.dataset
          value: application

- name: Read an ingest pipeline
  zupersero.elastic.ingest_pipeline:
    name: application-events
  register: application_pipeline

- name: Authoritatively replace a pipeline
  zupersero.elastic.ingest_pipeline:
    name: application-events
    replace: true
    processors:
      - set:
          field: event.kind
          value: event
    metadata: {}

- name: Delete an ingest pipeline
  zupersero.elastic.ingest_pipeline:
    name: obsolete-pipeline
    state: absent
"""

RETURN = r"""
ingest_pipeline:
  description:
    - Current ingest pipeline returned by Elasticsearch after reconciliation.
    - In check mode, this is the predicted pipeline definition.
    - For deletion, this is the last observed pipeline. It is C(null) when already absent.
  returned: always
  type: dict
  sample:
    name: application-events
    description: Normalize application events
    processors:
      - set:
          field: event.ingested
          copy_from: '@timestamp'
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


def _desired_pipeline(module: AnsibleModule) -> dict[str, Any]:
    """Build the user-managed pipeline view."""
    desired: dict[str, Any] = {"name": module.params["name"]}
    for field in ("description", "processors", "on_failure", "version"):
        if module.params.get(field) is not None:
            desired[field] = module.params[field]
    if module.params.get("metadata") is not None:
        desired["_meta"] = module.params["metadata"]
    return desired


def _read_managed_pipeline(
    module: AnsibleModule,
    client: ElasticsearchClient,
    name: str,
) -> tuple[Any, dict[str, Any] | None]:
    """Read a pipeline or fail with sanitized API context."""
    response, current = client.pipeline.get(name)
    path = client.pipeline.path(name)
    if response.status not in (200, 404):
        fail_api_error(
            module,
            operation="read ingest pipeline",
            path=path,
            response=response,
            success_codes=[200, 404],
        )
    if response.status == 200 and current is None:
        module.fail_json(
            msg=(
                f"Elasticsearch read ingest pipeline request to {path!r} "
                f"returned HTTP {response.status} with no matching pipeline definition"
            ),
            status=response.status,
            response=sanitize_data(response.data),
        )
    return response, current


def _predicted_pipeline(
    client: ElasticsearchClient,
    current: dict[str, Any] | None,
    desired: dict[str, Any],
    *,
    replace: bool,
) -> dict[str, Any]:
    predicted = client.pipeline.payload(current, desired, replace=replace)
    predicted["name"] = desired["name"]
    return predicted


def run_module(
    module: AnsibleModule,
    client: ElasticsearchClient | None = None,
) -> None:
    """Reconcile an Elasticsearch ingest pipeline."""
    client = client or ElasticsearchClient(module)
    name = module.params["name"]
    desired = _desired_pipeline(module)
    replace = module.params["replace"]
    read_response, current = _read_managed_pipeline(module, client, name)

    if module.params["state"] == "absent":
        diff = {"before": sanitize_data(current or {}), "after": {}}
        if current is None:
            module.exit_json(
                changed=False,
                ingest_pipeline=None,
                status=read_response.status,
                diff=diff,
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                ingest_pipeline=sanitize_data(current),
                status=read_response.status,
                diff=diff,
            )
        response = client.pipeline.delete(name)
        if response.status != 200:
            fail_api_error(
                module,
                operation="delete ingest pipeline",
                path=client.pipeline.path(name),
                response=response,
                success_codes=[200],
            )
        module.exit_json(
            changed=True,
            ingest_pipeline=sanitize_data(current),
            status=response.status,
            diff=diff,
        )

    if (current is None or replace) and module.params.get("processors") is None:
        module.fail_json(
            msg=(
                "processors is required when creating or replacing ingest "
                f"pipeline {name!r}"
            )
        )

    if current is None:
        diff = {"before": {}, "after": sanitize_data(desired)}
        if module.check_mode:
            module.exit_json(
                changed=True,
                ingest_pipeline=sanitize_data(desired),
                status=read_response.status,
                diff=diff,
            )
        response = client.pipeline.create_or_update(
            name,
            current=None,
            desired=desired,
            replace=replace,
        )
        if response.status != 200:
            fail_api_error(
                module,
                operation="create ingest pipeline",
                path=client.pipeline.path(name),
                response=response,
                success_codes=[200],
            )
        refresh_response, managed = _read_managed_pipeline(module, client, name)
        if managed is None:
            module.fail_json(
                msg=(
                    f"Elasticsearch reported successful ingest pipeline creation "
                    f"for {name!r}, but it was not observable during refresh"
                ),
                status=refresh_response.status,
                mutation_status=response.status,
                response=sanitize_data(refresh_response.data),
            )
        module.exit_json(
            changed=True,
            ingest_pipeline=sanitize_data(managed),
            status=response.status,
            diff=diff,
        )

    changed, diff = client.pipeline.compare(current, desired, replace=replace)
    if not changed:
        module.exit_json(
            changed=False,
            ingest_pipeline=sanitize_data(current),
            status=read_response.status,
            diff=diff,
        )
    if module.check_mode:
        module.exit_json(
            changed=True,
            ingest_pipeline=sanitize_data(
                _predicted_pipeline(client, current, desired, replace=replace)
            ),
            status=read_response.status,
            diff=diff,
        )

    response = client.pipeline.create_or_update(
        name,
        current=current,
        desired=desired,
        replace=replace,
    )
    if response.status != 200:
        fail_api_error(
            module,
            operation="update ingest pipeline",
            path=client.pipeline.path(name),
            response=response,
            success_codes=[200],
        )
    refresh_response, managed = _read_managed_pipeline(module, client, name)
    if managed is None:
        module.fail_json(
            msg=(
                f"Elasticsearch reported successful ingest pipeline update for "
                f"{name!r}, but it was not observable during refresh"
            ),
            status=refresh_response.status,
            mutation_status=response.status,
            response=sanitize_data(refresh_response.data),
        )
    module.exit_json(
        changed=True,
        ingest_pipeline=sanitize_data(managed),
        status=response.status,
        diff=diff,
    )


def ingest_pipeline_argument_spec() -> dict[str, dict[str, Any]]:
    """Return the ingest pipeline argument specification."""
    argument_spec = elasticsearch_argument_spec()
    argument_spec.update(
        name=dict(type="str", required=True),
        description=dict(type="str"),
        processors=dict(type="list", elements="dict"),
        on_failure=dict(type="list", elements="dict"),
        version=dict(type="int"),
        metadata=dict(type="dict"),
        replace=dict(type="bool", default=False),
    )
    return argument_spec


def main() -> None:
    module = AnsibleModule(
        argument_spec=ingest_pipeline_argument_spec(),
        required_together=elasticsearch_required_together(),
        mutually_exclusive=elasticsearch_mutually_exclusive(),
        supports_check_mode=True,
    )
    run_module(module)


if __name__ == "__main__":
    main()

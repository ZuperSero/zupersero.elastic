# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

DOCUMENTATION = r"""
---
module: index_template
short_description: Manage an Elasticsearch composable index template
description:
  - Creates, reads, updates, and deletes an Elasticsearch composable index template.
  - The module manages the C(_index_template) API, not deprecated legacy templates.
  - Updates preserve fields omitted from the task, including unknown writable fields returned by Elasticsearch.
version_added: "1.0.0"
author:
  - Zupersero (@zupersero)
extends_documentation_fragment:
  - zupersero.elastic.elasticsearch
options:
  name:
    description:
      - Name of the index template to manage.
      - The name is URL-quoted as one path component.
    type: str
    required: true
  index_patterns:
    description:
      - Wildcard expressions matched against new index and data-stream names.
      - Required when creating a template. It may be omitted to read or partially update an existing template.
    type: list
    elements: str
  composed_of:
    description:
      - Ordered component-template names to merge.
      - Later component templates have higher precedence.
    type: list
    elements: str
  settings:
    description:
      - Index settings applied directly by this index template.
      - The optional C(index) namespace and dotted setting names are accepted.
      - Existing settings omitted here are preserved.
    type: dict
  mappings:
    description:
      - Index mappings applied directly by this index template.
      - Existing mapping fields omitted here are preserved.
    type: dict
  aliases:
    description:
      - Index or data-stream aliases applied by this index template.
      - Existing aliases omitted here are preserved.
    type: dict
  priority:
    description:
      - Precedence when multiple index templates match.
      - The matching template with the highest priority is selected.
    type: int
  version:
    description:
      - External version number used to manage the index template.
      - Elasticsearch does not generate or increment this value.
    type: int
  metadata:
    description:
      - User metadata stored as the Elasticsearch C(_meta) field.
      - Existing metadata keys omitted here are preserved.
    type: dict
  data_stream:
    description:
      - Data-stream template options.
      - Supply an empty dictionary to create a data-stream-enabled template.
      - Supported keys are C(hidden), C(allow_custom_routing), and C(failure_store), subject to the Elasticsearch version.
    type: dict
  lifecycle:
    description:
      - Typed index lifecycle management settings applied by the template.
      - Set I(lifecycle.name) to attach an index lifecycle policy.
      - I(lifecycle.rollover_alias) is used for alias-based rollover and is not valid for data-stream templates.
      - Supply an empty dictionary to detach the lifecycle policy and rollover alias.
      - Lifecycle settings supplied here must not also be supplied through I(settings).
    type: dict
    suboptions:
      name:
        description:
          - Name of the index lifecycle policy applied to new indices or data-stream backing indices.
        type: str
      rollover_alias:
        description:
          - Alias updated by an ILM rollover action for alias-based rolling indices.
          - Do not set this for data streams, which manage rollover without an alias.
        type: str
  allow_auto_create:
    description:
      - Whether matching indices may be automatically created.
      - Overrides the cluster C(action.auto_create_index) setting for this template.
    type: bool
  ignore_missing_component_templates:
    description:
      - Component-template names allowed to be missing when this template is stored.
    type: list
    elements: str
  deprecated:
    description:
      - Whether Elasticsearch should mark the index template as deprecated.
    type: bool
  replace:
    description:
      - Whether an existing index template should be fully replaced.
      - By default, updates preserve existing fields omitted from the task.
      - When C(true), only the requested writable fields are sent.
      - Empty I(settings), I(mappings), I(aliases), or I(metadata) dictionaries clear existing values, and omitted fields such as I(data_stream) are removed.
      - I(index_patterns) must contain at least one pattern in replacement mode.
    type: bool
    default: false
  state:
    description:
      - Whether the index template should exist.
    type: str
    choices: [present, absent]
    default: present
notes:
  - Changes affect only indices and data streams created after the index template is updated.
  - Supplying only I(name) and I(state=present) reads an existing template, but I(index_patterns) is required if it does not exist.
  - Use I(replace=true) only when the task declares the complete desired index-template state.
  - For alias-based rollover, bootstrap the first numbered index separately and make it the write index for I(lifecycle.rollover_alias).
  - Do not also define the rollover alias under I(aliases); Elasticsearch reports duplicate-alias errors after rollover.
  - Check mode predicts creation, updates, and deletion without sending mutating requests.
"""

EXAMPLES = r"""
- name: Create a composable index template
  zupersero.elastic.index_template:
    url: https://es.example.invalid:9200
    api_key: "{{ vault_elasticsearch_api_key }}"
    name: application-events
    index_patterns:
      - application-events-*
    composed_of:
      - application-mappings
    settings:
      number_of_replicas: 1
    priority: 200
    version: 1

- name: Add a direct mapping and update metadata
  zupersero.elastic.index_template:
    name: application-events
    mappings:
      properties:
        environment:
          type: keyword
    metadata:
      owner: platform

- name: Attach lifecycle management to an alias-based rolling index
  zupersero.elastic.index_template:
    name: application-events
    lifecycle:
      name: application-events-policy
      rollover_alias: application-events

- name: Attach lifecycle management to a data-stream template
  zupersero.elastic.index_template:
    name: application-stream
    index_patterns:
      - application-stream-*
    data_stream: {}
    lifecycle:
      name: application-stream-policy

- name: Detach lifecycle management
  zupersero.elastic.index_template:
    name: application-events
    lifecycle: {}

- name: Read an index template using environment authentication
  zupersero.elastic.index_template:
    name: application-events
  register: application_template

- name: Replace an index template and disable data-stream mode
  zupersero.elastic.index_template:
    name: application-events
    replace: true
    index_patterns:
      - application-events-*
    settings:
      number_of_replicas: 1
    mappings: {}
    aliases: {}
    metadata: {}

- name: Delete an index template
  zupersero.elastic.index_template:
    name: obsolete-template
    state: absent
"""

RETURN = r"""
index_template:
  description:
    - Current index-template definition returned by Elasticsearch after reconciliation.
    - In update check mode, this is the predicted definition.
    - For deletion, this is the last observed definition. It is C(null) when already absent.
  returned: always
  type: dict
  sample:
    name: application-events
    index_patterns:
      - application-events-*
    composed_of:
      - application-mappings
    template:
      settings:
        number_of_replicas: "1"
    priority: 200
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

import copy  # noqa: E402
from typing import Any, Mapping  # noqa: E402

from ansible.module_utils.basic import AnsibleModule  # noqa: E402

from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch import (  # noqa: E402
    ElasticsearchClient,
    elasticsearch_argument_spec,
    elasticsearch_mutually_exclusive,
    elasticsearch_required_together,
    fail_api_error,
    sanitize_data,
)
from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch_services.index import (  # noqa: E402
    flatten_index_settings,
)


def _typed_lifecycle_settings(lifecycle: Mapping[str, Any]) -> dict[str, Any]:
    """Project typed lifecycle options into Elasticsearch index settings."""
    if not lifecycle or all(
        lifecycle.get(field) is None for field in ("name", "rollover_alias")
    ):
        return {
            "index.lifecycle.name": None,
            "index.lifecycle.rollover_alias": None,
        }
    settings = {}
    if lifecycle.get("name") is not None:
        settings["index.lifecycle.name"] = lifecycle["name"]
    if lifecycle.get("rollover_alias") is not None:
        settings["index.lifecycle.rollover_alias"] = lifecycle["rollover_alias"]
    return settings


def _desired_index_template(module: AnsibleModule) -> dict[str, Any]:
    """Build the user-managed index-template view."""
    desired: dict[str, Any] = {"name": module.params["name"]}
    for field in (
        "index_patterns",
        "composed_of",
        "priority",
        "version",
        "data_stream",
        "allow_auto_create",
        "ignore_missing_component_templates",
        "deprecated",
    ):
        if module.params.get(field) is not None:
            desired[field] = module.params[field]
    template = {
        field: copy.deepcopy(module.params[field])
        for field in ("settings", "mappings", "aliases")
        if module.params.get(field) is not None
    }
    lifecycle = module.params.get("lifecycle")
    if lifecycle is not None:
        settings = template.setdefault("settings", {})
        settings.update(_typed_lifecycle_settings(lifecycle))
    if template:
        desired["template"] = template
    if module.params.get("metadata") is not None:
        desired["_meta"] = module.params["metadata"]
    return desired


def _validate_typed_lifecycle(
    module: AnsibleModule,
    current: Mapping[str, Any] | None,
    *,
    replace: bool,
) -> None:
    """Validate lifecycle settings that depend on current template state."""
    lifecycle = module.params.get("lifecycle")
    if lifecycle is None:
        return

    raw_settings = module.params.get("settings")
    if isinstance(raw_settings, Mapping):
        flattened_raw = flatten_index_settings(raw_settings)
        conflicts = sorted(
            {
                key
                for key in ("lifecycle.name", "lifecycle.rollover_alias")
                if key in flattened_raw
            }
        )
        if conflicts:
            module.fail_json(
                msg=(
                    "lifecycle must not be combined with duplicate raw settings: "
                    + ", ".join(f"index.{key}" for key in conflicts)
                )
            )

    rollover_alias = lifecycle.get("rollover_alias")
    current_template = current.get("template") if isinstance(current, Mapping) else None
    current_settings = (
        current_template.get("settings")
        if isinstance(current_template, Mapping)
        else None
    )
    current_lifecycle = (
        flatten_index_settings(current_settings)
        if isinstance(current_settings, Mapping)
        else {}
    )
    if (
        rollover_alias is not None
        and lifecycle.get("name") is None
        and (replace or current_lifecycle.get("lifecycle.name") in (None, ""))
    ):
        module.fail_json(
            msg=(
                "lifecycle.name is required when setting "
                "lifecycle.rollover_alias on a template without an attached policy"
            )
        )

    desired_data_stream = module.params.get("data_stream")
    is_data_stream = (
        desired_data_stream is not None
        or (
            not replace
            and isinstance(current, Mapping)
            and isinstance(current.get("data_stream"), Mapping)
        )
    )
    if rollover_alias is not None and is_data_stream:
        module.fail_json(
            msg=(
                "lifecycle.rollover_alias is not valid for a data-stream template; "
                "data streams manage rollover without an alias"
            )
        )

    if rollover_alias is None:
        return
    desired_template_aliases = module.params.get("aliases")
    current_aliases = (
        current_template.get("aliases")
        if isinstance(current_template, Mapping)
        else None
    )
    if desired_template_aliases is not None:
        effective_aliases = desired_template_aliases
    elif replace:
        effective_aliases = None
    else:
        effective_aliases = current_aliases
    if isinstance(effective_aliases, Mapping) and rollover_alias in effective_aliases:
        module.fail_json(
            msg=(
                f"lifecycle.rollover_alias {rollover_alias!r} must not also be "
                "defined in template aliases"
            )
        )


def _read_managed_template(
    module: AnsibleModule,
    client: ElasticsearchClient,
    name: str,
) -> tuple[Any, dict[str, Any] | None]:
    """Read an index template or fail with sanitized API context."""
    response, current = client.index_template.get(name)
    path = client.index_template.path(name)
    if response.status not in (200, 404):
        fail_api_error(
            module,
            operation="read index template",
            path=path,
            response=response,
            success_codes=[200, 404],
        )
    if response.status == 200 and current is None:
        module.fail_json(
            msg=(
                f"Elasticsearch read index template request to {path!r} "
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
    predicted = client.index_template.payload(
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
    """Reconcile an Elasticsearch composable index template."""
    client = client or ElasticsearchClient(module)
    name = module.params["name"]
    desired = _desired_index_template(module)
    replace = module.params["replace"]
    read_response, current = _read_managed_template(module, client, name)
    _validate_typed_lifecycle(module, current, replace=replace)

    if module.params["state"] == "absent":
        diff = {"before": sanitize_data(current or {}), "after": {}}
        if current is None:
            module.exit_json(
                changed=False,
                index_template=None,
                status=read_response.status,
                diff=diff,
            )
        if module.check_mode:
            module.exit_json(
                changed=True,
                index_template=sanitize_data(current),
                status=read_response.status,
                diff=diff,
            )
        response = client.index_template.delete(name)
        if response.status != 200:
            fail_api_error(
                module,
                operation="delete index template",
                path=client.index_template.path(name),
                response=response,
                success_codes=[200],
            )
        module.exit_json(
            changed=True,
            index_template=sanitize_data(current),
            status=response.status,
            diff=diff,
        )

    if (current is None or replace) and not module.params.get("index_patterns"):
        module.fail_json(
            msg=(
                "index_patterns must contain at least one pattern when creating or "
                "replacing "
                f"index template {name!r}"
            )
        )

    if current is None:
        diff = {"before": {}, "after": sanitize_data(desired)}
        if module.check_mode:
            module.exit_json(
                changed=True,
                index_template=sanitize_data(desired),
                status=read_response.status,
                diff=diff,
            )
        response = client.index_template.create_or_update(
            name,
            current=None,
            desired=desired,
            replace=replace,
        )
        if response.status != 200:
            fail_api_error(
                module,
                operation="create index template",
                path=client.index_template.path(name),
                response=response,
                success_codes=[200],
            )
        managed = _read_managed_template(module, client, name)[1]
        module.exit_json(
            changed=True,
            index_template=sanitize_data(managed),
            status=response.status,
            diff=diff,
        )

    changed, diff = client.index_template.compare(
        current,
        desired,
        replace=replace,
    )
    if not changed:
        module.exit_json(
            changed=False,
            index_template=sanitize_data(current),
            status=read_response.status,
            diff=diff,
        )
    if module.check_mode:
        module.exit_json(
            changed=True,
            index_template=sanitize_data(
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

    response = client.index_template.create_or_update(
        name,
        current=current,
        desired=desired,
        replace=replace,
    )
    if response.status != 200:
        fail_api_error(
            module,
            operation="update index template",
            path=client.index_template.path(name),
            response=response,
            success_codes=[200],
        )
    managed = _read_managed_template(module, client, name)[1]
    module.exit_json(
        changed=True,
        index_template=sanitize_data(managed),
        status=response.status,
        diff=diff,
    )


def index_template_argument_spec() -> dict[str, dict[str, Any]]:
    """Return the composable index-template argument specification."""
    argument_spec = elasticsearch_argument_spec()
    argument_spec.update(
        name=dict(type="str", required=True),
        index_patterns=dict(type="list", elements="str"),
        composed_of=dict(type="list", elements="str"),
        settings=dict(type="dict"),
        mappings=dict(type="dict"),
        aliases=dict(type="dict"),
        priority=dict(type="int"),
        version=dict(type="int"),
        metadata=dict(type="dict"),
        data_stream=dict(type="dict"),
        lifecycle=dict(
            type="dict",
            options=dict(
                name=dict(type="str"),
                rollover_alias=dict(type="str"),
            ),
        ),
        allow_auto_create=dict(type="bool"),
        ignore_missing_component_templates=dict(type="list", elements="str"),
        deprecated=dict(type="bool"),
        replace=dict(type="bool", default=False),
    )
    return argument_spec


def main() -> None:
    module = AnsibleModule(
        argument_spec=index_template_argument_spec(),
        required_together=elasticsearch_required_together(),
        mutually_exclusive=elasticsearch_mutually_exclusive(),
        supports_check_mode=True,
    )
    run_module(module)


if __name__ == "__main__":
    main()

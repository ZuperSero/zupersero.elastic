# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

DOCUMENTATION = r"""
---
module: elasticsearch_object
short_description: Manage an arbitrary Elasticsearch API object
description:
  - Manages an object at an arbitrary Elasticsearch API path.
  - Use a typed collection module when one exists; this module is an escape hatch for other object APIs.
  - Reads current state before changing it, ignores unknown server fields by default, and supports check and diff mode.
version_added: "1.0.0"
author:
  - Zupersero (@zupersero)
extends_documentation_fragment:
  - zupersero.elastic.elasticsearch
options:
  state:
    description: Whether the object should exist.
    type: str
    choices: [present, absent]
    default: present
  path:
    description:
      - API path used to read, update, and delete the object.
      - If I(id) is set, its URL-quoted value is appended, or replaces C({id}) in the path.
      - Must be relative; absolute, cross-origin, and malformed paths are rejected.
    type: str
    required: true
  id:
    description:
      - Optional resource identity. It is URL-quoted before being added to a path.
    type: str
  payload:
    description:
      - Desired object payload. Required when I(state=present).
      - Fields not present in this payload are ignored during the default comparison.
    type: dict
  query:
    description:
      - Query parameters sent with every read, create, update, and delete request.
    type: dict
    default: {}
  create_path:
    description:
      - Optional API path used only for creation.
      - Supports the same C({id}) interpolation as I(path).
    type: str
  get_method:
    description: HTTP method used to read current state.
    type: str
    choices: [GET, POST]
    default: GET
  create_method:
    description: HTTP method used to create a missing object.
    type: str
    choices: [POST, PUT, PATCH]
    default: PUT
  update_method:
    description: HTTP method used to update an existing object.
    type: str
    choices: [POST, PUT, PATCH]
    default: PUT
  delete_method:
    description: HTTP method used to delete an existing object.
    type: str
    choices: [DELETE, POST]
    default: DELETE
  get_success_codes:
    description: HTTP status codes accepted when reading an existing object.
    type: list
    elements: int
    default: [200]
  create_success_codes:
    description: HTTP status codes accepted after creation.
    type: list
    elements: int
    default: [200, 201, 202]
  update_success_codes:
    description: HTTP status codes accepted after an update.
    type: list
    elements: int
    default: [200, 201, 202]
  delete_success_codes:
    description: HTTP status codes accepted after deletion.
    type: list
    elements: int
    default: [200, 202, 204]
  not_found_codes:
    description: HTTP status codes that mean the object does not exist.
    type: list
    elements: int
    default: [404]
  response_path:
    description:
      - Dotted path used to extract the managed object from read and mutation responses.
      - Numeric path components can select list entries.
    type: str
  compare_fields:
    description:
      - Dotted paths to compare explicitly.
      - By default, only fields supplied in I(payload) are compared.
    type: list
    elements: str
    default: []
  ignore_fields:
    description: Dotted paths removed before comparing and displaying the diff.
    type: list
    elements: str
    default: []
  sensitive_fields:
    description:
      - Dotted payload or response paths redacted from object output, diffs, and API failures.
      - Credential-like key names are redacted automatically.
    type: list
    elements: str
    default: []
  unordered_lists:
    description: Whether every list should be sorted before comparison.
    type: bool
    default: false
notes:
  - Values under keys that look like passwords, tokens, credentials, or private keys are redacted from results and diffs.
  - Create, update, and delete requests are retried only when I(retry_mutating_requests=true).
"""

EXAMPLES = r"""
- name: Manage an ingest pipeline
  zupersero.elastic.elasticsearch_object:
    url: https://es.example.invalid:9200
    api_key: "{{ vault_elasticsearch_api_key }}"
    path: _ingest/pipeline
    id: normalize-events
    payload:
      description: Normalize event fields
      processors:
        - lowercase:
            field: event.category

- name: Preview an update and show a stable diff
  zupersero.elastic.elasticsearch_object:
    path: _scripts/{id}
    id: score script/v2
    payload:
      script:
        lang: painless
        source: "doc['score'].value"
    ignore_fields:
      - version
  check_mode: true
  diff: true

- name: Delete an object
  zupersero.elastic.elasticsearch_object:
    path: _ingest/pipeline
    id: obsolete-pipeline
    state: absent
"""

RETURN = r"""
object:
  description: Managed object after reconciliation, or the last observed object when deleting.
  returned: always
  type: raw
status:
  description: Mutation HTTP status when changed, otherwise the current-state read status.
  returned: always
  type: int
diff:
  description: Sanitized normalized before and after values.
  returned: always
  type: dict
  contains:
    before:
      description: Normalized state before reconciliation.
      type: raw
    after:
      description: Normalized desired state.
      type: raw
"""

from ansible.module_utils.basic import AnsibleModule  # noqa: E402

from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch import (  # noqa: E402
    ElasticsearchClient,
    compare_objects,
    elasticsearch_argument_spec,
    elasticsearch_mutually_exclusive,
    elasticsearch_required_together,
    extract_response_path,
    fail_api_error,
    quote_resource_path,
    sanitize_data,
)


def run_module(module: AnsibleModule, client: ElasticsearchClient | None = None) -> None:
    """Reconcile the requested generic object."""
    client = client or ElasticsearchClient(module)
    params = module.params
    resource_path = quote_resource_path(params["path"], params.get("id"))
    read_response = client.request(
        resource_path,
        method=params["get_method"],
        query=params["query"],
    )
    exists = read_response.status not in params["not_found_codes"]
    if exists and read_response.status not in params["get_success_codes"]:
        fail_api_error(
            module,
            operation="read",
            path=resource_path,
            response=read_response,
            success_codes=params["get_success_codes"],
            sensitive_fields=params["sensitive_fields"],
        )

    current = (
        extract_response_path(read_response.data, params.get("response_path"))
        if exists
        else None
    )
    state = params["state"]
    if state == "absent":
        diff = {
            "before": sanitize_data(
                current if exists else {},
                params["sensitive_fields"],
            ),
            "after": {},
        }
        if not exists:
            module.exit_json(changed=False, object=None, status=read_response.status, diff=diff)
        if module.check_mode:
            module.exit_json(
                changed=True,
                object=sanitize_data(current, params["sensitive_fields"]),
                status=read_response.status,
                diff=diff,
            )
        response = client.request(
            resource_path,
            method=params["delete_method"],
            query=params["query"],
        )
        if response.status not in params["delete_success_codes"]:
            fail_api_error(
                module,
                operation="delete",
                path=resource_path,
                response=response,
                success_codes=params["delete_success_codes"],
                sensitive_fields=params["sensitive_fields"],
            )
        module.exit_json(
            changed=True,
            object=sanitize_data(current, params["sensitive_fields"]),
            status=response.status,
            diff=diff,
        )

    desired = params["payload"]
    if exists:
        changed, diff = compare_objects(
            current,
            desired,
            compare_fields=params["compare_fields"],
            ignore_fields=params["ignore_fields"],
            sensitive_fields=params["sensitive_fields"],
            unordered_lists=params["unordered_lists"],
        )
    else:
        changed = True
        diff = {
            "before": {},
            "after": sanitize_data(desired, params["sensitive_fields"]),
        }

    if not changed:
        module.exit_json(
            changed=False,
            object=sanitize_data(current, params["sensitive_fields"]),
            status=read_response.status,
            diff=diff,
        )
    if module.check_mode:
        module.exit_json(
            changed=True,
            object=sanitize_data(desired, params["sensitive_fields"]),
            status=read_response.status,
            diff=diff,
        )

    operation = "update" if exists else "create"
    method = params["update_method"] if exists else params["create_method"]
    success_codes = (
        params["update_success_codes"] if exists else params["create_success_codes"]
    )
    mutation_path = resource_path
    if not exists and params.get("create_path"):
        mutation_path = quote_resource_path(params["create_path"], params.get("id"))
    response = client.request(
        mutation_path,
        method=method,
        data=desired,
        query=params["query"],
    )
    if response.status not in success_codes:
        fail_api_error(
            module,
            operation=operation,
            path=mutation_path,
            response=response,
            success_codes=success_codes,
            sensitive_fields=params["sensitive_fields"],
        )

    managed = extract_response_path(response.data, params.get("response_path"))
    if not response.is_async:
        refreshed = client.request(
            resource_path,
            method=params["get_method"],
            query=params["query"],
        )
        if refreshed.status in params["get_success_codes"]:
            managed = extract_response_path(refreshed.data, params.get("response_path"))
    if managed is None:
        managed = desired
    module.exit_json(
        changed=True,
        object=sanitize_data(managed, params["sensitive_fields"]),
        status=response.status,
        diff=diff,
    )


def object_argument_spec() -> dict:
    """Return the generic object argument specification."""
    argument_spec = elasticsearch_argument_spec()
    argument_spec.update(
        path=dict(type="str", required=True),
        id=dict(type="str"),
        payload=dict(type="dict"),
        query=dict(type="dict", default={}),
        create_path=dict(type="str"),
        get_method=dict(type="str", choices=["GET", "POST"], default="GET"),
        create_method=dict(
            type="str",
            choices=["POST", "PUT", "PATCH"],
            default="PUT",
        ),
        update_method=dict(type="str", choices=["POST", "PUT", "PATCH"], default="PUT"),
        delete_method=dict(type="str", choices=["DELETE", "POST"], default="DELETE"),
        get_success_codes=dict(type="list", elements="int", default=[200]),
        create_success_codes=dict(type="list", elements="int", default=[200, 201, 202]),
        update_success_codes=dict(type="list", elements="int", default=[200, 201, 202]),
        delete_success_codes=dict(type="list", elements="int", default=[200, 202, 204]),
        not_found_codes=dict(type="list", elements="int", default=[404]),
        response_path=dict(type="str"),
        compare_fields=dict(type="list", elements="str", default=[]),
        ignore_fields=dict(type="list", elements="str", default=[]),
        sensitive_fields=dict(type="list", elements="str", default=[]),
        unordered_lists=dict(type="bool", default=False),
    )
    return argument_spec


def main() -> None:
    argument_spec = object_argument_spec()
    module = AnsibleModule(
        argument_spec=argument_spec,
        required_if=[["state", "present", ["payload"]]],
        required_together=elasticsearch_required_together(),
        mutually_exclusive=elasticsearch_mutually_exclusive(),
        supports_check_mode=True,
    )
    run_module(module)


if __name__ == "__main__":
    main()

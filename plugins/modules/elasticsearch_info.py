# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

DOCUMENTATION = r"""
---
module: elasticsearch_info
short_description: Read or list arbitrary Elasticsearch API objects
description:
  - Reads an arbitrary Elasticsearch API endpoint without changing remote state.
  - Can extract a dotted response path and collect offset-based pages.
version_added: "1.0.0"
author:
  - Zupersero (@zupersero)
extends_documentation_fragment:
  - zupersero.elastic.elasticsearch
options:
  path:
    description:
      - Elasticsearch API path to read.
      - Must be relative; absolute, cross-origin, and malformed paths are rejected.
    type: str
    required: true
  query:
    description: Query parameters included in the request.
    type: dict
    default: {}
  response_path:
    description:
      - Optional dotted path returned as I(objects).
      - Required when I(paginate=true), and must resolve to a list on every page.
    type: str
  success_codes:
    description: HTTP status codes accepted as successful.
    type: list
    elements: int
    default: [200]
  paginate:
    description: Collect offset-based pages until a short page is returned.
    type: bool
    default: false
  page_size:
    description: Number of objects requested per page.
    type: int
    default: 100
  max_pages:
    description: Maximum number of pages to request.
    type: int
    default: 100
  offset_parameter:
    description: Query parameter carrying the zero-based item offset.
    type: str
    default: from
  page_size_parameter:
    description: Query parameter carrying the requested page size.
    type: str
    default: size
  sensitive_fields:
    description:
      - Dotted response paths redacted from objects, raw responses, pagination results, and API failures.
      - Paths traverse every list entry when a component names a list of objects.
    type: list
    elements: str
    default: []
notes:
  - This module is read-only and behaves the same in check mode.
  - Values under keys that look like passwords, tokens, credentials, or private keys are redacted.
"""

EXAMPLES = r"""
- name: Read Elasticsearch distribution and version information
  zupersero.elastic.elasticsearch_info:
    path: /
  register: elasticsearch_root

- name: List documents with offset pagination
  zupersero.elastic.elasticsearch_info:
    path: application-state/_search
    response_path: hits.hits
    paginate: true
    page_size: 50
    query:
      track_total_hits: true
"""

RETURN = r"""
objects:
  description: Extracted response value, or the complete response when I(response_path) is omitted.
  returned: always
  type: raw
response:
  description: Sanitized raw response, or a list of raw page responses when pagination is enabled.
  returned: always
  type: raw
status:
  description: HTTP status from the request or final page.
  returned: always
  type: int
"""

from ansible.module_utils.basic import AnsibleModule  # noqa: E402

from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch import (  # noqa: E402
    ElasticsearchClient,
    elasticsearch_argument_spec,
    elasticsearch_mutually_exclusive,
    elasticsearch_required_together,
    extract_response_path,
    fail_api_error,
    sanitize_data,
)


def run_module(module: AnsibleModule, client: ElasticsearchClient | None = None) -> None:
    """Read the configured endpoint."""
    client = client or ElasticsearchClient(module)
    params = module.params
    if params["paginate"]:
        if not params.get("response_path"):
            module.fail_json(msg="response_path is required when paginate=true")
        objects, responses, status = client.paginate(
            params["path"],
            response_path=params["response_path"],
            query=params["query"],
            page_size=params["page_size"],
            max_pages=params["max_pages"],
            offset_parameter=params["offset_parameter"],
            page_size_parameter=params["page_size_parameter"],
            sensitive_fields=params["sensitive_fields"],
        )
        if status not in params["success_codes"]:
            from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch import (  # noqa: PLC0415
                ElasticsearchResponse,
            )

            fail_api_error(
                module,
                operation="list",
                path=params["path"],
                response=ElasticsearchResponse(status, responses[-1], {}),
                success_codes=params["success_codes"],
                sensitive_fields=params["sensitive_fields"],
            )
        module.exit_json(
            changed=False,
            objects=sanitize_data(objects, params["sensitive_fields"]),
            response=sanitize_data(responses, params["sensitive_fields"]),
            status=status,
        )

    response = client.request(params["path"], query=params["query"])
    if response.status not in params["success_codes"]:
        fail_api_error(
            module,
            operation="read",
            path=params["path"],
            response=response,
            success_codes=params["success_codes"],
            sensitive_fields=params["sensitive_fields"],
        )
    sanitized_response = sanitize_data(
        response.data,
        params["sensitive_fields"],
    )
    objects = extract_response_path(
        sanitized_response,
        params.get("response_path"),
    )
    module.exit_json(
        changed=False,
        objects=objects,
        response=sanitized_response,
        status=response.status,
    )


def main() -> None:
    argument_spec = elasticsearch_argument_spec()
    argument_spec.pop("state", None)
    argument_spec.update(
        path=dict(type="str", required=True),
        query=dict(type="dict", default={}),
        response_path=dict(type="str"),
        success_codes=dict(type="list", elements="int", default=[200]),
        paginate=dict(type="bool", default=False),
        page_size=dict(type="int", default=100),
        max_pages=dict(type="int", default=100),
        offset_parameter=dict(type="str", default="from"),
        page_size_parameter=dict(type="str", default="size"),
        sensitive_fields=dict(type="list", elements="str", default=[]),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        required_together=elasticsearch_required_together(),
        mutually_exclusive=elasticsearch_mutually_exclusive(),
        supports_check_mode=True,
    )
    if module.params["page_size"] < 1:
        module.fail_json(msg="page_size must be greater than zero")
    if module.params["max_pages"] < 1:
        module.fail_json(msg="max_pages must be greater than zero")
    run_module(module)


if __name__ == "__main__":
    main()

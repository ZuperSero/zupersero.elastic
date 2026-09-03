# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

DOCUMENTATION = r"""
---
module: elasticsearch_request
short_description: Send a non-resource Elasticsearch API request
description:
  - Sends arbitrary Elasticsearch API actions without claiming resource idempotency.
  - Safe HTTP methods always report unchanged. Other methods report changed when executed or predicted in check mode.
version_added: "1.0.0"
author:
  - Zupersero (@zupersero)
extends_documentation_fragment:
  - zupersero.elastic.elasticsearch
options:
  path:
    description:
      - Elasticsearch API path.
      - Must be relative; absolute, cross-origin, and malformed paths are rejected.
    type: str
    required: true
  method:
    description: HTTP method to send.
    type: str
    choices: [GET, HEAD, OPTIONS, POST, PUT, PATCH, DELETE]
    default: GET
  body:
    description: Optional JSON-compatible request body, text, or byte string.
    type: raw
  query:
    description: Query parameters. List values are encoded as repeated parameters.
    type: dict
    default: {}
  success_codes:
    description: HTTP status codes accepted as successful.
    type: list
    elements: int
    default: [200, 201, 202, 204]
  response_path:
    description: Optional dotted path to extract from the response.
    type: str
  sensitive_fields:
    description:
      - Dotted response paths redacted from successful output and API failures.
      - Paths traverse every list entry when a component names a list of objects.
    type: list
    elements: str
    default: []
notes:
  - Mutating requests are skipped in check mode because arbitrary actions cannot be safely simulated.
  - Mutating requests are retried only when I(retry_mutating_requests=true).
  - Values under keys that look like passwords, tokens, credentials, or private keys are redacted.
"""

EXAMPLES = r"""
- name: Read cluster health
  zupersero.elastic.elasticsearch_request:
    path: _cluster/health
    query:
      level: indices
  register: cluster_health

- name: Trigger a snapshot
  zupersero.elastic.elasticsearch_request:
    path: _snapshot/backups/nightly
    method: PUT
    body:
      indices: logs-*
    success_codes: [200, 202]
"""

RETURN = r"""
response:
  description: Sanitized parsed response, optionally extracted with I(response_path).
  returned: always
  type: raw
status:
  description: HTTP status, or C(null) for a mutating request skipped in check mode.
  returned: always
  type: int
"""

from ansible.module_utils.basic import AnsibleModule  # noqa: E402

from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch import (  # noqa: E402
    SAFE_METHODS,
    ElasticsearchClient,
    elasticsearch_argument_spec,
    elasticsearch_mutually_exclusive,
    elasticsearch_required_together,
    extract_response_path,
    fail_api_error,
    sanitize_data,
)


def run_module(module: AnsibleModule, client: ElasticsearchClient | None = None) -> None:
    """Execute the configured request."""
    client = client or ElasticsearchClient(module)
    params = module.params
    method = params["method"]
    changed = method not in SAFE_METHODS
    if module.check_mode and changed:
        module.exit_json(changed=True, response=None, status=None)

    response = client.request(
        params["path"],
        method=method,
        data=params.get("body"),
        query=params["query"],
    )
    if response.status not in params["success_codes"]:
        fail_api_error(
            module,
            operation=method.lower(),
            path=params["path"],
            response=response,
            success_codes=params["success_codes"],
            sensitive_fields=params["sensitive_fields"],
        )
    sanitized_response = sanitize_data(
        response.data,
        params["sensitive_fields"],
    )
    result = extract_response_path(
        sanitized_response,
        params.get("response_path"),
    )
    module.exit_json(
        changed=changed,
        response=result,
        status=response.status,
    )


def main() -> None:
    argument_spec = elasticsearch_argument_spec()
    argument_spec.pop("state", None)
    argument_spec.update(
        path=dict(type="str", required=True),
        method=dict(
            type="str",
            choices=["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"],
            default="GET",
        ),
        body=dict(type="raw"),
        query=dict(type="dict", default={}),
        success_codes=dict(type="list", elements="int", default=[200, 201, 202, 204]),
        response_path=dict(type="str"),
        sensitive_fields=dict(type="list", elements="str", default=[]),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        required_together=elasticsearch_required_together(),
        mutually_exclusive=elasticsearch_mutually_exclusive(),
        supports_check_mode=True,
    )
    run_module(module)


if __name__ == "__main__":
    main()

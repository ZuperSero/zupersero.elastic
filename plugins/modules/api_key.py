# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+
from __future__ import annotations
# ruff: noqa: E402

DOCUMENTATION = r"""
---
module: api_key
short_description: Manage an Elasticsearch security API key
description:
  - Creates, updates, or invalidates an API key identified by I(id).
  - Key material is returned only by a successful create operation.
version_added: "1.0.0"
author: [Zupersero (@zupersero)]
extends_documentation_fragment: [zupersero.elastic.elasticsearch]
options:
  id: {description: Existing API key identifier. Omit to create a key., type: str}
  name: {description: API key name., type: str}
  expiration: {description: Expiration duration accepted by Elasticsearch. Applies during creation., type: str}
  role_descriptors: {description: Privileges granted to the key., type: dict}
  metadata: {description: Arbitrary key metadata., type: dict}
  state: {description: Whether the key should be active., type: str, choices: [present, absent], default: present}
notes:
  - The connection I(api_key) option authenticates the request and is distinct from the managed key returned as C(encoded).
"""
EXAMPLES = r"""
- name: Create a monitoring key
  zupersero.elastic.api_key:
    name: monitoring
    expiration: 30d
    role_descriptors:
      monitoring: {cluster: [monitor], indices: []}
  register: created_key
- name: Invalidate a key
  zupersero.elastic.api_key: {id: "{{ old_key_id }}", state: absent}
"""
RETURN = r"""
api_key_result: {description: Current or predicted API key metadata without secret material., returned: always, type: dict}
id: {description: Managed API key identifier., returned: when known, type: str}
api_key_secret: {description: Secret returned once when a key is created., returned: on creation, type: str}
encoded: {description: Encoded credential returned once when a key is created., returned: on creation, type: str}
status: {description: HTTP status code., returned: always, type: int}
diff: {description: State before and after reconciliation., returned: always, type: dict}
"""

import copy  # noqa: E402
from typing import Any, Mapping  # noqa: E402

from ansible.module_utils.basic import AnsibleModule  # noqa: E402
from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch import (
    ElasticsearchClient,
    elasticsearch_argument_spec,
    elasticsearch_mutually_exclusive,
    elasticsearch_required_together,
    fail_api_error,
    sanitize_data,
)  # noqa: E402


def _managed(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if not value:
        return {}
    return {
        key: copy.deepcopy(value[key])
        for key in ("id", "name", "role_descriptors", "metadata", "invalidated")
        if key in value
    }


def run_module(
    module: AnsibleModule, client: ElasticsearchClient | None = None
) -> None:
    client = client or ElasticsearchClient(module)
    key_id = module.params.get("id")
    response = None
    current = None
    if key_id:
        response, current = client.api_keys.get(key_id)
        if response.status != 200:
            fail_api_error(
                module,
                operation="read API key",
                path=client.api_keys.path,
                response=response,
                success_codes=[200],
            )
        if current is None and module.params["state"] == "present":
            module.fail_json(
                msg=f"API key {key_id!r} was not found; omit id to create a new key"
            )
    elif module.params["state"] == "present" and module.params.get("name"):
        response, matches = client.api_keys.find_by_name(module.params["name"])
        if response.status != 200:
            fail_api_error(
                module,
                operation="find API key by name",
                path=client.api_keys.path,
                response=response,
                success_codes=[200],
            )
        if len(matches) > 1:
            module.fail_json(
                msg=f"multiple active API keys named {module.params['name']!r} exist; specify id"
            )
        if matches:
            current = matches[0]
            key_id = current.get("id")
    current_state = _managed(current)
    if module.params["state"] == "absent":
        if not key_id:
            module.fail_json(msg="id is required when state is absent")
        exists = bool(current and not current.get("invalidated"))
        diff = {"before": sanitize_data(current_state), "after": {}}
        if not exists or module.check_mode:
            module.exit_json(
                changed=exists,
                api_key_result=current_state or None,
                id=key_id,
                status=response.status,
                diff=diff,
            )
        mutation = client.api_keys.invalidate(key_id)
        if mutation.status != 200:
            fail_api_error(
                module,
                operation="invalidate API key",
                path=client.api_keys.path,
                response=mutation,
                success_codes=[200],
            )
        module.exit_json(
            changed=True,
            api_key_result=current_state,
            id=key_id,
            status=mutation.status,
            diff=diff,
        )

    if current is None and not module.params.get("name"):
        module.fail_json(msg="name is required when creating an API key")
    desired = {
        key: copy.deepcopy(module.params[key])
        for key in ("name", "role_descriptors", "metadata")
        if module.params.get(key) is not None
    }
    if current:
        desired.setdefault("name", current.get("name"))
        desired.setdefault("role_descriptors", current.get("role_descriptors", {}))
        desired.setdefault("metadata", current.get("metadata", {}))
    desired_compare = dict(desired)
    if key_id:
        desired_compare["id"] = key_id
    changed = current is None or any(
        current_state.get(key) != value for key, value in desired_compare.items()
    )
    diff = {
        "before": sanitize_data(current_state),
        "after": sanitize_data(desired_compare),
    }
    if not changed or module.check_mode:
        module.exit_json(
            changed=changed,
            api_key_result=desired_compare if changed else current_state,
            id=key_id,
            status=response.status if response else 0,
            diff=diff,
        )
    if current:
        payload = {key: value for key, value in desired.items() if key != "name"}
        mutation = client.api_keys.update(key_id, payload)
        expected = [200]
    else:
        payload = desired
        if module.params.get("expiration") is not None:
            payload["expiration"] = module.params["expiration"]
        mutation = client.api_keys.create(payload)
        expected = [200, 201]
    if mutation.status not in expected or not isinstance(mutation.data, Mapping):
        fail_api_error(
            module,
            operation="write API key",
            path=client.api_keys.path,
            response=mutation,
            success_codes=expected,
            sensitive_fields=["api_key", "encoded"],
        )
    result = _managed(mutation.data) or desired_compare
    output = dict(
        changed=True,
        api_key_result=sanitize_data(result),
        id=mutation.data.get("id", key_id),
        status=mutation.status,
        diff=diff,
    )
    if current is None:
        output["api_key_secret"] = mutation.data.get("api_key")
        output["encoded"] = mutation.data.get("encoded")
    module.exit_json(**output)


def main() -> None:
    spec = elasticsearch_argument_spec()
    spec.update(
        id=dict(type="str"),
        name=dict(type="str"),
        expiration=dict(type="str"),
        role_descriptors=dict(type="dict", no_log=False),
        metadata=dict(type="dict"),
    )
    module = AnsibleModule(
        argument_spec=spec,
        required_together=elasticsearch_required_together(),
        mutually_exclusive=elasticsearch_mutually_exclusive(),
        supports_check_mode=True,
    )
    run_module(module)


if __name__ == "__main__":
    main()

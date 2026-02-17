# Copyright (c) 2025, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

DOCUMENTATION = r'''
---
module: data_view
short_description: Manage Kibana Data Views
description:
  - Create, update, or delete Kibana Data Views.
version_added: "1.0.0"
author:
  - Zupersero (@zupersero)
options:
  id:
    description:
      - The unique identifier for the data view.
    type: str
    required: true
  name:
    description:
      - The display name for the data view.
    type: str
  title:
    description:
      - The index pattern (title) for the data view.
      - Mutually exclusive with I(index_pattern).
    type: str
  index_pattern:
    description:
      - Alias for I(title).
    type: str
  time_field:
    description:
      - The time field name for the data view.
    type: str
  state:
    description:
      - Whether the data view should exist or not.
    choices: [ present, absent ]
    default: present
    type: str
'''

EXAMPLES = r'''
- name: Create a data view
  zupersero.elastic.data_view:
    id: "logs-view"
    name: "Logs"
    title: "logs-*"
    time_field: "@timestamp"
    state: present

- name: Delete a data view
  zupersero.elastic.data_view:
    id: "logs-view"
    state: absent
'''

RETURN = r'''
data_view:
  description: The data view object as returned by Kibana.
  returned: when state=present or state=absent
  type: dict
'''

from typing import Any  # noqa: E402

from ansible.module_utils.basic import AnsibleModule  # noqa: E402
from ansible.module_utils.common.dict_transformations import recursive_diff  # noqa: E402


def build_data_view_payload(module: AnsibleModule, include_id: bool = True) -> dict[str, Any]:
    """
    Build the data view payload for Kibana API.
    """
    title = module.params.get('index_pattern') or module.params.get('title')
    data_view = {
        'name': module.params['name'],
        'title': title,
    }
    if include_id:
        data_view['id'] = module.params['id']
    if module.params.get('time_field'):
        data_view['timeFieldName'] = module.params['time_field']
    return {'data_view': data_view}


def normalize_data_view(data_view: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize data view data for idempotency checks.
    """
    if 'data_view' in data_view:
        data_view = data_view.get('data_view', {})
    return {
        'id': data_view.get('id'),
        'name': data_view.get('name'),
        'title': data_view.get('title'),
        'timeFieldName': data_view.get('timeFieldName'),
    }


def enrich_data_view_output(data_view: dict[str, Any]) -> dict[str, Any]:
    """
    Enrich output to include indexPattern alias when possible.
    """
    if 'data_view' in data_view:
        data_view = data_view.get('data_view', {})
    if 'indexPattern' not in data_view and data_view.get('title') is not None:
        data_view = data_view.copy()
        data_view['indexPattern'] = data_view.get('title')
    return data_view


def main() -> None:
    from ansible_collections.zupersero.elastic.plugins.module_utils import kibana

    argument_spec = kibana.kibana_argument_spec()
    argument_spec.update(
        id=dict(type='str', required=True),
        name=dict(type='str', required=False),
        title=dict(type='str', required=False),
        index_pattern=dict(type='str', required=False),
        time_field=dict(type='str', required=False),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_together=kibana.kibana_required_together(),
        mutually_exclusive=kibana.kibana_mutually_exclusive(),
    )

    state = module.params['state']
    if state == 'present':
        if not module.params.get('name'):
            module.fail_json(msg="`name` is required when state is `present`")
        if not (module.params.get('title') or module.params.get('index_pattern')):
            module.fail_json(msg="Either `title` or `index_pattern` is required when state is `present`")
        if not module.params.get('time_field'):
            module.fail_json(msg="`time_field` is required when state is `present`")

    client = kibana.KibanaClient(module)
    data_view_id = module.params['id']

    status_code, current_data_view = client.data_views.get(data_view_id)
    data_view_exists = status_code == 200

    result = {
        'changed': False,
    }

    if state == 'present':
        desired_payload = build_data_view_payload(module, include_id=True)

        if not data_view_exists:
            result['changed'] = True
            if module.check_mode:
                result['data_view'] = enrich_data_view_output(desired_payload)
                module.exit_json(**result)

            status_code, created = client.data_views.create(desired_payload)
            if status_code not in [200, 201]:
                module.fail_json(msg=f"Failed to create data view: {created.get('error', 'Unknown error')}")

            result['data_view'] = enrich_data_view_output(created or {})
        else:
            current_normalized = normalize_data_view(current_data_view or {})
            desired_normalized = normalize_data_view(desired_payload)

            diff = recursive_diff(current_normalized, desired_normalized)
            if diff:
                result['changed'] = True
                if module.check_mode:
                    result['data_view'] = enrich_data_view_output(desired_payload)
                    module.exit_json(**result)

                update_payload = build_data_view_payload(module, include_id=False)
                status_code, updated = client.data_views.update(data_view_id, update_payload)
                if status_code != 200:
                    module.fail_json(msg=f"Failed to update data view: {updated.get('error', 'Unknown error')}")

                result['data_view'] = enrich_data_view_output(updated or {})
            else:
                result['data_view'] = enrich_data_view_output(current_data_view or {})

    elif state == 'absent':
        if data_view_exists:
            result['changed'] = True
            if module.check_mode:
                result['data_view'] = {'id': data_view_id}
                module.exit_json(**result)

            status_code, response = client.data_views.delete(data_view_id)
            if status_code not in [200, 204]:
                module.fail_json(msg=f"Failed to delete data view: {response.get('error', 'Unknown error')}")

        result['data_view'] = {'id': data_view_id}

    module.exit_json(**result)


if __name__ == '__main__':
    main()

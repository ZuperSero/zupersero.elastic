# Copyright (c) 2025, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

DOCUMENTATION = r'''
---
module: user_role
short_description: Manage Elasticsearch security roles
description:
  - Create, update, or delete roles via the Elasticsearch C(_security/role) API.
  - Idempotently reconciles cluster, index, application, and run-as privileges along with metadata.
version_added: "1.0.0"
author:
  - Zupersero (@zupersero)
options:
  name:
    description:
      - Name of the role to manage.
    required: true
    type: str
  cluster:
    description:
      - Cluster privileges to assign.
    required: false
    type: list
    elements: str
  indices:
    description:
      - Index privilege assignments.
    required: false
    type: list
    elements: dict
    suboptions:
      names:
        description:
          - Index or index pattern names.
        required: true
        type: list
        elements: str
      privileges:
        description:
          - Privileges for the listed indices.
        required: true
        type: list
        elements: str
      field_security:
        description:
          - Field-level security settings.
        required: false
        type: dict
      query:
        description:
          - Document-level security query.
        required: false
        type: str
      allow_restricted_indices:
        description:
          - Whether to allow access to restricted indices.
        required: false
        type: bool
        default: false
  applications:
    description:
      - Application privilege assignments.
    required: false
    type: list
    elements: dict
    suboptions:
      application:
        description:
          - Application name.
        required: true
        type: str
      privileges:
        description:
          - Privileges for the application.
        required: true
        type: list
        elements: str
      resources:
        description:
          - Resource identifiers.
        required: true
        type: list
        elements: str
  run_as:
    description:
      - Users that can be impersonated via the run-as mechanism.
    required: false
    type: list
    elements: str
  metadata:
    description:
      - Arbitrary metadata to attach to the role.
    required: false
    type: dict
  transient_metadata:
    description:
      - Transient metadata such as the enabled flag.
    required: false
    type: dict
  global_privileges:
    description:
      - Global privileges definition.
    required: false
    type: dict
  state:
    description:
      - Whether the role should exist.
    choices: [ present, absent ]
    default: present
    type: str
  url:
    description:
      - URL of the Elasticsearch instance.
      - Can also be set via the ELASTICSEARCH_URL environment variable.
    required: false
    type: str
  username:
    description:
      - Username for authenticating to Elasticsearch.
      - Can also be set via the ELASTICSEARCH_USERNAME environment variable.
    required: false
    type: str
  password:
    description:
      - Password for authenticating to Elasticsearch.
      - Can also be set via the ELASTICSEARCH_PASSWORD environment variable.
    required: false
    type: str
  api_key:
    description:
      - API key for authenticating to Elasticsearch.
      - Can also be set via the ELASTICSEARCH_API_KEY environment variable.
    required: false
    type: str
  validate_certs:
    description:
      - Whether to validate SSL certificates.
      - Can also be set via the ELASTICSEARCH_VALIDATE_CERTS environment variable.
    type: bool
    default: true
  client_cert:
    description:
      - PEM-formatted client certificate chain.
    type: path
  client_key:
    description:
      - PEM-formatted private key for the client certificate.
    type: path
  force_basic_auth:
    description:
      - Send the basic authentication header with the initial request.
    type: bool
    default: false
  url_username:
    description:
      - Username embedded in URL authentication.
    type: str
  url_password:
    description:
      - Password embedded in URL authentication.
    type: str
  timeout:
    description:
      - Timeout in seconds for API requests.
    type: int
    default: 30
  retries:
    description:
      - Number of times to retry failed requests.
    type: int
    default: 3
  retry_pause:
    description:
      - Seconds to wait between retry attempts.
    type: float
    default: 1.0
requirements:
  - ansible.module_utils.urls
notes:
  - Authentication uses I(api_key) or I(username)+I(password).
'''

EXAMPLES = r'''
- name: Create a role with cluster and index privileges
  zupersero.elastic.user_role:
    url: http://localhost:9200
    username: elastic
    password: changeme
    name: data_reader
    cluster:
      - monitor
    indices:
      - names: [ "logs-*" ]
        privileges: [ "read" ]
        allow_restricted_indices: false

- name: Manage application privileges
  zupersero.elastic.user_role:
    url: http://localhost:9200
    username: elastic
    password: changeme
    name: kibana_reader
    applications:
      - application: kibana-.kibana
        privileges: [ "read" ]
        resources: [ "*" ]
    run_as:
      - analyst
    state: present

- name: Delete a role
  zupersero.elastic.user_role:
    url: http://localhost:9200
    username: elastic
    password: changeme
    name: old_role
    state: absent
'''

RETURN = r'''
role:
  description: The role object returned by Elasticsearch.
  returned: always
  type: dict
changed:
  description: Whether any change was made.
  returned: always
  type: bool
'''

from typing import Any  # noqa: E402
import json  # noqa: E402

from ansible_collections.zupersero.elastic.plugins.module_utils import elasticsearch  # noqa: E402
from ansible.module_utils.basic import AnsibleModule  # noqa: E402
from ansible.module_utils.common.dict_transformations import recursive_diff  # noqa: E402


def _normalize_list_of_dicts(items: list[dict]) -> list[dict]:
    """
    Normalize a list of dictionaries for comparison.
    """
    normalized_items: list[dict] = []
    for item in items:
        entry = dict(item)
        names = entry.pop('names', entry.pop('index', None))
        if names is not None:
            entry['names'] = sorted(names)

        privileges = entry.get('privileges')
        if privileges is not None:
            entry['privileges'] = sorted(privileges)

        resources = entry.get('resources')
        if resources is not None:
            entry['resources'] = sorted(resources)

        allow_restricted = entry.get('allow_restricted_indices')
        if allow_restricted is not None:
            entry['allow_restricted_indices'] = bool(allow_restricted)

        normalized_items.append(entry)

    return sorted(normalized_items, key=lambda x: json.dumps(x, sort_keys=True))


def normalize_role_data(role_data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize role data for comparison.
    """
    normalized = {
        'name': role_data.get('name') or '',
        'cluster': sorted(role_data.get('cluster', [])),
        'run_as': sorted(role_data.get('run_as', []) or role_data.get('runAs', [])),
        'indices': _normalize_list_of_dicts(role_data.get('indices') or []),
        'applications': _normalize_list_of_dicts(role_data.get('applications') or []),
        'metadata': role_data.get('metadata') or {},
    }

    transient_meta = role_data.get('transient_metadata')
    if transient_meta is None:
        transient_meta = role_data.get('transientMetadata')
    normalized['transient_metadata'] = transient_meta or {}

    if 'global' in role_data:
        normalized['global'] = role_data.get('global') or role_data.get('global_privileges', {})

    return normalized


def _strip_none_values(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Remove keys with None values from list entries.
    """
    cleaned: list[dict[str, Any]] = []
    for entry in items:
        cleaned.append({key: value for key, value in entry.items() if value is not None})
    return cleaned


def build_desired_role(module: AnsibleModule, current_role: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Build the desired role payload and comparison dict.

    Returns:
        tuple: (payload_for_api, desired_role_state)
    """
    params = module.params

    def resolve(field: str, default: Any, alt_keys: tuple[str, ...] = ()) -> Any:
        value = params.get(field)
        if value is not None:
            return value
        if current_role:
            for key in (field, *alt_keys):
                if key in current_role:
                    return current_role.get(key)
        return default

    desired_state = {
        'name': params['name'],
        'cluster': resolve('cluster', []),
        'indices': resolve('indices', []),
        'applications': resolve('applications', []),
        'run_as': resolve('run_as', []),
        'metadata': resolve('metadata', {}),
        'transient_metadata': resolve('transient_metadata', {'enabled': True}, ('transientMetadata',)),
    }

    global_privileges = resolve('global_privileges', None, ('global',))
    if global_privileges is not None:
        desired_state['global'] = global_privileges

    cleaned_indices = _strip_none_values(desired_state['indices'])
    cleaned_applications = _strip_none_values(desired_state['applications'])
    desired_state['indices'] = cleaned_indices
    desired_state['applications'] = cleaned_applications

    payload: dict[str, Any] = {
        'cluster': desired_state['cluster'],
        'indices': cleaned_indices,
        'applications': cleaned_applications,
        'run_as': desired_state['run_as'],
        'metadata': desired_state['metadata'],
        'transient_metadata': desired_state['transient_metadata'],
    }

    if global_privileges is not None:
        payload['global'] = global_privileges

    return payload, desired_state


def main() -> None:
    argument_spec = elasticsearch.elasticsearch_argument_spec()

    argument_spec.update(
        name=dict(type='str', required=True),
        cluster=dict(type='list', elements='str', required=False, default=None),
        indices=dict(
            type='list',
            elements='dict',
            required=False,
            default=None,
            options=dict(
                names=dict(type='list', elements='str', required=True),
                privileges=dict(type='list', elements='str', required=True),
                field_security=dict(type='dict', required=False, default=None),
                query=dict(type='str', required=False, default=None),
                allow_restricted_indices=dict(type='bool', required=False, default=False),
            ),
        ),
        applications=dict(
            type='list',
            elements='dict',
            required=False,
            default=None,
            options=dict(
                application=dict(type='str', required=True),
                privileges=dict(type='list', elements='str', required=True),
                resources=dict(type='list', elements='str', required=True),
            ),
        ),
        run_as=dict(type='list', elements='str', required=False, default=None),
        metadata=dict(type='dict', required=False, default=None),
        transient_metadata=dict(type='dict', required=False, default=None),
        global_privileges=dict(type='dict', required=False, default=None),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=elasticsearch.elasticsearch_required_if(),
        required_together=elasticsearch.elasticsearch_required_together(),
        mutually_exclusive=elasticsearch.elasticsearch_mutually_exclusive(),
    )

    role_name = module.params['name']
    state = module.params['state']

    client = elasticsearch.ElasticsearchClient(module)

    status_code, current_role = client.role.get(role_name)
    role_exists = status_code == 200

    result: dict[str, Any] = {'changed': False}

    if state == 'present':
        payload, desired_state = build_desired_role(module, current_role if role_exists else None)
        desired_normalized = normalize_role_data(desired_state)

        if not role_exists:
            result['changed'] = True

            if module.check_mode:
                result['role'] = desired_state
                module.exit_json(**result)

            status_code, response = client.role.create_or_update(role_name, payload)
            if status_code not in [200, 201]:
                error_msg = response.get('error', 'Unknown error') if isinstance(response, dict) else 'Unknown error'
                module.fail_json(msg=f"Failed to create role: {error_msg}", status_code=status_code, response=response)

            status_code, created_role = client.role.get(role_name)
            result['role'] = created_role if status_code == 200 else response
        else:
            current_normalized = normalize_role_data(current_role)
            diff = recursive_diff(current_normalized, desired_normalized)

            if diff:
                result['changed'] = True

                if module.check_mode:
                    result['role'] = desired_state
                    module.exit_json(**result)

                status_code, response = client.role.create_or_update(role_name, payload)
                if status_code not in [200, 201]:
                    error_msg = response.get('error', 'Unknown error') if isinstance(response, dict) else 'Unknown error'
                    module.fail_json(msg=f"Failed to update role: {error_msg}", status_code=status_code, response=response, payload=payload)

                status_code, updated_role = client.role.get(role_name)
                result['role'] = updated_role if status_code == 200 else response
            else:
                result['role'] = current_role
    else:
        if role_exists:
            result['changed'] = True
            result['role'] = current_role if isinstance(current_role, dict) else {'name': role_name}

            if module.check_mode:
                module.exit_json(**result)

            status_code, response = client.role.delete(role_name)
            if status_code not in [200, 404]:
                error_msg = response.get('error', 'Unknown error') if isinstance(response, dict) else 'Unknown error'
                module.fail_json(msg=f"Failed to delete role: {error_msg}", status_code=status_code, response=response)

    module.exit_json(**result)


if __name__ == '__main__':
    main()

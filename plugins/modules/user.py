# Copyright (c) 2025, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

DOCUMENTATION = r'''
---
module: user
short_description: Manage Elasticsearch security users
description:
  - Create, update, disable, or delete users via the Elasticsearch C(_security/user) API.
  - Idempotently reconciles roles, contact details, metadata, and enabled state.
  - Passwords are applied on creation only, unless I(update_password=always) is set.
version_added: "1.0.0"
author:
  - Zupersero (@zupersero)
options:
  username:
    description:
      - The Elasticsearch username to manage.
    required: true
    type: str
  password:
    description:
      - Plain-text password for the user.
      - Mutually exclusive with I(password_hash).
      - Applied on creation, or always when I(update_password=always).
    required: false
    type: str
  password_hash:
    description:
      - Pre-hashed password for the user (bcrypt by default in Elasticsearch).
      - Mutually exclusive with I(password).
      - Applied on creation, or always when I(update_password=always).
    required: false
    type: str
  roles:
    description:
      - List of roles to assign.
    required: false
    type: list
    elements: str
  full_name:
    description:
      - Full name for the user.
    required: false
    type: str
  email:
    description:
      - Email address for the user.
    required: false
    type: str
  metadata:
    description:
      - Arbitrary metadata to attach to the user.
    required: false
    type: dict
  enabled:
    description:
      - Whether the user is enabled.
    required: false
    type: bool
  update_password:
    description:
      - Controls when provided passwords are applied.
      - C(on_create) only sets the password when creating the user.
      - C(always) updates the password on every run when provided.
    type: str
    default: on_create
    choices: [ on_create, always ]
  auth_username:
    description:
      - Username for authenticating to Elasticsearch.
      - Can also be set via the ELASTICSEARCH_USERNAME environment variable.
    required: false
    type: str
  auth_password:
    description:
      - Password for authenticating to Elasticsearch.
      - Can also be set via the ELASTICSEARCH_PASSWORD environment variable.
    required: false
    type: str
  auth_api_key:
    description:
      - API key for authenticating to Elasticsearch.
      - Can also be set via the ELASTICSEARCH_API_KEY environment variable.
    required: false
    type: str
  state:
    description:
      - Whether the user should exist.
    choices: [ present, absent ]
    default: present
    type: str
  url:
    description:
      - URL of the Elasticsearch instance.
      - Can also be set via the ELASTICSEARCH_URL environment variable.
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
      - PEM formatted certificate chain file for SSL client authentication.
    type: path
  client_key:
    description:
      - PEM formatted private key file for SSL client authentication.
    type: path
  force_basic_auth:
    description:
      - Force sending basic authentication header on the first request.
    type: bool
    default: false
  url_username:
    description:
      - Username to use for URL-based basic authentication.
    type: str
  url_password:
    description:
      - Password to use for URL-based basic authentication.
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
  - Authentication uses I(auth_api_key) or I(auth_username)+I(auth_password).
  - Passwords are not returned by the API and cannot be read for comparison.
'''

EXAMPLES = r'''
- name: Create a user with a plain password
  zupersero.elastic.user:
    url: http://localhost:9200
    auth_username: elastic
    auth_password: changeme
    username: example_user
    password: s3cret
    roles:
      - superuser
    full_name: Example Managed User
    email: managed@example.com
    metadata:
      owner: platform
    enabled: true

- name: Create a user with a pre-hashed password
  zupersero.elastic.user:
    url: http://localhost:9200
    auth_username: elastic
    auth_password: changeme
    username: hash_user
    # Precomputed bcrypt hash for "password"
    password_hash: "$2b$12$GhvMmNVjRW29ulnudl.LbuAnUtN/LRfe1JsBm1Xu6LE3059z5Tr8m"
    roles:
      - power_user
    update_password: on_create
    state: present

- name: Rotate a password on every run
  zupersero.elastic.user:
    url: http://localhost:9200
    auth_username: elastic
    auth_password: changeme
    username: example_user
    password: "{{ lookup('ansible.builtin.password', '/tmp/new-pass length=20') }}"
    update_password: always
    state: present

- name: Disable a user
  zupersero.elastic.user:
    url: http://localhost:9200
    auth_username: elastic
    auth_password: changeme
    username: example_user
    enabled: false

- name: Delete a user
  zupersero.elastic.user:
    url: http://localhost:9200
    auth_username: elastic
    auth_password: changeme
    username: example_user
    state: absent
'''

RETURN = r'''
user:
  description: The user object returned by Elasticsearch.
  returned: always
  type: dict
  sample:
    username: example_user
    roles:
      - superuser
    full_name: Example Managed User
    email: managed@example.com
    metadata:
      owner: platform
    enabled: true
changed:
  description: Whether any change was made.
  returned: always
  type: bool
'''

from typing import Any  # noqa: E402

from ansible_collections.zupersero.elastic.plugins.module_utils import elasticsearch  # noqa: E402
from ansible.module_utils.basic import AnsibleModule  # noqa: E402
from ansible.module_utils.common.dict_transformations import recursive_diff  # noqa: E402


def normalize_user_data(user_data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize user data for comparison.
    """
    normalized = {
        'username': user_data.get('username'),
        'roles': sorted(user_data.get('roles', [])),
        'full_name': user_data.get('full_name') or user_data.get('fullName') or '',
        'email': user_data.get('email', ''),
        'enabled': user_data.get('enabled', True),
    }

    if 'metadata' in user_data:
        normalized['metadata'] = user_data.get('metadata') or {}

    return normalized


def build_desired_user(module: AnsibleModule, current_user: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Build the desired user payload and comparison dict.

    Returns:
        tuple: (payload_for_api, desired_user_state)
    """
    params = module.params

    def resolve(field: str, default: Any, alt_keys: tuple[str, ...] = ()) -> Any:
        value = params.get(field)
        if value is not None:
            return value
        if current_user:
            for key in (field, *alt_keys):
                if key in current_user:
                    return current_user.get(key)
        return default

    desired_state = {
        'username': params['username'],
        'roles': resolve('roles', [], ()),
        'full_name': resolve('full_name', '', ('fullName',)),
        'email': resolve('email', ''),
        'enabled': resolve('enabled', True),
    }

    payload: dict[str, Any] = {
        'roles': desired_state['roles'],
        'full_name': desired_state['full_name'],
        'email': desired_state['email'],
        'enabled': desired_state['enabled'],
    }

    metadata_value = resolve('metadata', None)
    if metadata_value is None and current_user and 'metadata' in current_user:
        metadata_value = current_user.get('metadata')
    if metadata_value is not None:
        desired_state['metadata'] = metadata_value
        payload['metadata'] = metadata_value

    password = params.get('password')
    password_hash = params.get('password_hash')
    update_password = params.get('update_password')

    if not current_user or update_password == 'always':
        if password is not None:
            payload['password'] = password
        if password_hash is not None:
            payload['password_hash'] = password_hash

    return payload, desired_state


def main() -> None:
    argument_spec = elasticsearch.elasticsearch_argument_spec()

    # Rename auth parameters to avoid collision with managed user fields
    auth_username_spec = argument_spec.pop('username')
    auth_password_spec = argument_spec.pop('password')
    auth_api_key_spec = argument_spec.pop('api_key')

    argument_spec['auth_username'] = auth_username_spec
    argument_spec['auth_password'] = auth_password_spec
    argument_spec['auth_api_key'] = auth_api_key_spec

    argument_spec.update(
        username=dict(type='str', required=True),
        password=dict(type='str', required=False, no_log=True),
        password_hash=dict(type='str', required=False, no_log=True),
        roles=dict(type='list', elements='str', required=False, default=None),
        full_name=dict(type='str', required=False, default=None),
        email=dict(type='str', required=False, default=None),
        metadata=dict(type='dict', required=False, default=None),
        enabled=dict(type='bool', required=False, default=None),
        update_password=dict(type='str', choices=['always', 'on_create'], default='on_create'),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=elasticsearch.elasticsearch_required_if(),
        required_together=elasticsearch.elasticsearch_required_together(),
        mutually_exclusive=[['password', 'password_hash']],
    )

    # Preserve managed user fields before swapping in auth creds for the client
    managed_username = module.params['username']
    managed_password = module.params.get('password')
    managed_password_hash = module.params.get('password_hash')

    auth_username = module.params.get('auth_username')
    auth_password = module.params.get('auth_password')
    auth_api_key = module.params.get('auth_api_key')

    module.params['username'] = auth_username
    module.params['password'] = auth_password
    module.params['api_key'] = auth_api_key

    client = elasticsearch.ElasticsearchClient(module)

    # Restore managed user fields
    module.params['username'] = managed_username
    module.params['password'] = managed_password
    module.params['password_hash'] = managed_password_hash
    module.params['api_key'] = auth_api_key

    username = managed_username
    state = module.params['state']

    status_code, current_user = client.user.get(username)
    user_exists = status_code == 200

    result: dict[str, Any] = {'changed': False}

    if state == 'present':
        if not user_exists and not (module.params.get('password') or module.params.get('password_hash')):
            module.fail_json(msg="Creating a user requires either password or password_hash")

        payload, desired_state = build_desired_user(module, current_user if user_exists else None)
        desired_normalized = normalize_user_data(desired_state)

        if not user_exists:
            result['changed'] = True

            if module.check_mode:
                result['user'] = desired_state
                module.exit_json(**result)

            status_code, response = client.user.create_or_update(username, payload)
            if status_code not in [200, 201]:
                error_msg = response.get('error', 'Unknown error') if isinstance(response, dict) else 'Unknown error'
                module.fail_json(msg=f"Failed to create user: {error_msg}", status_code=status_code, response=response)

            status_code, created_user = client.user.get(username)
            result['user'] = created_user if status_code == 200 else response
        else:
            current_normalized = normalize_user_data(current_user)
            diff = recursive_diff(current_normalized, desired_normalized)

            password_provided = module.params.get('password') is not None or module.params.get('password_hash') is not None
            password_update_needed = password_provided and module.params['update_password'] == 'always'

            if diff or password_update_needed:
                result['changed'] = True

                if module.check_mode:
                    result['user'] = desired_state
                    module.exit_json(**result)

                status_code, response = client.user.create_or_update(username, payload)
                if status_code not in [200, 201]:
                    error_msg = response.get('error', 'Unknown error') if isinstance(response, dict) else 'Unknown error'
                    module.fail_json(msg=f"Failed to update user: {error_msg}", status_code=status_code, response=response, payload=payload)

                status_code, updated_user = client.user.get(username)
                result['user'] = updated_user if status_code == 200 else response
            else:
                result['user'] = current_user
    else:  # state == 'absent'
        if user_exists:
            result['changed'] = True
            result['user'] = current_user if isinstance(current_user, dict) else {'username': username}
            # Preserve username and present a consistent enabled flag for reporting
            if isinstance(result['user'], dict):
                result['user'].setdefault('username', username)
                if result['user'].get('enabled') is False:
                    result['user']['enabled'] = True
                elif 'enabled' not in result['user']:
                    result['user']['enabled'] = True

            if module.check_mode:
                module.exit_json(**result)

            status_code, response = client.user.delete(username)
            if status_code not in [200, 404]:
                error_msg = response.get('error', 'Unknown error') if isinstance(response, dict) else 'Unknown error'
                module.fail_json(msg=f"Failed to delete user: {error_msg}", status_code=status_code, response=response)

        # If the user does not exist, nothing to do

    module.exit_json(**result)


if __name__ == '__main__':
    main()

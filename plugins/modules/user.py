# Copyright (c) 2025, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later
# pylint: disable=disallowed-name

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
  urls:
    description:
      - Elasticsearch URLs used in order for request failover.
      - Can also be set as a comma-separated ELASTICSEARCH_URLS environment variable.
    type: list
    elements: str
  bearer_token:
    description:
      - Bearer token for authenticating to Elasticsearch.
      - Can also be set via the ELASTICSEARCH_BEARER_TOKEN environment variable.
    type: str
  headers:
    description:
      - Additional HTTP headers sent with every request.
      - Can also be set as JSON via the ELASTICSEARCH_HEADERS environment variable.
    type: dict
    default: {}
  validate_certs:
    description:
      - Whether to validate SSL certificates.
      - Can also be set via the ELASTICSEARCH_VALIDATE_CERTS environment variable.
    type: bool
    default: true
  ca_path:
    description:
      - Path to a PEM CA certificate bundle.
      - Can also be set via the ELASTICSEARCH_CA_PATH environment variable.
    type: path
  ca_data:
    description:
      - PEM CA certificate data.
      - Can also be set via the ELASTICSEARCH_CA_DATA environment variable.
    type: str
  client_cert:
    description:
      - PEM formatted certificate chain file for SSL client authentication.
    type: path
  client_key:
    description:
      - PEM formatted private key file for SSL client authentication.
    type: path
  certificate_fingerprint:
    description:
      - SHA-256 fingerprint of the HTTPS server leaf certificate.
      - Uses an unauthenticated TLS preflight and cannot be combined with I(client_cert).
      - Can also be set via the ELASTICSEARCH_CERTIFICATE_FINGERPRINT environment variable.
    type: str
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
  retry_status_codes:
    description:
      - HTTP status codes that trigger endpoint failover and retry for safe read methods.
      - Mutating methods are not retried automatically.
    type: list
    elements: int
    default: [429, 502, 503, 504]
  retry_mutating_requests:
    description:
      - Whether mutating requests can be retried and failed over.
      - Can also be set via the ELASTICSEARCH_RETRY_MUTATING_REQUESTS environment variable.
    type: bool
    default: false
requirements:
  - ansible.module_utils.urls
notes:
  - Authentication uses I(auth_api_key), I(bearer_token), or I(auth_username)+I(auth_password).
  - Passwords are not returned by the API and cannot be read for comparison.
  - Check mode predicts creation, updates, and deletion without sending mutating requests.
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
'''

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


def _desired_user(module: AnsibleModule) -> dict[str, Any]:
    """Build the sparse user fields explicitly set by this task."""
    desired: dict[str, Any] = {}
    for field in ("roles", "full_name", "email", "metadata", "enabled"):
        if module.params.get(field) is not None:
            desired[field] = module.params[field]
    return desired


def _secrets(module: AnsibleModule, *, creating: bool) -> dict[str, Any]:
    """Return password/password_hash to apply on this request, if any."""
    if not creating and module.params["update_password"] != "always":
        return {}
    secrets: dict[str, Any] = {}
    if module.params.get("password") is not None:
        secrets["password"] = module.params["password"]
    if module.params.get("password_hash") is not None:
        secrets["password_hash"] = module.params["password_hash"]
    return secrets


def run_module(
    module: AnsibleModule,
    client: ElasticsearchClient | None = None,
) -> None:
    """Reconcile an Elasticsearch security user."""
    client = client or ElasticsearchClient(module)
    username = module.params["username"]
    state = module.params["state"]

    read_response, current = client.user.get(username)
    if read_response.status not in (200, 404):
        fail_api_error(
            module,
            operation="read user",
            path=client.user.path(username),
            response=read_response,
            success_codes=[200, 404],
        )

    if state == "absent":
        diff = {"before": sanitize_data(current or {}), "after": {}}
        if current is None:
            module.exit_json(changed=False, user=None, diff=diff)
        if module.check_mode:
            module.exit_json(changed=True, user=sanitize_data(current), diff=diff)
        response = client.user.delete(username)
        if response.status not in (200, 404):
            fail_api_error(
                module,
                operation="delete user",
                path=client.user.path(username),
                response=response,
                success_codes=[200, 404],
            )
        module.exit_json(changed=True, user=sanitize_data(current), diff=diff)

    desired = _desired_user(module)
    password = module.params.get("password")
    password_hash = module.params.get("password_hash")

    if current is None:
        if password is None and password_hash is None:
            module.fail_json(msg="Creating a user requires either password or password_hash")

        predicted = client.user.payload(None, desired)
        predicted["username"] = username
        diff = {"before": {}, "after": sanitize_data(predicted)}
        if module.check_mode:
            module.exit_json(changed=True, user=sanitize_data(predicted), diff=diff)

        response = client.user.create_or_update(
            username,
            current=None,
            desired=desired,
            secrets=_secrets(module, creating=True),
        )
        if response.status not in (200, 201):
            fail_api_error(
                module,
                operation="create user",
                path=client.user.path(username),
                response=response,
                success_codes=[200, 201],
            )
        _, current = client.user.get(username)
        module.exit_json(changed=True, user=sanitize_data(current), diff=diff)
        return

    changed, diff = client.user.compare(current, desired)
    password_update_needed = (
        (password is not None or password_hash is not None)
        and module.params["update_password"] == "always"
    )
    changed = changed or password_update_needed

    if not changed:
        module.exit_json(changed=False, user=sanitize_data(current), diff=diff)

    if module.check_mode:
        predicted = client.user.payload(current, desired)
        predicted["username"] = username
        module.exit_json(changed=True, user=sanitize_data(predicted), diff=diff)

    response = client.user.create_or_update(
        username,
        current=current,
        desired=desired,
        secrets=_secrets(module, creating=False),
    )
    if response.status not in (200, 201):
        fail_api_error(
            module,
            operation="update user",
            path=client.user.path(username),
            response=response,
            success_codes=[200, 201],
        )
    _, current = client.user.get(username)
    module.exit_json(changed=True, user=sanitize_data(current), diff=diff)


def main() -> None:
    argument_spec = elasticsearch_argument_spec()

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
        update_password=dict(type='str', choices=['always', 'on_create'], default='on_create', no_log=False),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_together=elasticsearch_required_together(
            username='auth_username',
            password='auth_password',
        ),
        mutually_exclusive=[
            *elasticsearch_mutually_exclusive(
                username='auth_username',
                password='auth_password',
                api_key='auth_api_key',
                bearer_token='bearer_token',
            ),
            ['password', 'password_hash'],
        ],
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

    client = ElasticsearchClient(module)

    # Restore managed user fields
    module.params['username'] = managed_username
    module.params['password'] = managed_password
    module.params['password_hash'] = managed_password_hash
    module.params['api_key'] = auth_api_key

    run_module(module, client)


if __name__ == '__main__':
    main()

# Copyright (c) 2025, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

DOCUMENTATION = r'''
---
module: space
short_description: Manage Kibana Spaces
description:
  - Create, update, or delete Kibana Spaces
  - Kibana Spaces allow you to organize your dashboards, visualizations, and other saved objects into separate collections
  - This module provides idempotent management of Kibana Spaces
version_added: "1.0.0"
author:
  - zupersero
options:
  id:
    description:
      - The unique identifier for the space
      - Must be lowercase and cannot contain spaces
    required: true
    type: str
  name:
    description:
      - The display name for the space
      - If not provided, defaults to the space ID
    required: false
    type: str
  description:
    description:
      - A description for the space
    required: false
    type: str
    default: ''
  disabled_features:
    description:
      - List of Kibana features to disable in this space
      - Common features include 'discover', 'dashboard', 'canvas', 'maps', 'ml', etc.
    required: false
    type: list
    elements: str
    default: []
  state:
    description:
      - Whether the space should exist or not
      - C(present) ensures the space exists with the specified configuration
      - C(absent) ensures the space is deleted
    choices: [ present, absent ]
    default: present
    type: str
  url:
    description:
      - The URL of the Kibana instance
      - Can also be set via the KIBANA_URL environment variable
    required: false
    type: str
  username:
    description:
      - Username for basic authentication
      - Can also be set via the KIBANA_USERNAME environment variable
      - Mutually exclusive with I(api_key)
    required: false
    type: str
  password:
    description:
      - Password for basic authentication
      - Can also be set via the KIBANA_PASSWORD environment variable
      - Required if I(username) is specified
    required: false
    type: str
  api_key:
    description:
      - API key for authentication
      - Can also be set via the KIBANA_API_KEY environment variable
      - Mutually exclusive with I(username) and I(password)
    required: false
    type: str
  validate_certs:
    description:
      - Whether to validate SSL certificates
      - Can also be set via the KIBANA_VALIDATE_CERTS environment variable
    type: bool
    default: true
  timeout:
    description:
      - Timeout in seconds for API requests
    type: int
    default: 30
  retries:
    description:
      - Number of times to retry failed requests
    type: int
    default: 3
  retry_interval:
    description:
      - Seconds to wait between retry attempts
    type: int
    default: 10
requirements:
  - ansible.module_utils.urls
notes:
  - Either I(api_key) or both I(username) and I(password) must be provided for authentication
  - The default space (id='default') cannot be deleted
  - Deleting a space will also delete all saved objects within that space
'''
EXAMPLES = r'''
- name: Create a new space for development team
  zupersero.elastic.space:
    url: https://kibana.example.com
    api_key: "your-api-key-here"
    id: dev-team
    name: Development Team
    description: Space for development team dashboards and visualizations
    state: present

- name: Create a space with disabled features using username/password auth
  zupersero.elastic.space:
    url: https://kibana.example.com
    username: admin
    password: secretpassword
    id: restricted-space
    name: Restricted Space
    description: Space with limited features
    disabled_features:
      - ml
      - canvas
      - maps
    state: present

- name: Update an existing space
  zupersero.elastic.space:
    url: https://kibana.example.com
    api_key: "your-api-key-here"
    id: dev-team
    name: Development Team (Updated)
    description: Updated description for dev team
    state: present

- name: Delete a space
  zupersero.elastic.space:
    url: https://kibana.example.com
    api_key: "your-api-key-here"
    id: old-space
    state: absent

- name: Create space using environment variables for authentication
  zupersero.elastic.space:
    id: prod-team
    name: Production Team
    description: Space for production monitoring
    state: present
  environment:
    KIBANA_URL: https://kibana.example.com
    KIBANA_API_KEY: your-api-key-here

- name: Create space without SSL certificate validation (not recommended for production)
  zupersero.elastic.space:
    url: https://kibana-dev.local
    api_key: "your-api-key-here"
    validate_certs: false
    id: test-space
    name: Test Space
    state: present
'''
RETURN = r'''
space:
  description: The space object as returned by Kibana
  returned: when state=present
  type: dict
  sample:
    id: dev-team
    name: Development Team
    description: Space for development team dashboards and visualizations
    disabledFeatures: []
    _reserved: false
changed:
  description: Whether the space was created, updated, or deleted
  returned: always
  type: bool
  sample: true
diff:
  description: The difference between the current and desired state
  returned: when changed=true and state=present
  type: dict
  sample:
    before:
      id: dev-team
      name: Development Team
      description: Old description
      disabledFeatures: []
    after:
      id: dev-team
      name: Development Team
      description: New description
      disabledFeatures: []
'''

from typing import Any

from ansible_collections.zupersero.elastic.plugins.module_utils import kibana
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.common.dict_transformations import recursive_diff


def build_space_data(module: AnsibleModule) -> dict[str, Any]:
    """
    Build the space data object from module parameters.

    Args:
        module (AnsibleModule): The Ansible module instance

    Returns:
        dict[str, Any]: Space data dictionary with id, name, description, and disabledFeatures
    """
    space_data = {
        'id': module.params['id'],
        'name': module.params.get('name') or module.params['id'],
        'description': module.params.get('description', ''),
        'disabledFeatures': module.params.get('disabled_features', []),
    }
    return space_data


def normalize_space_data(space_data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize space data for comparison.

    This function ensures consistent formatting of space data by:
    - Ensuring disabledFeatures is always a list
    - Sorting disabledFeatures for consistent comparison
    - Removing fields that are not relevant for comparison

    Args:
        space_data (dict[str, Any]): Raw space data from Kibana API

    Returns:
        dict[str, Any]: Normalized space data with consistent structure
    """
    # Ensure disabledFeatures is always a list
    if 'disabledFeatures' not in space_data:
        space_data['disabledFeatures'] = []

    # Remove fields that are not relevant for comparison
    normalized = {
        'id': space_data.get('id'),
        'name': space_data.get('name'),
        'description': space_data.get('description', ''),
        'disabledFeatures': sorted(space_data.get('disabledFeatures', [])),
    }
    return normalized


def main() -> None:
    """
    Main execution function for the space module.

    This function handles the module lifecycle including:
    - Argument parsing and validation
    - Client initialization
    - State management (present/absent)
    - Idempotency checking
    - Check mode support
    - Diff mode support
    """
    argument_spec = kibana.kibana_argument_spec()
    argument_spec.update(
        id=dict(type='str', required=True),
        name=dict(type='str', required=False),
        description=dict(type='str', required=False, default=''),
        disabled_features=dict(type='list', elements='str', required=False, default=[]),
    )
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=kibana.kibana_required_if(),
        required_together=kibana.kibana_required_together(),
        mutually_exclusive=kibana.kibana_mutually_exclusive(),
    )

    # Initialize client
    client = kibana.KibanaClient(module)

    space_id = module.params['id']
    state = module.params['state']

    # Get current space state
    status_code, current_space = client.spaces.get(space_id)
    space_exists = status_code == 200

    result = {
        'changed': False,
    }

    if state == 'present':
        # Build desired space data
        desired_space = build_space_data(module)

        if not space_exists:
            # Space doesn't exist, create it
            result['changed'] = True

            if module.check_mode:
                result['space'] = desired_space
                module.exit_json(**result)

            # Create the space
            status_code, created_space = client.spaces.create(desired_space)

            if status_code not in [200, 201]:
                module.fail_json(msg=f"Failed to create space: {created_space.get('error', 'Unknown error')}")

            result['space'] = created_space
            result['diff'] = {
                'before': {},
                'after': normalize_space_data(created_space)
            }
        else:
            # Space exists, check if update is needed
            current_normalized = normalize_space_data(current_space)
            desired_normalized = normalize_space_data(desired_space)

            # Use recursive_diff to check for differences
            diff = recursive_diff(current_normalized, desired_normalized)

            if diff:
                # Changes detected
                result['changed'] = True
                result['diff'] = {
                    'before': current_normalized,
                    'after': desired_normalized
                }

                if module.check_mode:
                    result['space'] = desired_space
                    module.exit_json(**result)

                # Update the space
                status_code, updated_space = client.spaces.update(space_id, desired_space)

                if status_code != 200:
                    module.fail_json(msg=f"Failed to update space: {updated_space.get('error', 'Unknown error')}")

                result['space'] = updated_space
            else:
                # No changes needed
                result['space'] = current_space

    elif state == 'absent':
        if space_exists:
            # Space exists and should be deleted
            result['changed'] = True

            if module.check_mode:
                module.exit_json(**result)

            # Delete the space
            status_code, response = client.spaces.delete(space_id)

            if status_code not in [200, 204]:
                module.fail_json(msg=f"Failed to delete space: {response.get('error', 'Unknown error') if response else 'Unknown error'}")
        # else: Space doesn't exist, nothing to do

    module.exit_json(**result)


if __name__ == '__main__':
    main()
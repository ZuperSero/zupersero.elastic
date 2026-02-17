# Copyright (c) 2025, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

DOCUMENTATION = r'''
---
module: connector
short_description: Manage Kibana Connectors
description:
  - Create, update, or delete Kibana Connectors for actions.
version_added: "1.0.0"
author:
  - Zupersero (@zupersero)
options:
  id:
    description:
      - The unique identifier for the connector. If not provided, one will be generated.
    type: str
  name:
    description:
      - The display name for the connector.
    required: true
    type: str
  connector_type_id:
    description:
      - The type of connector to create.
    required: true
    type: str
    choices:
      - .email
      - .index
      - .pagerduty
      - .swimlane
      - .server-log
      - .slack
      - .slack_api
      - .webhook
      - .cases-webhook
      - .xmatters
      - .servicenow
      - .servicenow-sir
      - .servicenow-itom
      - .jira
      - .teams
      - .torq
      - .opsgenie
      - .jira-service-management
      - .tines
      - .gen-ai
      - .bedrock
      - .gemini
      - .d3security
      - .resilient
      - .thehive
      - .xsoar
      - .sentinelone
      - .crowdstrike
      - .inference
      - .microsoft_defender_endpoint
  config:
    description:
      - The configuration for the connector. Varies by connector type.
    required: true
    type: dict
  secrets:
    description:
      - The secrets for the connector. Varies by connector type.
    required: false
    type: dict
    no_log: true
  state:
    description:
      - Whether the connector should exist or not.
    choices: [ present, absent ]
    default: present
    type: str
'''

EXAMPLES = r'''
- name: Create an email connector
  zupersero.elastic.connector:
    name: "My Email Connector"
    connector_type_id: ".email"
    config:
      from: "sender@example.com"
      host: "smtp.example.com"
      port: 587
      secure: true
    secrets:
      user: "myuser"
      password: "mypassword"
    state: present

- name: Delete a connector
  zupersero.elastic.connector:
    id: "my-email-connector-id"
    state: absent
'''

RETURN = r'''
connector:
  description: The connector object as returned by Kibana.
  returned: when state=present
  type: dict
  sample:
    id: "d4c6f0e0-2b9a-11eb-a3e6-2d9c8a7b7d7c"
    name: "My Email Connector"
    connector_type_id: ".email"
    config:
      from: "sender@example.com"
      host: "smtp.example.com"
      port: 587
      secure: true
'''

from typing import Any, TypedDict  # noqa: E402


from ansible.module_utils.basic import AnsibleModule  # noqa: E402
from ansible.module_utils.common.dict_transformations import recursive_diff  # noqa: E402


class ConnectorTypeIdEnum:
    """Enum for connector type IDs."""
    email = ".email"
    index = ".index"
    pagerduty = ".pagerduty"
    swimlane = ".swimlane"
    server_log = ".server-log"
    slack = ".slack"
    slack_api = ".slack_api"
    webhook = ".webhook"
    cases_webhook = ".cases-webhook"
    xmatters = ".xmatters"
    servicenow = ".servicenow"
    servicenow_sir = ".servicenow-sir"
    servicenow_itom = ".servicenow-itom"
    jira = ".jira"
    teams = ".teams"
    torq = ".torq"
    opsgenie = ".opsgenie"
    jira_service_management = ".jira-service-management"
    tines = ".tines"
    gen_ai = ".gen-ai"
    bedrock = ".bedrock"
    gemini = ".gemini"
    d3security = ".d3security"
    resilient = ".resilient"
    thehive = ".thehive"
    xsoar = ".xsoar"
    sentinelone = ".sentinelone"
    crowdstrike = ".crowdstrike"
    inference = ".inference"
    microsoft_defender_endpoint = ".microsoft_defender_endpoint"


EmailConfig = TypedDict('EmailConfig',
                         {
                                'clientId': str,
                                'from': str,
                                'hasAuth': bool,
                                'host': str,
                                'oauthTokenUrl': str,
                                'port': int,
                                'secure': bool,
                                'service': str,
                                'tenantId': str,
                         }, total=False)

EmailSecret = TypedDict('EmailSecret',
                        {
                                'clientSecret': str,
                                'password': str,
                                'user': str,
                        }, total=False)

SlackConfig = TypedDict('SlackConfig',
                        {}, total=False)

SlackSecret = TypedDict('SlackSecret',
                        {
                                'webhookUrl': str,
                        }, total=False)


def validate_email_config(module: AnsibleModule) -> None:
    """
    """
    required_fields = ['from', 'host', 'port']

    for field in required_fields:
        if field not in module.params['config']:
            module.fail_json(msg=f"Field '{field}' is required in config for email connector.")

def validate_slack_config(module: AnsibleModule) -> None:
    """
    """
    if not module.params.get('secrets'):
        module.fail_json(msg="`secrets` is required for slack connector.")
    required_fields = ['webhookUrl']

    for field in required_fields:
        if field not in module.params['secrets']:
            module.fail_json(msg=f"Field '{field}' is required in secrets for slack connector.")

def validate_config(module: AnsibleModule) -> None:
    """
    """
    validators = {
        ConnectorTypeIdEnum.email: validate_email_config,
        ConnectorTypeIdEnum.slack: validate_slack_config,
    }

    validator = validators.get(module.params['connector_type_id'])
    if validator:
        validator(module)

def normalize_connector_data(connector: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize connector data to only fields we manage for idempotency checks.
    """
    return {
        'name': connector.get('name'),
        # Kibana responses use connector_type_id, but be defensive
        'connector_type_id': connector.get('connector_type_id') or connector.get('connectorTypeId'),
        'config': connector.get('config', {}),
    }


def main() -> None:
    """
    """
    from ansible_collections.zupersero.elastic.plugins.module_utils import kibana
    argument_spec = kibana.kibana_argument_spec()
    argument_spec.update(
        id=dict(type='str', required=False),
        name=dict(type='str', required=False),
        connector_type_id=dict(type='str', required=False, choices=[v for v in ConnectorTypeIdEnum.__dict__.values() if isinstance(v, str)]),
        config=dict(type='dict', required=False),
        secrets=dict(type='dict', required=False, no_log=True),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_together=kibana.kibana_required_together(),
        mutually_exclusive=kibana.kibana_mutually_exclusive(),
    )

    if module.params['state'] == 'present':
        if not module.params.get('name'):
            module.fail_json(msg="`name` is required when state is `present`")
        if not module.params.get('connector_type_id'):
            module.fail_json(msg="`connector_type_id` is required when state is `present`")
        if not module.params.get('config'):
            module.fail_json(msg="`config` is required when state is `present`")

    validate_config(module)

    client = kibana.KibanaClient(module)
    connector_id = module.params.get('id')
    state = module.params.get('state')

    if state == 'absent' and not connector_id:
        module.fail_json(msg="`id` is required when state is `absent`")

    current_connector = None
    connector_exists = False
    if connector_id:
        status_code, current_connector = client.connectors.get(connector_id)
        connector_exists = status_code == 200

    result = {
        'changed': False,
    }

    if state == 'present':
        desired_connector = {
            'name': module.params['name'],
            'connector_type_id': module.params['connector_type_id'],
            'config': module.params['config'],
        }
        if module.params.get('secrets'):
            desired_connector['secrets'] = module.params['secrets']

        if not connector_exists:
            result['changed'] = True
            if not module.check_mode:
                status_code, created_connector = client.connectors.create(desired_connector)
                if status_code not in [200, 201]:
                    module.fail_json(msg=f"Failed to create connector: {created_connector.get('error', 'Unknown error')}")
                result['connector'] = created_connector
            else:
                result['connector'] = desired_connector
        else:
            if not connector_id:
                module.fail_json(msg="`id` is required to update an existing connector")
            current_normalized = normalize_connector_data(current_connector or {})
            desired_normalized = normalize_connector_data(desired_connector)

            # Connector type cannot be changed once created
            if current_normalized.get('connector_type_id') and current_normalized['connector_type_id'] != desired_normalized['connector_type_id']:
                module.fail_json(msg="`connector_type_id` cannot be changed for an existing connector")

            diff = recursive_diff(current_normalized, desired_normalized)
            secrets_provided = bool(module.params.get('secrets'))

            if diff or secrets_provided:
                result['changed'] = True
                if not module.check_mode:
                    update_payload = {
                        'name': module.params['name'],
                        'config': module.params['config'],
                    }
                    if module.params.get('secrets'):
                        update_payload['secrets'] = module.params['secrets']

                    status_code, updated_connector = client.connectors.update(connector_id, update_payload)
                    if status_code != 200:
                        module.fail_json(msg=f"Failed to update connector: {updated_connector.get('error', 'Unknown error')}")
                    result['connector'] = updated_connector
                else:
                    result['connector'] = desired_connector
            else:
                result['connector'] = current_connector
    elif state == 'absent':
        if connector_exists:
            result['changed'] = True
            if not module.check_mode:
                status_code, response = client.connectors.delete(connector_id)
                if status_code not in [200, 204]:
                    module.fail_json(msg=f"Failed to delete connector: {response.get('error', 'Unknown error')}")
        else:
            # Nothing to do
            pass

    module.exit_json(**result)

if __name__ == '__main__':
    main()

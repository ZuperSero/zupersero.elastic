# Copyright (c) 2026, zupersero
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Documentation fragment for Elasticsearch connection options."""


class ModuleDocFragment:
    DOCUMENTATION = r"""
options:
  url:
    description:
      - Elasticsearch base URL.
      - Mutually exclusive with I(urls).
      - Can also be set with the E(ELASTICSEARCH_URL) environment variable.
    type: str
  urls:
    description:
      - Elasticsearch base URLs used in order for request failover.
      - Mutually exclusive with I(url).
      - Can also be set as a comma-separated E(ELASTICSEARCH_URLS) environment variable.
    type: list
    elements: str
  username:
    description:
      - Username for HTTP basic authentication.
      - Must be supplied together with I(password).
      - Can also be set with the E(ELASTICSEARCH_USERNAME) environment variable.
    type: str
  password:
    description:
      - Password for HTTP basic authentication.
      - Must be supplied together with I(username).
      - Can also be set with the E(ELASTICSEARCH_PASSWORD) environment variable.
    type: str
  api_key:
    description:
      - Encoded Elasticsearch API key.
      - Mutually exclusive with basic authentication and I(bearer_token).
      - Can also be set with the E(ELASTICSEARCH_API_KEY) environment variable.
    type: str
  bearer_token:
    description:
      - Bearer token used for authentication.
      - Mutually exclusive with basic authentication and I(api_key).
      - Can also be set with the E(ELASTICSEARCH_BEARER_TOKEN) environment variable.
    type: str
  headers:
    description:
      - Additional HTTP headers added to every request.
      - Authentication options override an C(Authorization) value in this mapping.
      - Can also be set as a JSON mapping in the E(ELASTICSEARCH_HEADERS) environment variable.
    type: dict
    default: {}
  validate_certs:
    description:
      - Whether to validate the Elasticsearch TLS certificate.
      - Can also be set with the E(ELASTICSEARCH_VALIDATE_CERTS) environment variable.
    type: bool
    default: true
  ca_path:
    description:
      - Path to a PEM CA certificate bundle used for server verification.
      - Mutually exclusive with I(ca_data).
      - Can also be set with the E(ELASTICSEARCH_CA_PATH) environment variable.
    type: path
  ca_data:
    description:
      - PEM CA certificate data used for server verification.
      - Mutually exclusive with I(ca_path).
      - Can also be set with the E(ELASTICSEARCH_CA_DATA) environment variable.
    type: str
  client_cert:
    description:
      - Path to a PEM client certificate chain.
      - The file can include its private key; otherwise also set I(client_key).
      - Can also be set with the E(ELASTICSEARCH_CLIENT_CERT) environment variable.
    type: path
  client_key:
    description:
      - Path to the PEM private key for I(client_cert).
      - Can also be set with the E(ELASTICSEARCH_CLIENT_KEY) environment variable.
    type: path
  certificate_fingerprint:
    description:
      - SHA-256 fingerprint of the HTTPS server leaf certificate.
      - Separators and whitespace are ignored.
      - Pinning performs a direct unauthenticated TLS preflight before HTTP credentials or custom headers are sent.
      - Pinning is mutually exclusive with I(client_cert) because client credentials cannot be sent before verification.
      - Can also be set with the E(ELASTICSEARCH_CERTIFICATE_FINGERPRINT) environment variable.
    type: str
  timeout:
    description:
      - Request timeout in seconds.
      - Can also be set with the E(ELASTICSEARCH_TIMEOUT) environment variable.
    type: int
    default: 30
  retries:
    description:
      - Number of retry attempts after the initial request.
      - Each retry advances to the next configured endpoint.
      - Can also be set with the E(ELASTICSEARCH_RETRIES) environment variable.
    type: int
    default: 3
  retry_pause:
    description:
      - Initial retry delay in seconds. The delay doubles for each attempt, up to 60 seconds.
      - Can also be set with the E(ELASTICSEARCH_RETRY_PAUSE) environment variable.
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
      - Whether mutating HTTP methods can be retried and failed over.
      - Disabled by default because retrying a request after an uncertain failure can repeat a non-idempotent action.
      - Can also be set with the E(ELASTICSEARCH_RETRY_MUTATING_REQUESTS) environment variable.
    type: bool
    default: false
  url_username:
    description:
      - Compatibility alias for I(username).
      - Prefer I(username) for new playbooks.
    type: str
  url_password:
    description:
      - Compatibility alias for I(password).
      - Prefer I(password) for new playbooks.
    type: str
  force_basic_auth:
    description:
      - Compatibility option. Basic authentication is always sent with the initial request.
    type: bool
    default: false
requirements:
  - ansible-core >= 2.15.0
"""

:orphan:

Index of all Collection Environment Variables
=============================================

The Elasticsearch API modules read these controller-side environment variables
when the corresponding module argument is omitted. Explicit module arguments
take precedence. Keep credentials, tokens, headers, and private key material in
your secret manager rather than committing them to playbooks.

Connection and authentication
-----------------------------

``ELASTICSEARCH_URL``
  Single Elasticsearch base URL (default: ``http://localhost:9200``).
``ELASTICSEARCH_URLS``
  Comma-separated URLs used for endpoint failover; mutually exclusive with
  ``ELASTICSEARCH_URL``.
``ELASTICSEARCH_USERNAME`` / ``ELASTICSEARCH_PASSWORD``
  Basic-auth credentials, used together.
``ELASTICSEARCH_API_KEY``
  Encoded Elasticsearch API key.
``ELASTICSEARCH_BEARER_TOKEN``
  Bearer token for HTTP authentication.
``ELASTICSEARCH_HEADERS``
  JSON object of additional HTTP headers.

TLS and client certificates
---------------------------

``ELASTICSEARCH_VALIDATE_CERTS``
  Enable or disable TLS certificate validation (default: ``true``).
``ELASTICSEARCH_CA_PATH`` / ``ELASTICSEARCH_CA_DATA``
  PEM CA bundle path or inline PEM data; use only one.
``ELASTICSEARCH_CLIENT_CERT`` / ``ELASTICSEARCH_CLIENT_KEY``
  PEM client certificate and private-key paths.
``ELASTICSEARCH_CERTIFICATE_FINGERPRINT``
  SHA-256 fingerprint for HTTPS certificate pinning.

Transport and retries
---------------------

``ELASTICSEARCH_TIMEOUT``
  Request timeout in seconds (default: ``30``).
``ELASTICSEARCH_RETRIES``
  Retry attempts after the initial request (default: ``3``).
``ELASTICSEARCH_RETRY_PAUSE``
  Initial retry delay in seconds (default: ``1.0``).
``ELASTICSEARCH_RETRY_MUTATING_REQUESTS``
  Allow retries for mutating requests (default: ``false``).

``retry_status_codes`` has no environment-variable fallback. The compatibility
arguments ``url_username``, ``url_password``, and ``force_basic_auth`` are also
module arguments only.

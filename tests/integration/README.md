# Integration Tests

These targets exercise the Elasticsearch API modules in `zupersero.elastic`.

## Prerequisites

- Elasticsearch available at `http://localhost:9200`
- Username `elastic` and password `changeme`
- Self-signed certificate validation disabled by the test defaults

## Running tests

```sh
# Entire integration suite
ansible-test integration

# Individual targets
ansible-test integration user
ansible-test integration user_role
ansible-test integration enrich_policy
ansible-test integration ingest_pipeline
```

Targets live under `tests/integration/targets/<module_name>/`. Each contains
`tasks/main.yml` and an `aliases` file. Tests cover create, update, delete,
idempotence, authentication, check mode, and password-hash behavior where
applicable. Shared connection parameters are defined with `module_defaults`.

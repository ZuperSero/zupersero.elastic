# Integration Tests

This directory contains integration tests for the zupersero.elastic collection.

## Prerequisites

- A running Kibana instance on `localhost:5601` (for `connector`, `data_view`, `space`)
- A running Elasticsearch instance on `localhost:9200` (for `user`, `user_role`)
- Credentials: username=`elastic`, password=`changeme`
- Self-signed certificates (validate_certs is disabled in tests)

## Running Tests

### Using ansible-test

```bash
# Run all integration tests
ansible-test integration

# Run specific target
ansible-test integration space
ansible-test integration user_role
ansible-test integration user
ansible-test integration connector
ansible-test integration data_view
```

## Test Structure

Each module has its own target directory under `tests/integration/targets/[module_name]/`:

- `tasks/main.yml` - Main test playbook
- `aliases` - Test aliases and tags

## Test Coverage

### connector module
- Create connector
- Update connector
- Cleanup (delete connector)

### data_view module
- Create data view (with check mode)
- Idempotency check after creation
- Update data view
- Delete data view
- Alias-based create/update

### space module
- Create space (with check mode)
- Idempotency check after creation
- Update space (with check mode)
- Idempotency check after update
- Delete space (with check mode)
- Idempotency check after deletion

### user_role module
- Create role (with check mode)
- Idempotency check after creation
- Update role (with check mode) including applications and expanded privileges
- Idempotency check after update
- Delete role (with check mode)
- Idempotency check after deletion

### user module
- Create user
- Idempotency checks
- Authenticate with created user
- Disable user
- Delete user
- Create/delete user with password hash

All tests use `module_defaults` to avoid repeating connection parameters.

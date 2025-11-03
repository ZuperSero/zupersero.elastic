# Integration Tests

This directory contains integration tests for the zupersero.elastic collection.

## Prerequisites

- A running Kibana instance on `localhost:5601`
- Credentials: username=`elastic`, password=`changeme`
- Self-signed certificates (validate_certs is disabled in tests)

## Running Tests

### Using ansible-test

```bash
# Run all integration tests
ansible-test integration

# Run specific target
ansible-test integration space
```

### Using ansible-playbook directly

```bash
# Navigate to the collection root
cd /path/to/zupersero.elastic

# Run the space test playbook
ansible-playbook tests/integration/test_space.yml
```

## Test Structure

Each module has its own target directory under `tests/integration/targets/[module_name]/`:

- `tasks/main.yml` - Main test playbook
- `aliases` - Test aliases and tags

## Test Coverage

### space module
- Create space (with check mode)
- Idempotency check after creation
- Update space (with check mode)
- Idempotency check after update
- Delete space (with check mode)
- Idempotency check after deletion

All tests use `module_defaults` to avoid repeating connection parameters.

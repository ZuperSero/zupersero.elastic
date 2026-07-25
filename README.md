# zupersero.elastic

[![Molecule Tests](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/molecule.yml/badge.svg?branch=main)](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/molecule.yml)
[![Integration Tests](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-integration.yml/badge.svg?branch=main)](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-integration.yml)
[![Sanity Tests](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-sanity.yml/badge.svg?branch=main)](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-sanity.yml)

An Ansible collection for installing, configuring, and managing Elasticsearch.
Kibana roles and API modules live in the separate `zupersero.kibana` collection.

## Installation

```sh
ansible-galaxy collection install zupersero.elastic
```

To install from Git:

```sh
ansible-galaxy collection install git+https://github.com/ZuperSero/zupersero.elastic.git
```

## Environment variables

Elasticsearch API modules accept:

```text
ELASTICSEARCH_URL
ELASTICSEARCH_USERNAME
ELASTICSEARCH_PASSWORD
ELASTICSEARCH_API_KEY
ELASTICSEARCH_VALIDATE_CERTS
```

For AWX or Automation Controller, inject these variables through a custom
credential type and mark passwords and API keys as secret.

## Development

```sh
just init
just ruff
just sanity
just integration
just molecule
```

See `roles/elasticsearch/README.md` for role usage and
`tests/integration/README.md` for integration-test prerequisites.

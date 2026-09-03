# zupersero.elastic

[![Molecule Tests](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/molecule.yml/badge.svg?branch=main)](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/molecule.yml)
[![Integration Tests](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-integration.yml/badge.svg?branch=main)](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-integration.yml)
[![Sanity Tests](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-sanity.yml/badge.svg?branch=main)](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-sanity.yml)
[![Unit Tests](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-units.yml/badge.svg?branch=main)](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-units.yml)

An Ansible collection for installing, configuring, and managing Elasticsearch.
Kibana roles and API modules live in the separate `zupersero.kibana` collection.

Also check out my other collections:
[zupersero.kibana](https://github.com/ZuperSero/zupersero.kibana) for Kibana and
Fleet management, and [zupersero.tailscale](https://github.com/ZuperSero/zupersero.tailscale)
for Tailscale automation.

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

All Elasticsearch API modules belong to the `zupersero.elastic.elasticsearch`
module-defaults group:

```yaml
module_defaults:
  group/zupersero.elastic.elasticsearch:
    url: https://elasticsearch.example.com:9200
    api_key: "{{ elasticsearch_api_key }}"
```

## Examples

See the [examples directory](examples/) for ready-to-adapt playbooks. The
collection also includes detailed examples on each module's documentation page.

## Releases

See the latest published versions on [Ansible Galaxy](https://galaxy.ansible.com/ui/repo/published/zupersero/elastic/)
or browse the [GitHub releases](https://github.com/ZuperSero/zupersero.elastic/releases).

## Development

To get a local environment ready, install [uv](https://docs.astral.sh/uv/)
first, then run `just init`. It creates the collection's Python virtual
environment and installs the tooling needed to run checks and examples.

```sh
just init
```

## API reference

The [Ansible Galaxy collection page](https://galaxy.ansible.com/ui/repo/published/zupersero/elastic/)
and generated documentation contain the complete module and role reference.
Start with the examples above for common tasks, or use
`zupersero.elastic.elasticsearch_object` when a typed module is not available
for an API resource.

Template modules preserve omitted existing fields during normal updates. Set
`replace: true` when declaring the complete desired template and clearing
empty dictionaries or removing omitted optional fields such as `data_stream`.
Lifecycle policies follow the same preservation model. Index templates accept
typed `lifecycle.name` and `lifecycle.rollover_alias` options; an empty
`lifecycle` dictionary detaches both settings.

Data stream lifecycle updates also preserve omitted fields by default. Set
`replace: true` to remove omitted retention or downsampling configuration, use
an empty `downsampling` list to clear only the rounds while preserving other
fields, and set `state: absent` to detach lifecycle management without deleting
the data stream.

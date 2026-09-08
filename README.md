# zupersero.elastic

[![Molecule Tests](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/molecule.yml/badge.svg?branch=main)](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/molecule.yml)
[![Integration Tests](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-integration.yml/badge.svg?branch=main)](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-integration.yml)
[![Sanity Tests](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-sanity.yml/badge.svg?branch=main)](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-sanity.yml)
[![Unit Tests](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-units.yml/badge.svg?branch=main)](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-units.yml)

An Ansible collection for installing, configuring, and managing Elasticsearch.
Kibana roles and API modules live in the separate `zupersero.kibana` collection.

Collection releases use independent Semantic Versioning. A collection version
does not identify or mirror an Elasticsearch version.

## Supported versions

The 1.0 release is verified with ansible-core 2.19, controller Python 3.11-3.13,
and Elasticsearch 9.2, 9.4, and 9.5. The Elasticsearch role is verified on
Ubuntu 24.04, Debian 13, and Rocky Linux 10; the Elastic Agent role is verified
on Ubuntu 24.04. Elasticsearch Serverless is not part of the initial support
guarantee.

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

The complete environment-variable reference, including bearer authentication,
multiple endpoints, custom headers, CA data, client certificates, certificate
fingerprints, and retry controls, is in
[`docs/environment_variables.rst`](docs/environment_variables.rst).

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

The initial typed surface covers indices and mappings, aliases, cluster
settings, composable templates, ILM, data streams, ingest and enrich policies,
snapshot repositories and lifecycle policies, users, roles, role mappings, and
API keys. `elasticsearch_info` and `elasticsearch_request` cover read/list and
non-resource operations not represented by a typed module.

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

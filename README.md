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

All Elasticsearch API modules belong to the `zupersero.elastic.elasticsearch`
module-defaults group:

```yaml
module_defaults:
  group/zupersero.elastic.elasticsearch:
    url: https://elasticsearch.example.com:9200
    api_key: "{{ elasticsearch_api_key }}"
```

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

## Releases

Releases are published to Ansible Galaxy by GitHub Actions when a published,
non-prerelease GitHub Release uses a tag matching the `version` in `galaxy.yml`
(for example, `1.0.0`). To release this collection:

1. Update the `version` in `galaxy.yml` and commit the change.
2. Push the commit and create a GitHub Release using the matching version tag.
3. Confirm that the release workflow builds and imports the collection at
   [Ansible Galaxy](https://galaxy.ansible.com/).

The repository must have a `GALAXY_API_KEY` secret with permission to publish
the `zupersero.elastic` namespace. The workflow only requests read access to
repository contents and intentionally skips prereleases. Do not reuse a
published version; Galaxy rejects duplicate collection versions.

## API modules

- `zupersero.elastic.data_stream` manages data stream creation, reads, and
  deletion independently of lifecycle attachment.
- `zupersero.elastic.data_stream_lifecycle` manages typed retention and
  downsampling configuration on existing data streams, including partial
  preservation, authoritative replacement, explicit clearing, and detachment.
- `zupersero.elastic.component_template` manages reusable composable-template
  settings, mappings, aliases, metadata, versions, and deprecation state.
- `zupersero.elastic.index_template` manages composable index templates,
  including patterns, ordered component composition, direct template content,
  data-stream options, typed lifecycle policy attachment, priority, and
  auto-creation behavior.
- `zupersero.elastic.index_lifecycle_policy` manages ILM phase policies with
  preservation-aware partial updates, authoritative replacement, check mode,
  and diff mode.
- `zupersero.elastic.ingest_pipeline` manages ingest pipelines with arbitrary
  processor definitions, preservation-aware partial updates, authoritative
  replacement, check mode, and diff mode.
- `zupersero.elastic.enrich_policy` manages match, range, and geo-match enrich
  policies with preservation-aware updates, authoritative replacement, and an
  explicit execution action.
- `zupersero.elastic.index` manages index creation, dynamic settings, mappings,
  read outcomes, and deletion with check and diff mode support.
- `zupersero.elastic.elasticsearch_object` manages arbitrary idempotent API
  objects when no typed module exists.
- `zupersero.elastic.elasticsearch_request` executes explicit API actions.
- `zupersero.elastic.elasticsearch_info` reads arbitrary API information.

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

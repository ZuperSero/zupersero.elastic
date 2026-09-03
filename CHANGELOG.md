# Changelog

## Unreleased

- Add guarded GitHub Release automation that builds and publishes matching
  collection versions to Ansible Galaxy.
- Add shared Phase 0 API client foundations and generic object, request, and
  information modules.
- Add the typed `index` module and reusable index service with idempotent
  settings and mapping reconciliation, check mode, diff mode, and complete
  live lifecycle coverage.
- Add typed `component_template` and composable `index_template` modules backed
  by reusable template services, with preservation-aware partial updates,
  explicit full-replacement and clearing support, check and diff mode,
  current-state returns, and live lifecycle coverage.
- Add typed `index_lifecycle_policy` management and reusable lifecycle service
  with phase-envelope validation, preservation-aware partial updates,
  authoritative replacement, current-state returns, check and diff mode, and
  complete live lifecycle coverage.
- Add typed `ingest_pipeline` management and reusable pipeline service with
  arbitrary processor definitions, preservation-aware partial updates,
  authoritative replacement, current-state returns, check and diff mode, and
  complete live lifecycle coverage.
- Add typed `enrich_policy` management and reusable enrich service with
  match/range/geo-match validation, preservation-aware partial updates,
  authoritative replacement, explicit execution, check mode, and sanitized
  errors.
- Add typed lifecycle policy and rollover-alias attachment to composable index
  templates, including explicit detachment and data-stream validation.
- Add typed `data_stream` and `data_stream_lifecycle` modules backed by
  reusable services, with independent stream and lifecycle state, typed
  retention and downsampling, normalized effective and global retention
  responses, preservation-aware updates, authoritative clearing, check and
  diff mode, and complete live lifecycle coverage.



## [1.0.0] - 2025-01-18

### Added

- Initial release of the `zupersero.elastic` collection
- `space` module for managing Kibana Spaces (create, update, delete)
- `elasticsearch` role for installing and configuring Elasticsearch
- Module utilities for Kibana API interaction

Elastic Agent
=========

Installs Elastic Agent from the Linux tarball and enrolls the host into Fleet.

Requirements
------------

The target host must be Linux with systemd and belong to the Debian or RedHat OS family.

Role Variables
--------------

| Variable | Default | Description |
|----------|---------|-------------|
| `elastic_agent_version` | `auto` | Elastic Agent version to install, or `auto` to use the Elasticsearch version |
| `elastic_agent_fleet_url` | `""` | Fleet Server URL used for enrollment |
| `elastic_agent_policy_id` | `""` | Fleet agent policy ID |
| `elastic_agent_kibana_url` | `""` | Kibana URL used for enrollment token lookup/creation |
| `elastic_agent_kibana_api_key` | `""` | Kibana API key authentication |
| `elastic_agent_kibana_username` | `""` | Kibana basic auth username |
| `elastic_agent_kibana_password` | `""` | Kibana basic auth password |
| `elastic_agent_elasticsearch_url` | `""` | Elasticsearch URL used when version is `auto` |
| `elastic_agent_elasticsearch_api_key` | `""` | Elasticsearch API key authentication |
| `elastic_agent_elasticsearch_username` | `""` | Elasticsearch basic auth username |
| `elastic_agent_elasticsearch_password` | `""` | Elasticsearch basic auth password |
| `elastic_agent_validate_certs` | `true` | Validate TLS certificates for API requests |
| `elastic_agent_certificate_authorities` | `""` | CA file passed to Elastic Agent install |
| `elastic_agent_ca_sha256` | `""` | CA SHA256 fingerprint passed to Elastic Agent install |
| `elastic_agent_insecure` | `false` | Pass `--insecure` to Elastic Agent install |
| `elastic_agent_artifact_url` | `""` | Override tarball URL |
| `elastic_agent_download_dir` | `/tmp` | Remote staging directory for the downloaded archive and extracted installer. Set this to a filesystem with enough free space if `/tmp` is small |
| `elastic_agent_cleanup_extract_dir` | `true` | Remove the extracted installer directory after install attempts |

Dependencies
------------

None.

Example Playbook
----------------

    - hosts: agents
      roles:
        - role: zupersero.elastic.elastic_agent
          elastic_agent_fleet_url: "https://fleet.example.com:8220"
          elastic_agent_policy_id: "agent-policy-id"
          elastic_agent_kibana_url: "https://kibana.example.com"
          elastic_agent_kibana_api_key: "{{ kibana_api_key }}"
          elastic_agent_elasticsearch_url: "https://elasticsearch.example.com:9200"
          elastic_agent_elasticsearch_api_key: "{{ elasticsearch_api_key }}"

License
-------

GPL-3.0-or-later

Author Information
------------------

zupersero

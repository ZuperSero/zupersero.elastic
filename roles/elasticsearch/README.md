Elasticsearch
=========

Installs and configures Elasticsearch on Debian and RedHat-based systems.

Requirements
------------

None.

Role Variables
--------------

| Variable | Default | Description |
|----------|---------|-------------|
| `elasticsearch_version` | `9.2.1` | Elasticsearch version to install |
| `elasticsearch_bootstrap` | `false` | Enable bootstrap tasks |
| `elasticsearch_install_method` | `package` | Installation method (package or tar) |
| `elasticsearch_download_timeout` | `30` | Repository signing key download timeout in seconds |
| `elasticsearch_package_install_timeout` | `1800` | Maximum package manager operation runtime in seconds |
| `elasticsearch_jvm_heap_size` | `8g` | JVM heap size |
| `elasticsearch_config_content` | See defaults | Elasticsearch configuration as YAML |
| `elasticsearch_secure_config` | `{}` | Keystore settings |
| `elasticsearch_bootstrap_password` | `changeme` | Bootstrap password for security |

Dependencies
------------

None.

Example Playbook
----------------

    - hosts: elasticsearch
      roles:
        - role: zupersero.elastic.elasticsearch
          elasticsearch_version: "9.2.1"
          elasticsearch_config_content:
            cluster:
              name: "my_cluster"
            discovery:
              type: "single-node"
            node:
              name: "{{ inventory_hostname }}"

License
-------

BSD

Author Information
------------------

zupersero

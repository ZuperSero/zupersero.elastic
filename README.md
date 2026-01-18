# zupersero.elastic
[![Molecule Tests](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/molecule.yml/badge.svg?branch=main)](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/molecule.yml)
[![Run ansible integration tests](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-integration.yml/badge.svg?branch=main)](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-integration.yml)
[![Run ansible sanity tests](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-sanity.yml/badge.svg?branch=main)](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-sanity.yml)
[![Run ansible tests](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test.yml/badge.svg?branch=main)](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test.yml)

A collection to work with elastic products such as elasticsearch and kibana. The collection contains modules for working with elastic stack, such as creating accounts, manage ILM policies, creating detection and alert rules, manage fleet policies and integrations and much more.

Some modules might target kibana and some might target elasticsearch directly depending on where the API is exposed.
Two sets of [environment variables](#Environment-Variables) can help ease the use of this collection.

Read the full documentation on [galaxy](https://galaxy.ansible.com/ui/repo/published/zupersero/elastic)


## Installation
Follow these instructions to install the collection.

Read more about it [here](https://docs.ansible.com/ansible/latest/galaxy/user_guide.html#installing-roles-and-collections-from-the-same-requirements-yml-file)

ansible galaxy cli
```sh
ansible-galaxy collection install zupersero.elastic
```
or from github
```sh
ansible-galaxy collection install https://github.com/ZuperSero/zupersero.elastic
# or ssh
ansible-galaxy collection install git@github.com:ZuperSero/zupersero.elastic.git
```

requirements.yml
```yaml
collections:
  - src: zupersero.elastic
    version: "1.0.0"

  - src: git@github.com:ZuperSero/zupersero.elastic.git
    scm: git
```
Then run
```sh
ansible-galaxy collection install -r your_requirements.yml
```

## Environment Variables

For the elasticsearch modules.
```sh
ELASTICSEARCH_URL
ELASTICSEARCH_USERNAME
ELASTICSEARCH_PASSWORD
ELASTICSEARCH_API_KEY
ELASTICSEARCH_VALIDATE_CERTS
```

For the kibana modules.
```sh
KIBANA_URL
KIBANA_USERNAME
KIBANA_PASSWORD
KIBANA_API_KEY
KIBANA_SPACE
KIBANA_VALIDATE_CERTS
```

If you are using tower / awx / red hat automation platform you might want to make an elasticsearch credential type to inject these variables into you job templates.

Input configuration
```yaml
fields:
# Elasticsearch
  - id: ELASTICSEARCH_URL
    type: string
    label: Elasticsearch URL
    secret: false
  - id: ELASTICSEARCH_USERNAME
    type: string
    label: Elasticsearch Username
    secret: false
  - id: ELASTICSEARCH_PASSWORD
    type: string
    label: Elasticsearch Password
    secret: true
  - id: ELASTICSEARCH_API_KEY
    type: string
    label: Elasticsearch API Key
    secret: true
  # Kibana
  - id: KIBANA_URL
    type: string
    label: Kibana URL
    secret: false
  - id: KIBANA_USERNAME
    type: string
    label: Kibana Username
    secret: false
  - id: KIBANA_PASSWORD
    type: string
    label: Kibana Password
    secret: true
  - id: KIBANA_API_KEY
    type: string
    label: Kibana API Key
    secret: true
required:
  - ELASTICSEARCH_URL
  - KIBANA_URL
```

Injector configuration.
```yaml
env:
  ELASTICSEARCH_URL: '{{ ELASTICSEARCH_URL }}'
  ELASTICSEARCH_USERNAME: '{{ ELASTICSEARCH_USERNAME }}'
  ELASTICSEARCH_PASSWORD: '{{ ELASTICSEARCH_PASSWORD }}'
  ELASTICSEARCH_API_KEY: '{{ ELASTICSEARCH_API_KEY }}'
  KIBANA_URL: '{{ KIBANA_URL }}'
  KIBANA_USERNAME: '{{ KIBANA_USERNAME }}'
  KIBANA_PASSWORD: '{{ KIBANA_PASSWORD }}'
  KIBANA_API_KEY: '{{ KIBANA_API_KEY }}'
```
# zupersero.elastic
[![Molecule Tests](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/molecule.yml/badge.svg?branch=main)](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/molecule.yml)
[![Run ansible integration tests](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-integration.yml/badge.svg?branch=main)](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-integration.yml)
[![Run ansible sanity tests](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-sanity.yml/badge.svg?branch=main)](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test-sanity.yml)
[![Run ansible tests](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test.yml/badge.svg?branch=main)](https://github.com/ZuperSero/zupersero.elastic/actions/workflows/ansible-test.yml)

A collection to work with elastic products such as elasticsearch and kibana. The collection contains modules for working with elastic stack, such as creating accounts, manage ILM policies, creating detection and alert rules, manage fleet policies and integrations and much more.

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
ansible-galaxy collection install -r [your_requirements.yml]
```


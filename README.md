# zupersero.elastic
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


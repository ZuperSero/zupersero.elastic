init:
    uv venv --allow-existing --python 3.11
    source .venv/bin/activate
    uv pip install \
        ansible-core==2.19.5

activate:
    source .venv/bin/activate

install:
    ansible-galaxy collection install . --force

molecule:
    molecule test --scenario-name elasticsearch

sanity:
    .venv/bin/ansible-test sanity --coverage
    .venv/bin/ansible-test coverage report --include 'plugins/*'


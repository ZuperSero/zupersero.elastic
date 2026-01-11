init:
    uv venv --allow-existing --python 3.11
    source .venv/bin/activate
    uv pip install \
        ansible-core \
        molecule \
        molecule-plugins[docker]

install:
    ansible-galaxy collection install . --force

molecule:
    molecule test --scenario-name elasticsearch

sanity:
    ansible-test sanity

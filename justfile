init:
    uv venv --allow-existing
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
    docker run \
        --rm \
        -t \
        -e ANSIBLE_FORCE_COLOR=1 \
        -v ${PWD}:/ansible_collections/zupersero/elastic \
        -w /ansible_collections/zupersero/elastic \
        python:3.12.12-slim \
        sh -c "apt-get update && apt-get install -y git && pip install ansible-core && git config --global --add safe.directory /ansible_collections/zupersero/elastic && ansible-test sanity"

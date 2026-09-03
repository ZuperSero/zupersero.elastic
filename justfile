init:
    uv venv --allow-existing --python 3.11
    source .venv/bin/activate
    uv pip install \
        "ansible-core>=2.19.5" \
        "ansible-lint>=26.1.1" \
        "coverage==7.6.1" \
        "ruff>=0.14.13" \
        "molecule>=26.6.0" \
        "molecule-plugins[docker]>=26.7.15" \
        "antsibull-core>=3.5.0" \
        "antsibull-docs>=2.24.0" \
        "passlib>=1.7.4"
    .venv/bin/ansible-galaxy collection install \
        -r extensions/molecule/elasticsearch/collections.yml \
        --force

activate:
    source .venv/bin/activate

install:
    .venv/bin/ansible-galaxy collection install . --force

molecule:
    .venv/bin/ansible-galaxy collection install . --force
    cd extensions && PATH="{{ justfile_directory() }}/.venv/bin:$PATH" molecule test --scenario-name elasticsearch

ruff:
    .venv/bin/ruff check .
sanity:
    .venv/bin/ansible-test sanity --coverage
    .venv/bin/ansible-test coverage report --include 'plugins/*'

integration:
    .venv/bin/ansible-test integration --coverage
    .venv/bin/ansible-test coverage report --include 'plugins/*'

integration_act:
    # Set ACT_JOB to select a single workflow job; the workflow serializes its matrix.
    act push -W .github/workflows/ansible-test-integration.yml \
        -P ubuntu-latest=ghcr.io/catthehacker/ubuntu:full-22.04 \
        --container-options "--privileged --network host --user 0:0" \
        ${ACT_JOB:+-j "$ACT_JOB"}

molecule_act:
    act push -W .github/workflows/molecule.yml \
        -P ubuntu-latest=ghcr.io/catthehacker/ubuntu:full-22.04 \
        --container-options "--privileged --network host --user 0:0" \
        ${ACT_JOB:+-j "$ACT_JOB"}

unit_act:
    act push -W .github/workflows/ansible-test-units.yml \
        -P ubuntu-latest=ghcr.io/catthehacker/ubuntu:full-22.04 \
        --container-options "--privileged --network host --user 0:0" \
        ${ACT_JOB:+-j "$ACT_JOB"}

act-dry-run:
    act push -W .github/workflows/ansible-test-units.yml -W .github/workflows/ansible-test-sanity.yml -W .github/workflows/ansible-test-integration.yml -W .github/workflows/molecule.yml -P ubuntu-latest=ghcr.io/catthehacker/ubuntu:full-22.04 --dryrun

ci_act: integration_act molecule_act unit_act

elastic:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ -x elastic-start-local/start.sh ]]; then
        elastic-start-local/start.sh
        exit 0
    fi
    mkdir -p .build
    curl --fail --silent --show-error --location \
        --output .build/start-local.sh \
        https://elastic.co/start-local
    chmod +x .build/start-local.sh
    ES_LOCAL_PASSWORD="changeme" .build/start-local.sh -v 9.2.0

elastic_stop:
    elastic-start-local/stop.sh

elastic_teardown:
    elastic-start-local/uninstall.sh

docker_cleanup:
    docker stop $(docker ps -a -q) || true
    docker rm $(docker ps -a -q) || true

docs:
    .venv/bin/ansible-galaxy collection install . --force
    mkdir -p .build/docs
    .venv/bin/antsibull-docs sphinx-init --use-current --dest-dir .build/docs zupersero.elastic
    uv pip install --python .venv/bin/python -r .build/docs/requirements.txt
    cd .build/docs && PATH="{{ justfile_directory() }}/.venv/bin:$PATH" ./build.sh
    cp docs/environment_variables.rst .build/docs/rst/collections/environment_variables.rst
    cd .build/docs && PATH="{{ justfile_directory() }}/.venv/bin:$PATH" sphinx-build -M html rst build -c . -W --keep-going
    python3 -m http.server --directory .build/docs/build/html

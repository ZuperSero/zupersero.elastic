init:
    uv venv --allow-existing --python 3.11
    source .venv/bin/activate
    uv pip install \
        ansible-core==2.19.5 \
        ansible-lint==26.1.1 \
        ruff==0.14.13 \
        antsibull-core==3.5.0


activate:
    source .venv/bin/activate

install:
    ansible-galaxy collection install . --force

molecule:
    molecule test --scenario-name elasticsearch

ruff:
    .venv/bin/ruff check .
sanity:
    .venv/bin/ansible-test sanity --coverage
    .venv/bin/ansible-test coverage report --include 'plugins/*'

integration:
    .venv/bin/ansible-test integration --coverage
    .venv/bin/ansible-test coverage report --include 'plugins/*'

integration_act:
    act push -W .github/workflows/ansible-test-integration.yml -P ubuntu-latest=ghcr.io/catthehacker/ubuntu:full-22.04 --container-options "--privileged --network host --user 0:0"

elastic:
    wget https://elastic.co/start-local
    sed -i 's/check_disk_space_gb ${min_disk_space_required}/#check_disk_space_gb ${min_disk_space_required}/' start-local
    chmod +x start-local
    ES_LOCAL_PASSWORD="changeme" ./start-local -v 9.2.0
    rm start-local

elastic_teardown:
    elastic-start-local/uninstall.sh
    rm -rf elastic-start-local

docker_cleanup:
    docker stop $(docker ps -a -q) || true
    docker rm $(docker ps -a -q) || true

docs:
    ansible-galaxy collection install . --force
    mkdir -p .build/docs
    antsibull-docs sphinx-init --use-current --dest-dir .build/docs zupersero.elastic
    uv pip install -r .build/docs/requirements.txt
    cd .build/docs && ./build.sh

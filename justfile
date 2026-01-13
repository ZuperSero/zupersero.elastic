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

integration:
    .venv/bin/ansible-test integration --coverage
    .venv/bin/ansible-test coverage report --include 'plugins/*'

elastic:
    wget https://elastic.co/start-local
    sed -i 's/check_disk_space_gb ${min_disk_space_required}/#check_disk_space_gb ${min_disk_space_required}/' start-local
    chmod +x start-local
    ES_LOCAL_PASSWORD="changeme" ./start-local -v 9.2.0
    rm start-local

elastic_teardown:
    elastic-start-local/uninstall.sh
    rm -rf elastic-start-local
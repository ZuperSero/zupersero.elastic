# Demo Playbooks

This directory contains example playbooks demonstrating the capabilities of the `zupersero.elastic` collection.

## Available Playbooks

### demo.yml
Simple demonstration of the `zupersero.elastic.space` module that creates a single demo space.

### cleanup_demo.yml
Removes the demo space created by demo.yml.

## Usage

### Running the Demo

You need to provide the Kibana connection details:

```bash
ansible-playbook playbooks/demo.yml \
  -e kibana_url=http://localhost:5601 \
  -e kibana_user=elastic \
  -e kibana_password=changeme
```

### Cleaning Up

To remove the demo space:

```bash
ansible-playbook playbooks/cleanup_demo.yml \
  -e kibana_url=http://localhost:5601 \
  -e kibana_user=elastic \
  -e kibana_password=changeme
```

## What the Demo Creates

The demo playbook creates a single space:

- **demo-space**: Demo Space
  - Teal color (#00BFB3) with "DS" initials
  - Simple example showcasing basic space creation

## Notes

- The demo uses `validate_certs: false` for convenience. In production, you should validate certificates.
- The space is created idempotently - you can run the demo multiple times safely.
- Deleting a space also deletes all saved objects within it.

## Need Help?

For more information about the space module, see the module documentation:
```bash
ansible-doc zupersero.elastic.space
```

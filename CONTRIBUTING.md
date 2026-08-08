# Contributing

## Setting up

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
pre-commit install
cd ansible && ansible-galaxy collection install -r requirements.yml
```

## Before opening a pull request

```bash
make validate   # seed integrity and template rendering
make lint       # yamllint, ruff, ansible-lint
```

CI runs the same checks, so anything that passes locally will pass there.

## Adding a device

Devices are data, not code. Add an entry to `seed/devices.yml`:

```yaml
- name: "rtm-acc-03"
  location: "Rotterdam DC"
  role: "Access Switch"
  device_type: "Catalyst 9300-48P"
  platform: "Cisco IOS-XE"
  management_ip: "10.255.0.18/24"
  serial: "LAB-RTM-A003"
```

`make validate` will reject the entry if it references an unknown location,
role, device type or platform, if the name breaks the `<site>-<role>-<number>`
convention, or if the management address collides with another device or falls
outside a declared prefix.

## Adding a platform

Four things have to line up:

1. A `platforms` entry in `seed/devices.yml` with the correct `network_driver`
2. A template at `ansible/playbooks/templates/<network_driver>.j2`
3. A fetch task branch in `ansible/tasks/fetch_config.yml`
4. A mapping in `DRIVER_BY_PLATFORM` in `tests/validate_templates.py`

Miss any one and `make validate` will tell you which.

## Changing corporate standards

Values such as DNS servers, NTP servers and syslog targets live in
`ansible/group_vars/all.yml` under `corporate`. Change them there and every
device's intended configuration changes on the next render — that is the point
of holding standards in one place rather than in per-device templates.

## Style

Python is formatted and linted with `ruff`, targeting the version pinned in
`.pre-commit-config.yaml`. YAML is checked with `yamllint` against `.yamllint`.
Ansible content follows the `production` profile of `ansible-lint`.

Commit messages use the imperative mood: "Add EOS template", not "Added" or
"Adding".

## What does not belong here

No real device data. No configuration, addressing, hostnames or topology from
any production network. Everything in this repository is invented, and it stays
that way.

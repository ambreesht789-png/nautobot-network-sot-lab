#!/usr/bin/env python3
"""Render every configuration template against every device in the seed data.

This catches the two failure modes that only appear at run time otherwise: a
syntax error in a template, and a device whose platform has no template at all.
Both are cheap to find here and expensive to find mid-playbook.

Usage:
    python tests/validate_templates.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError

ROOT = Path(__file__).parent.parent
SEED_FILE = ROOT / "seed" / "devices.yml"
TEMPLATE_DIR = ROOT / "ansible" / "templates"
GROUP_VARS = ROOT / "ansible" / "group_vars" / "all.yml"

# Maps the platform names in the seed data to the network_driver value that
# Nautobot exposes and the templates are named after.
DRIVER_BY_PLATFORM = {
    "Cisco IOS-XE": "cisco_ios",
    "Cisco NX-OS": "cisco_nxos",
    "Juniper Junos": "juniper_junos",
    "Arista EOS": "arista_eos",
}


def load_corporate_standards() -> dict:
    """Extract the corporate variables the templates reference.

    group_vars/all.yml contains Ansible lookups that are not valid outside a
    playbook run, so the corporate block is read as raw text and parsed alone.
    """
    with GROUP_VARS.open(encoding="utf-8") as handle:
        lines = handle.readlines()

    block: list[str] = []
    capturing = False

    for line in lines:
        if line.startswith("corporate:"):
            capturing = True
            block.append(line)
            continue
        if capturing:
            if line.strip() and not line.startswith((" ", "\t")):
                break
            block.append(line)

    parsed = yaml.safe_load("".join(block))
    return parsed["corporate"]


def build_context(device: dict, corporate: dict) -> dict:
    """Assemble the variables a template expects for one device."""
    return {
        "inventory_hostname": device["name"],
        "device_platform": device["platform"],
        "device_role": device["role"],
        "site_name": device["location"],
        "ansible_host": device["management_ip"].split("/")[0],
        "corporate": corporate,
    }


def main() -> int:
    """Render each device's template and report any failure."""
    with SEED_FILE.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    corporate = load_corporate_standards()

    environment = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
    )

    failures = 0
    rendered = 0

    for device in data["devices"]:
        driver = DRIVER_BY_PLATFORM.get(device["platform"])

        if driver is None:
            print(
                f"FAIL {device['name']}: platform '{device['platform']}' has no "
                f"driver mapping"
            )
            failures += 1
            continue

        template_path = TEMPLATE_DIR / f"{driver}.j2"
        if not template_path.exists():
            print(f"FAIL {device['name']}: missing template {driver}.j2")
            failures += 1
            continue

        try:
            template = environment.get_template(f"{driver}.j2")
            output = template.render(**build_context(device, corporate))
        except TemplateError as error:
            print(f"FAIL {device['name']} ({driver}.j2): {error}")
            failures += 1
            continue

        if not output.strip():
            print(f"FAIL {device['name']}: template rendered empty output")
            failures += 1
            continue

        rendered += 1

    if failures:
        print(f"\n{failures} template(s) failed to render.")
        return 1

    print(f"All {rendered} device configurations rendered successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

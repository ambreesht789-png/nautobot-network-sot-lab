#!/usr/bin/env python3
"""Validate the integrity of the synthetic inventory definition.

Run before seeding, and in CI on every change. Catching a broken reference here
takes a second; catching it halfway through a seed run leaves Nautobot in a
partially populated state.

Usage:
    python tests/validate_seed.py
"""

from __future__ import annotations

import ipaddress
import sys
from collections import Counter
from pathlib import Path

import yaml

SEED_FILE = Path(__file__).parent.parent / "seed" / "devices.yml"


class ValidationError(Exception):
    """Raised when the seed definition fails a check."""


def load_seed() -> dict:
    """Read and parse the seed definition."""
    if not SEED_FILE.exists():
        raise ValidationError(f"Seed file not found: {SEED_FILE}")

    with SEED_FILE.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def check_required_sections(data: dict) -> None:
    """Every top-level section the seeder depends on must be present."""
    required = {
        "organisation",
        "locations",
        "manufacturers",
        "roles",
        "platforms",
        "prefixes",
        "devices",
    }
    missing = required - set(data)
    if missing:
        raise ValidationError(f"Missing sections: {', '.join(sorted(missing))}")


def check_unique_names(data: dict) -> None:
    """Device names and serial numbers must both be unique."""
    for field in ("name", "serial"):
        values = [device[field] for device in data["devices"]]
        duplicates = [value for value, count in Counter(values).items() if count > 1]
        if duplicates:
            raise ValidationError(
                f"Duplicate device {field}(s): {', '.join(sorted(duplicates))}"
            )


def check_references(data: dict) -> None:
    """Every device must reference a location, role, type and platform that exist."""
    known = {
        "location": {entry["name"] for entry in data["locations"]},
        "role": {entry["name"] for entry in data["roles"]},
        "platform": {entry["name"] for entry in data["platforms"]},
        "device_type": {
            model["model"]
            for manufacturer in data["manufacturers"]
            for model in manufacturer["device_types"]
        },
    }

    for device in data["devices"]:
        for field, valid_values in known.items():
            value = device.get(field)
            if value not in valid_values:
                raise ValidationError(
                    f"Device '{device['name']}' references unknown {field} "
                    f"'{value}'"
                )


def check_platform_manufacturers(data: dict) -> None:
    """Each platform must belong to a manufacturer that is defined."""
    manufacturers = {entry["name"] for entry in data["manufacturers"]}

    for platform in data["platforms"]:
        if platform["manufacturer"] not in manufacturers:
            raise ValidationError(
                f"Platform '{platform['name']}' references unknown manufacturer "
                f"'{platform['manufacturer']}'"
            )


def check_addressing(data: dict) -> None:
    """Management addresses must be unique, valid, and inside a declared prefix."""
    prefixes = [ipaddress.ip_network(entry["prefix"]) for entry in data["prefixes"]]
    seen: dict[str, str] = {}

    for device in data["devices"]:
        raw = device["management_ip"]

        try:
            interface = ipaddress.ip_interface(raw)
        except ValueError as error:
            raise ValidationError(
                f"Device '{device['name']}' has an invalid management IP "
                f"'{raw}': {error}"
            ) from error

        address = str(interface.ip)

        if address in seen:
            raise ValidationError(
                f"Management IP {address} is used by both '{seen[address]}' "
                f"and '{device['name']}'"
            )
        seen[address] = device["name"]

        if not any(interface.ip in prefix for prefix in prefixes):
            raise ValidationError(
                f"Device '{device['name']}' management IP {address} falls "
                f"outside every declared prefix"
            )


def check_naming_convention(data: dict) -> None:
    """Device names must follow the site-role-number convention."""
    site_codes = {entry["code"].lower() for entry in data["locations"]}

    for device in data["devices"]:
        parts = device["name"].split("-")
        if len(parts) != 3:
            raise ValidationError(
                f"Device name '{device['name']}' does not match the "
                f"<site>-<role>-<number> convention"
            )
        if parts[0] not in site_codes:
            raise ValidationError(
                f"Device name '{device['name']}' starts with an unknown site "
                f"code '{parts[0]}'"
            )


def main() -> int:
    """Run every check and report the outcome."""
    checks = (
        ("required sections", check_required_sections),
        ("unique names and serials", check_unique_names),
        ("object references", check_references),
        ("platform manufacturers", check_platform_manufacturers),
        ("management addressing", check_addressing),
        ("naming convention", check_naming_convention),
    )

    try:
        data = load_seed()
    except ValidationError as error:
        print(f"FAIL: {error}")
        return 1

    for description, check in checks:
        try:
            check(data)
        except ValidationError as error:
            print(f"FAIL [{description}]: {error}")
            return 1
        print(f"  ok  {description}")

    print(
        f"\nAll checks passed: {len(data['devices'])} devices across "
        f"{len(data['locations'])} locations."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

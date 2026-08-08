#!/usr/bin/env python3
"""Populate a Nautobot instance with the synthetic lab inventory.

The script is idempotent: running it repeatedly will not create duplicate
objects. It reads the inventory definition from ``devices.yml`` and talks to
Nautobot over its REST API using pynautobot.

Usage:
    export NAUTOBOT_URL="http://localhost:8080"
    export NAUTOBOT_TOKEN="<api-token>"
    python seed_nautobot.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

import pynautobot
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("seed")

SEED_FILE = Path(__file__).parent / "devices.yml"
ACTIVE_STATUS = "Active"


def get_client() -> pynautobot.api:
    """Build an authenticated Nautobot API client from the environment."""
    url = os.getenv("NAUTOBOT_URL")
    token = os.getenv("NAUTOBOT_TOKEN")

    if not url or not token:
        logger.error("NAUTOBOT_URL and NAUTOBOT_TOKEN must both be set.")
        sys.exit(1)

    client = pynautobot.api(url=url.rstrip("/"), token=token)
    client.http_session.verify = True
    return client


def ensure(endpoint: Any, lookup: dict, payload: dict) -> Any:
    """Return an existing object matching ``lookup``, creating it if absent.

    This is the core idempotency helper. Every object in the lab is created
    through it, so the seed can be re-run safely at any time.
    """
    existing = endpoint.get(**lookup)
    if existing:
        logger.debug("Exists: %s", lookup)
        return existing

    created = endpoint.create(**payload)
    logger.info("Created: %s", payload.get("name", lookup))
    return created


def seed_statuses(client: pynautobot.api) -> None:
    """Confirm that the statuses referenced by the lab are present."""
    status = client.extras.statuses.get(name=ACTIVE_STATUS)
    if not status:
        logger.error(
            "Status '%s' is missing. Nautobot normally ships with it.",
            ACTIVE_STATUS,
        )
        sys.exit(1)


def seed_locations(client: pynautobot.api, data: dict) -> dict:
    """Create the location type and every location defined in the seed file."""
    location_type = ensure(
        client.dcim.location_types,
        {"name": "Site"},
        {"name": "Site", "nestable": False},
    )

    active = client.extras.statuses.get(name=ACTIVE_STATUS)
    locations = {}

    for entry in data["locations"]:
        location = ensure(
            client.dcim.locations,
            {"name": entry["name"]},
            {
                "name": entry["name"],
                "location_type": location_type.id,
                "status": active.id,
                "time_zone": entry["time_zone"],
                "description": f"{entry['type']} ({entry['code']})",
            },
        )
        locations[entry["name"]] = location

    return locations


def seed_manufacturers_and_types(client: pynautobot.api, data: dict) -> dict:
    """Create manufacturers and their associated device types."""
    device_types = {}

    for entry in data["manufacturers"]:
        manufacturer = ensure(
            client.dcim.manufacturers,
            {"name": entry["name"]},
            {"name": entry["name"]},
        )

        for model in entry["device_types"]:
            device_type = ensure(
                client.dcim.device_types,
                {"model": model["model"]},
                {
                    "model": model["model"],
                    "manufacturer": manufacturer.id,
                    "part_number": model["part_number"],
                    "u_height": model["u_height"],
                },
            )
            device_types[model["model"]] = device_type

    return device_types


def seed_roles(client: pynautobot.api, data: dict) -> dict:
    """Create device roles, each restricted to the dcim.device content type."""
    roles = {}

    for entry in data["roles"]:
        role = ensure(
            client.extras.roles,
            {"name": entry["name"]},
            {
                "name": entry["name"],
                "color": entry["color"],
                "content_types": ["dcim.device"],
            },
        )
        roles[entry["name"]] = role

    return roles


def seed_platforms(client: pynautobot.api, data: dict) -> dict:
    """Create platforms and bind each to its manufacturer and network driver."""
    platforms = {}

    for entry in data["platforms"]:
        manufacturer = client.dcim.manufacturers.get(name=entry["manufacturer"])
        platform = ensure(
            client.dcim.platforms,
            {"name": entry["name"]},
            {
                "name": entry["name"],
                "manufacturer": manufacturer.id,
                "network_driver": entry["network_driver"],
            },
        )
        platforms[entry["name"]] = platform

    return platforms


def seed_prefixes(client: pynautobot.api, data: dict) -> None:
    """Create the IP prefixes that back the lab addressing plan."""
    active = client.extras.statuses.get(name=ACTIVE_STATUS)
    namespace = client.ipam.namespaces.get(name="Global")

    for entry in data["prefixes"]:
        ensure(
            client.ipam.prefixes,
            {"prefix": entry["prefix"]},
            {
                "prefix": entry["prefix"],
                "status": active.id,
                "namespace": namespace.id,
                "description": entry["description"],
            },
        )


def seed_devices(
    client: pynautobot.api,
    data: dict,
    locations: dict,
    device_types: dict,
    roles: dict,
    platforms: dict,
) -> None:
    """Create each device, its management interface and its management IP."""
    active = client.extras.statuses.get(name=ACTIVE_STATUS)
    namespace = client.ipam.namespaces.get(name="Global")

    for entry in data["devices"]:
        device = ensure(
            client.dcim.devices,
            {"name": entry["name"]},
            {
                "name": entry["name"],
                "location": locations[entry["location"]].id,
                "role": roles[entry["role"]].id,
                "device_type": device_types[entry["device_type"]].id,
                "platform": platforms[entry["platform"]].id,
                "status": active.id,
                "serial": entry["serial"],
            },
        )

        interface = ensure(
            client.dcim.interfaces,
            {"device_id": device.id, "name": "Management1"},
            {
                "device": device.id,
                "name": "Management1",
                "type": "1000base-t",
                "status": active.id,
                "mgmt_only": True,
                "description": "Out-of-band management interface",
            },
        )

        ip_address = ensure(
            client.ipam.ip_addresses,
            {"address": entry["management_ip"]},
            {
                "address": entry["management_ip"],
                "status": active.id,
                "namespace": namespace.id,
            },
        )

        # Bind the address to the interface, then promote it to primary.
        if not client.ipam.ip_address_to_interface.get(
            ip_address=ip_address.id, interface=interface.id
        ):
            client.ipam.ip_address_to_interface.create(
                ip_address=ip_address.id,
                interface=interface.id,
            )

        if not device.primary_ip4:
            device.primary_ip4 = ip_address.id
            device.save()
            logger.info("Set primary IP for %s", entry["name"])


def main() -> None:
    """Run the full seeding sequence in dependency order."""
    with SEED_FILE.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    client = get_client()

    logger.info("Seeding Nautobot at %s", client.base_url)
    seed_statuses(client)
    locations = seed_locations(client, data)
    device_types = seed_manufacturers_and_types(client, data)
    roles = seed_roles(client, data)
    platforms = seed_platforms(client, data)
    seed_prefixes(client, data)
    seed_devices(client, data, locations, device_types, roles, platforms)

    total = len(data["devices"])
    logger.info("Seeding complete: %d devices across %d locations.",
                total, len(data["locations"]))


if __name__ == "__main__":
    main()

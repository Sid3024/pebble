import json
import os
from pathlib import Path

from bleak import BleakScanner
from bleak.backends.device import BLEDevice

from .constants import LED_SERVICE_UUID, PEBBLE_NAME_PREFIX, PEBBLE_LED_NAME_PREFIX, SERVICE_UUID

PEBBLE_SHORT_NAME = "Pebble"
POD_CACHE_FILE = Path(".pebble_pods.json")


def _normalize_uuid(uuid: str) -> str:
    return str(uuid).strip("{}").lower()


def _matches_uuid(advertisement, uuid: str) -> bool:
    service_uuids = getattr(advertisement, "service_uuids", []) or []
    wanted = _normalize_uuid(uuid)
    return any(_normalize_uuid(found) == wanted for found in service_uuids)


def _device_name(device: BLEDevice, advertisement=None) -> str:
    return (
        getattr(device, "name", None)
        or getattr(advertisement, "local_name", None)
        or ""
    )


def _format_seen(discovered) -> list[str]:
    if isinstance(discovered, dict):
        rows = []
        for device, advertisement in discovered.values():
            name = _device_name(device, advertisement) or "<no name>"
            uuids = getattr(advertisement, "service_uuids", []) or []
            if name != "<no name>" or uuids:
                rows.append(f"{name} [{getattr(device, 'address', '?')}] uuids={list(uuids)}")
        return rows
    return [
        f"{getattr(device, 'name', None) or '<no name>'} [{getattr(device, 'address', '?')}]"
        for device in discovered
        if getattr(device, "name", None)
    ]


def _is_pebble_name(name: str) -> bool:
    return name.startswith(PEBBLE_NAME_PREFIX) or name == PEBBLE_SHORT_NAME


def load_known_pods() -> list[dict[str, str]]:
    pods: list[dict[str, str]] = []

    env_value = os.environ.get("PEBBLE_POD_ADDRESSES", "")
    for raw in env_value.split(","):
        address = raw.strip()
        if address:
            suffix = address[-8:].replace(":", "")
            pods.append({"address": address, "name": f"Pebble_{suffix}"})

    try:
        cached = json.loads(POD_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cached = []

    seen = {pod["address"] for pod in pods if pod.get("address")}
    for pod in cached:
        address = pod.get("address")
        if address and address not in seen:
            pods.append({
                "address": address,
                "name": pod.get("name") or f"Pebble_{address[-8:].replace(':', '')}",
            })
            seen.add(address)
    return pods


def save_known_pods(devices: list[BLEDevice]) -> None:
    known = {pod["address"]: pod for pod in load_known_pods() if pod.get("address")}
    for device in devices:
        address = getattr(device, "address", None)
        if not address:
            continue
        suffix = address[-8:].replace(":", "")
        known[address] = {
            "address": address,
            "name": getattr(device, "name", None) or f"Pebble_{suffix}",
        }
    try:
        POD_CACHE_FILE.write_text(
            json.dumps(list(known.values()), indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"[BLE] Could not save pod cache {POD_CACHE_FILE}: {exc}")


async def _discover(timeout: float):
    try:
        return await BleakScanner.discover(timeout=timeout, return_adv=True)
    except TypeError:
        return await BleakScanner.discover(timeout=timeout)


async def scan_for_pebbles(timeout: float = 10.0, debug: bool = False) -> list[BLEDevice]:
    """Scan for game pod MCUs by name prefix, advertised service UUID, or known cached address."""
    discovered = await _discover(timeout)
    known_addresses = {pod["address"].upper() for pod in load_known_pods()}

    if isinstance(discovered, dict):
        matches = [
            device
            for device, advertisement in discovered.values()
            if _is_pebble_name(_device_name(device, advertisement))
            or _matches_uuid(advertisement, SERVICE_UUID)
            or (known_addresses and getattr(device, "address", "").upper() in known_addresses)
        ]
    else:
        matches = [
            device
            for device in discovered
            if _is_pebble_name(_device_name(device))
            or (known_addresses and getattr(device, "address", "").upper() in known_addresses)
        ]

    if debug and not matches:
        total = len(discovered)
        hint = f"known addresses: {sorted(known_addresses)}" if known_addresses else "no cached addresses"
        print(f"[BLE] No pods found in scan ({total} nearby devices). {hint}.")
    if matches:
        save_known_pods(matches)
    return matches


async def scan_for_led_display(timeout: float = 10.0, debug: bool = False) -> list[BLEDevice]:
    """Scan for the LED display MCU by name prefix or advertised service UUID."""
    discovered = await _discover(timeout)
    if isinstance(discovered, dict):
        matches = [
            device
            for device, advertisement in discovered.values()
            if _device_name(device, advertisement).startswith(PEBBLE_LED_NAME_PREFIX)
            or _matches_uuid(advertisement, LED_SERVICE_UUID)
        ]
    else:
        matches = [
            device
            for device in discovered
            if _device_name(device).startswith(PEBBLE_LED_NAME_PREFIX)
        ]

    if debug and not matches:
        print(f"[BLE] No LED display found in scan ({len(discovered)} nearby devices).")
    return matches

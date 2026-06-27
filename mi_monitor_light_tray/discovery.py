"""Auto-discovery helper for finding Xiaomi devices on the local network.

Uses UDP broadcast to discover miio devices when the configured IP is unreachable.
"""

from __future__ import annotations

import logging
import socket
import struct
import time
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

DISCOVERY_PACKET = bytes.fromhex(
    "21310020ffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
)


@dataclass
class DiscoveredDevice:
    ip: str
    device_id: int
    model: str = ""


def discover_devices(timeout: float = 5.0) -> list[DiscoveredDevice]:
    """Broadcast UDP discovery packet and collect responses.

    Returns a list of discovered devices with IP and device ID. Does not
    require knowing the token in advance.
    """
    devices = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(0.5)

    try:
        sock.bind(("", 0))
        sock.sendto(DISCOVERY_PACKET, ("255.255.255.255", 54321))
        log.debug("Sent discovery broadcast to 255.255.255.255:54321")

        start = time.time()
        seen = set()

        while time.time() - start < timeout:
            try:
                data, addr = sock.recvfrom(1024)
                ip = addr[0]
                if ip in seen or len(data) < 32:
                    continue
                seen.add(ip)

                # Parse device ID from response header (bytes 8-12, big-endian)
                device_id = struct.unpack(">I", data[8:12])[0]
                devices.append(DiscoveredDevice(ip=ip, device_id=device_id))
                log.info("Discovered device at %s (ID: %08x)", ip, device_id)

            except socket.timeout:
                continue
            except Exception as exc:
                log.debug("Discovery recv error: %s", exc)
                continue

    except Exception as exc:
        log.warning("Discovery failed: %s", exc)
    finally:
        sock.close()

    return devices


def find_device_by_id(target_device_id: int, timeout: float = 5.0) -> Optional[str]:
    """Discover devices and return the IP of the one matching target_device_id.

    Useful when the device's IP has changed (DHCP reassignment) but you know
    the device ID from a previous successful connection.
    """
    devices = discover_devices(timeout=timeout)
    for dev in devices:
        if dev.device_id == target_device_id:
            log.info("Found target device %08x at new IP %s", target_device_id, dev.ip)
            return dev.ip
    return None

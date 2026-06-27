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


def _local_ipv4_addresses() -> list[str]:
    """Return every non-loopback IPv4 address bound to this host.

    On Windows the default route can pick a virtual adapter (VPN, Hyper-V, WSL,
    VMware) so a single 255.255.255.255 broadcast may never reach the LAN the
    light sits on. Enumerating interfaces lets us broadcast on each one.
    """
    addrs: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and ip not in addrs:
                addrs.append(ip)
    except socket.gaierror as exc:
        log.debug("getaddrinfo failed: %s", exc)
    return addrs


def discover_devices(timeout: float = 5.0) -> list[DiscoveredDevice]:
    """Broadcast UDP discovery packet and collect responses.

    Returns a list of discovered devices with IP and device ID. Does not
    require knowing the token in advance.

    Broadcasts from every local IPv4 interface, not just the default-route one,
    so a virtual adapter doesn't hide the real LAN. All sender sockets are kept
    open during the receive window so per-interface replies aren't dropped.
    """
    devices: list[DiscoveredDevice] = []
    seen: set[str] = set()

    # Always include a default-route socket bound to INADDR_ANY.
    socks: list[socket.socket] = []
    default = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    default.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    default.settimeout(0.2)
    try:
        default.bind(("", 0))
        socks.append(default)
    except OSError as exc:
        log.debug("Default socket bind failed: %s", exc)
        default.close()

    # One socket per local interface so each broadcast carries that interface's
    # source IP. Replies route back to the same socket.
    for iface_ip in _local_ipv4_addresses():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.settimeout(0.2)
        try:
            s.bind((iface_ip, 0))
            socks.append(s)
        except OSError as exc:
            log.debug("Bind on %s failed: %s", iface_ip, exc)
            s.close()

    if not socks:
        log.warning("Discovery: no usable sockets")
        return devices

    try:
        for s in socks:
            try:
                s.sendto(DISCOVERY_PACKET, ("255.255.255.255", 54321))
                log.debug("Sent discovery from %s", s.getsockname()[0] or "default")
            except OSError as exc:
                log.debug("sendto failed on %s: %s", s.getsockname(), exc)

        start = time.time()
        while time.time() - start < timeout:
            progressed = False
            for s in socks:
                try:
                    data, addr = s.recvfrom(1024)
                except socket.timeout:
                    continue
                except OSError as exc:
                    log.debug("recv error: %s", exc)
                    continue
                progressed = True
                ip = addr[0]
                if ip in seen or len(data) < 32:
                    continue
                seen.add(ip)
                device_id = struct.unpack(">I", data[8:12])[0]
                devices.append(DiscoveredDevice(ip=ip, device_id=device_id))
                log.info("Discovered device at %s (ID: %08x)", ip, device_id)
            if not progressed:
                # All sockets timed out this pass; brief sleep avoids a busy loop.
                time.sleep(0.05)
    finally:
        for s in socks:
            s.close()

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

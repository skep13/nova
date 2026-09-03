"""Find Govee lights on the LAN, using Govee's own local protocol.

Govee's LAN API is the only way to drive these that fits this device: it is
plain UDP on the local network, needs no account, no API key and no internet,
and keeps the "nothing leaves the box" rule that everything else here obeys.
Their cloud API would work too and is free, but it would put the bedroom lights
behind someone else's server and an outage.

It has to be switched on per-device first, in the Govee Home app:

    Device -> Settings (gear, top right) -> LAN Control -> on

Only some models have the option at all — the H61xx/H60xx strips and bulbs
mostly do, older and cheaper models often do not. If nothing answers, that
toggle is the first thing to check, and this prints what to do.

    python3 govee_discover.py [seconds]

The protocol, for anyone reading this later:
    discovery : send {"msg":{"cmd":"scan","data":{"account_topic":"reserve"}}}
                to 239.255.255.250:4001, listen on 4002
    control   : send to the device's own IP, port 4003
"""
import json
import socket
import struct
import sys
import time

MULTICAST = "239.255.255.250"
SEND_PORT = 4001      # devices listen for discovery here
RECV_PORT = 4002      # devices reply here
CONTROL_PORT = 4003   # commands go here, to the device's own IP

SCAN = json.dumps({"msg": {"cmd": "scan", "data": {"account_topic": "reserve"}}})


def discover(seconds=5):
    """Every Govee device that answers, as a list of dicts."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("0.0.0.0", RECV_PORT))
    # Join the multicast group on every interface, because this box has more
    # than one and the lights are only on one of them.
    listener.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                        struct.pack("=4sl", socket.inet_aton(MULTICAST),
                                    socket.INADDR_ANY))
    listener.settimeout(1.0)

    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

    found, seen = [], set()
    deadline = time.time() + seconds
    # Asked more than once: UDP is allowed to lose a packet, and a light that
    # missed the only scan looks exactly like a light that does not exist.
    while time.time() < deadline:
        try:
            sender.sendto(SCAN.encode(), (MULTICAST, SEND_PORT))
        except OSError as exc:
            print(f"  could not send discovery: {exc}")
            break
        end = min(deadline, time.time() + 1.5)
        while time.time() < end:
            try:
                raw, addr = listener.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                data = json.loads(raw.decode()).get("msg", {}).get("data", {})
            except Exception:
                continue
            ip = data.get("ip") or addr[0]
            if ip in seen:
                continue
            seen.add(ip)
            found.append({"ip": ip, "sku": data.get("sku"),
                          "device": data.get("device"),
                          "version": data.get("wifiVersionSoft")})
    listener.close()
    sender.close()
    return found


if __name__ == "__main__":
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    print(f"listening {secs}s for Govee devices on the LAN...")
    devices = discover(secs)
    if not devices:
        print("\n  Nothing answered.\n"
              "  Either LAN Control is off, or this model does not have it:\n"
              "    Govee Home app -> the light -> gear icon -> LAN Control -> on\n"
              "  It also has to be on the same network as this box.")
        sys.exit(1)
    print(f"\n  {len(devices)} device(s):")
    for d in devices:
        print(f"    {d['ip']:15}  sku={d['sku']}  id={d['device']}  fw={d['version']}")
    print("\n  Control port is 4003 on each of those addresses.")

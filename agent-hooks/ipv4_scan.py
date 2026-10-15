#!/usr/bin/env python3
"""Read 'file<TAB>added line' records on stdin; print each file that contains an
IPv4 address outside the allowlist. Used by commit-gate.sh.

Allowed: loopback 127.0.0.0/8, 0.0.0.0, the 255.255.255.x netmask forms, and
the documentation ranges 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24.
Private (RFC 1918) ranges are deliberately blocked. A match needs four octets
of 0-255, not adjacent to another digit or '.digit'.
"""
import ipaddress
import re
import sys

OCT = r"(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])"
IPV4 = re.compile(r"(?<![0-9])(?<![0-9]\.)(" + OCT + r"(?:\." + OCT + r"){3})(?![0-9])(?!\.[0-9])")
ALLOWED = [ipaddress.ip_network(n) for n in (
    "127.0.0.0/8", "0.0.0.0/32", "255.255.255.0/24",
    "192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]

bad = set()
for rec in sys.stdin:
    f, _, line = rec.rstrip("\n").partition("\t")
    for m in IPV4.finditer(line):
        ip = ipaddress.ip_address(m.group(1))
        if not any(ip in n for n in ALLOWED):
            bad.add(f)
for f in sorted(bad):
    print(f)

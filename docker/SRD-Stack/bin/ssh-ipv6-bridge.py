#!/usr/bin/env python3
"""Listen on [::1]:SSH_PORT and forward TCP to 127.0.0.1:SSH_PORT.

oc/kubectl port-forward dials [::1] inside the pod. IPv4-only sshd would
otherwise return connection refused.
"""
from __future__ import annotations

import os
import select
import socket
import sys
import threading


def pipe(a: socket.socket, b: socket.socket) -> None:
    try:
        while True:
            r, _, _ = select.select([a, b], [], [], 60)
            if not r:
                continue
            for src, dst in ((a, b), (b, a)):
                if src in r:
                    data = src.recv(65536)
                    if not data:
                        return
                    dst.sendall(data)
    except OSError:
        return
    finally:
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                s.close()
            except OSError:
                pass


def handle(client: socket.socket, port: int) -> None:
    upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        upstream.connect(("127.0.0.1", port))
    except OSError as exc:
        print(f"ssh-ipv6-bridge: upstream failed: {exc}", file=sys.stderr)
        client.close()
        return
    threading.Thread(target=pipe, args=(client, upstream), daemon=True).start()


def main() -> int:
    port = int(os.environ.get("SSH_PORT", "2022"))
    srv = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
    except OSError:
        pass
    try:
        srv.bind(("::1", port))
    except OSError as exc:
        print(f"ssh-ipv6-bridge: bind [::1]:{port} failed: {exc}", file=sys.stderr)
        return 1
    srv.listen(64)
    print(f"ssh-ipv6-bridge: [::1]:{port} -> 127.0.0.1:{port}", flush=True)
    while True:
        client, _ = srv.accept()
        threading.Thread(target=handle, args=(client, port), daemon=True).start()


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Patch jupyter-remote-desktop-proxy viewer.js to reconnect on clean closes.

Upstream only reconnects when e.detail.clean is false. Browser tab switches /
proxy idle timeouts often close the websocket cleanly, so the UI stays on
"Disconnected" until a manual refresh. See:
https://github.com/jupyterhub/jupyter-remote-desktop-proxy/issues/80
"""
from __future__ import annotations

import sys
from pathlib import Path

CANDIDATES = [
    Path("/usr/local/lib/python3.12/dist-packages/jupyter_remote_desktop_proxy/static/dist/viewer.js"),
    Path("/usr/local/lib/python3.11/dist-packages/jupyter_remote_desktop_proxy/static/dist/viewer.js"),
    Path("/usr/local/lib/python3.10/dist-packages/jupyter_remote_desktop_proxy/static/dist/viewer.js"),
]

OLD_LE = (
    'function le(e){e.detail.clean?ce("Disconnected"):(ce("Something went wrong, '
    'connection is closed"),fe<5?(ce("Reconnecting in 3 seconds"),'
    "setTimeout((()=>{de(),fe++}),3e3)):ce(\"Failed to connect, giving up\"))}"
)
NEW_LE = (
    "function le(e){fe<20?(ce(\"Disconnected — reconnecting in 3 seconds\"),"
    "setTimeout((()=>{de(),fe++}),3e3)):ce(\"Failed to connect, giving up\")}"
)
OLD_UE = 'function ue(){ce("Connected")}'
NEW_UE = 'function ue(){fe=0,ce("Connected")}'


def main() -> int:
    paths = [p for p in CANDIDATES if p.is_file()]
    if not paths:
        # fallback: search
        root = Path("/usr/local/lib")
        paths = list(root.glob("python*/dist-packages/jupyter_remote_desktop_proxy/static/dist/viewer.js"))
    if not paths:
        print("viewer.js not found", file=sys.stderr)
        return 1

    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if NEW_LE in text and NEW_UE in text:
            print(f"already patched: {path}")
            continue
        if OLD_LE not in text:
            print(f"unexpected viewer.js (le pattern missing): {path}", file=sys.stderr)
            return 2
        if OLD_UE not in text:
            print(f"unexpected viewer.js (ue pattern missing): {path}", file=sys.stderr)
            return 2
        path.write_text(
            text.replace(OLD_LE, NEW_LE).replace(OLD_UE, NEW_UE),
            encoding="utf-8",
        )
        print(f"patched: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Aegis Spatio-Temporal Memory Server Runner.

Binds the FastAPI service to 0.0.0.0:8000 for LAN / mobile device connectivity
and prints network discovery info and quick simulation presets.
"""

from __future__ import annotations

import socket

import uvicorn


def get_local_ip() -> str:
    """Detect primary LAN IPv4 address for mobile client connection."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not actually transmit packets, just routes to determine local outbound interface
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def main() -> None:
    host_ip = get_local_ip()
    port = 8000

    print("=" * 68)
    print("  🛡️  AEGIS SPATIO-TEMPORAL MEMORY SYSTEM — MID-1 PROTOTYPE SERVER")
    print("=" * 68)
    print(f"  • Localhost URL:      http://127.0.0.1:{port}")
    print(f"  • Mobile Phone URL:   http://{host_ip}:{port}")
    print(f"  • Swagger Docs:       http://{host_ip}:{port}/docs")
    print("-" * 68)
    print("  QUICK SIMULATION PRESETS FOR LIVE PRESENTATION:")
    print(f"  • [Move to Floor]:    http://{host_ip}:{port}/api/v1/simulate/floor")
    print(f"  • [Store in Cabinet]: http://{host_ip}:{port}/api/v1/simulate/cabinet")
    print(f"  • [Pick up In Hand]:  http://{host_ip}:{port}/api/v1/simulate/in_hand")
    print(f"  • [Reset to Default]: curl -X POST http://{host_ip}:{port}/api/v1/reset")
    print("=" * 68)
    print("Starting uvicorn on 0.0.0.0:8000 with CORS enabled for mobile client...\n")

    uvicorn.run(
        "aegis.remote.api:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()

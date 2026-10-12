"""Aegis Spatio-Temporal Memory Server Runner.

Binds the FastAPI service to 0.0.0.0:8000 for LAN / mobile device connectivity
and prints network discovery info and quick simulation presets.
"""

from __future__ import annotations

import argparse
import os
import socket

import uvicorn

from aegis.remote.api import (
    find_latest_objects_state,
    list_available_datasets,
    load_scene_graph_data,
    set_active_dataset,
)


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
    parser = argparse.ArgumentParser(description="Aegis Spatio-Temporal Memory Server")
    parser.add_argument(
        "--dataset-id",
        type=str,
        default=os.getenv("AEGIS_DATASET_ID", "Demo06-Self"),
        help="Dataset identifier to load as primary scene graph (e.g. Demo06-Self, demo01, demo03)",
    )
    parser.add_argument("--port", type=int, default=8000, help="Port to bind server")
    args = parser.parse_args()

    dataset_id = args.dataset_id
    set_active_dataset(dataset_id)
    os.environ["AEGIS_DATASET_ID"] = dataset_id

    # Load dynamic scene graph info
    sg = load_scene_graph_data(dataset_id)
    anchors = [a.get("label", "") for a in sg.get("anchors", [])]
    latest = find_latest_objects_state(sg)
    objects = sorted(
        {obj.get("label", "") for obj in latest.values() if obj.get("label")}
    )
    available_datasets = list_available_datasets()

    host_ip = get_local_ip()
    port = args.port

    print("=" * 68)
    print("  🛡️  AEGIS SPATIO-TEMPORAL MEMORY SYSTEM — SERVER RUNNER")
    print("=" * 68)
    print(f"  • Primary Dataset:     {dataset_id}")
    print(f"  • Available Datasets:  {', '.join(available_datasets)}")
    print(f"  • Grounded Anchors:    {', '.join(anchors) if anchors else 'None'}")
    print(f"  • Tracked Objects:     {', '.join(objects) if objects else 'None'}")
    print(f"  • Localhost URL:       http://127.0.0.1:{port}")
    print(f"  • LAN Mobile URL:      http://{host_ip}:{port}")
    print(f"  • Swagger Docs:        http://{host_ip}:{port}/docs")
    print(
        f"  • Dataset Switch API:  POST http://{host_ip}:{port}/api/v1/dataset/select?dataset_id=<id>"
    )
    print("-" * 68)
    print(f"  PRESETS FOR [{dataset_id.upper()}]:")
    if dataset_id == "Demo06-Self":
        print(
            f"  • [Bottle on Desk 1]: http://{host_ip}:{port}/api/v1/simulate/bottle_table1"
        )
        print(
            f"  • [Bottle Occluded]:  http://{host_ip}:{port}/api/v1/simulate/bottle_occluded"
        )
        print(
            f"  • [Bottle on Desk 2]: http://{host_ip}:{port}/api/v1/simulate/bottle_table2"
        )
    else:
        print(
            f"  • [Move to Floor]:    http://{host_ip}:{port}/api/v1/simulate/floor?dataset_id={dataset_id}"
        )
        print(
            f"  • [Store in Anchor]:  http://{host_ip}:{port}/api/v1/simulate/cabinet?dataset_id={dataset_id}"
        )
        print(
            f"  • [Pick up In Hand]:  http://{host_ip}:{port}/api/v1/simulate/in_hand?dataset_id={dataset_id}"
        )
    print(
        f"  • [Reset Graph]:      curl -X POST http://{host_ip}:{port}/api/v1/reset?dataset_id={dataset_id}"
    )
    print("=" * 68)
    print(f"Starting uvicorn on 0.0.0.0:{port} for dataset {dataset_id}...\n")

    uvicorn.run(
        "aegis.remote.api:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()

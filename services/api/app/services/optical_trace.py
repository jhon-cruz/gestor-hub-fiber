"""Graph traversal and estimated optical-loss budget for modeled topology."""

import math
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from app.models.fiber_topology import (
    FiberConnection,
    FiberConnectionEndpoint,
    FiberPortLink,
    OpticalCable,
    OpticalFiber,
)
from app.models.optical import OpticalDevice, OpticalPort


@dataclass(frozen=True)
class Edge:
    target: str
    kind: str
    label: str
    loss_db: float
    length_m: float = 0
    estimated: bool = False


def _connect(graph: dict[str, list[Edge]], source: str, edge: Edge) -> None:
    graph[source].append(edge)
    graph[edge.target].append(
        Edge(source, edge.kind, edge.label, edge.loss_db, edge.length_m, edge.estimated)
    )


def _fiber_node(fiber_id: uuid.UUID, side: str) -> str:
    return f"fiber:{fiber_id}:{side}"


def _port_node(port_id: uuid.UUID, side: str) -> str:
    return f"port:{port_id}:{side}"


def build_trace_graph(
    db,
) -> tuple[dict[str, list[Edge]], dict[str, str], dict[uuid.UUID, OpticalPort]]:
    graph: dict[str, list[Edge]] = defaultdict(list)
    labels: dict[str, str] = {}
    cables = {item.id: item for item in db.scalars(select(OpticalCable))}
    fibers = list(db.scalars(select(OpticalFiber)))
    ports = {item.id: item for item in db.scalars(select(OpticalPort))}
    devices = {item.id: item for item in db.scalars(select(OpticalDevice))}

    for fiber in fibers:
        cable = cables[fiber.cable_id]
        node_a = _fiber_node(fiber.id, "a")
        node_b = _fiber_node(fiber.id, "b")
        fiber_name = f"{cable.name} · FO {fiber.global_position}"
        labels[node_a] = f"{fiber_name} · ponta A"
        labels[node_b] = f"{fiber_name} · ponta B"
        attenuation = float(cable.properties.get("attenuation_db_per_km", 0.35))
        length_m = float(cable.measured_length_m or 0)
        _connect(
            graph,
            node_a,
            Edge(
                node_b,
                "fiber",
                fiber_name,
                round(attenuation * length_m / 1000, 4),
                length_m,
                cable.measured_length_m is None,
            ),
        )

    connections = {item.id: item for item in db.scalars(select(FiberConnection))}
    endpoints_by_connection: dict[uuid.UUID, list[FiberConnectionEndpoint]] = defaultdict(list)
    for endpoint in db.scalars(select(FiberConnectionEndpoint)):
        endpoints_by_connection[endpoint.connection_id].append(endpoint)
    for connection_id, endpoints in endpoints_by_connection.items():
        if len(endpoints) != 2:
            continue
        connection = connections[connection_id]
        first, second = sorted(endpoints, key=lambda item: item.role)
        _connect(
            graph,
            _fiber_node(first.fiber_id, first.end_side),
            Edge(
                _fiber_node(second.fiber_id, second.end_side),
                connection.connection_type,
                f"{connection.connection_type.title()} em caixa",
                float(connection.loss_db),
            ),
        )

    for link in db.scalars(select(FiberPortLink)):
        port = ports.get(link.port_id)
        if port is None:
            continue
        device = devices[port.device_id]
        port_node = _port_node(port.id, link.port_side)
        labels[port_node] = f"{device.name} · {port.label or f'Porta {port.position}'}"
        _connect(
            graph,
            _fiber_node(link.fiber_id, link.fiber_end),
            Edge(
                port_node,
                "termination",
                labels[port_node],
                float(link.insertion_loss_db),
            ),
        )

    ports_by_device: dict[uuid.UUID, list[OpticalPort]] = defaultdict(list)
    for port in ports.values():
        ports_by_device[port.device_id].append(port)
    for device_id, device_ports in ports_by_device.items():
        device = devices[device_id]
        if device.device_type == "dio":
            loss = float(device.properties.get("adapter_loss_db", 0.2))
            for port in device_ports:
                node_a, node_b = _port_node(port.id, "a"), _port_node(port.id, "b")
                labels.setdefault(
                    node_a, f"{device.name} · {port.label or f'Porta {port.position}'} A"
                )
                labels.setdefault(
                    node_b, f"{device.name} · {port.label or f'Porta {port.position}'} B"
                )
                _connect(graph, node_a, Edge(node_b, "adapter", device.name, loss, estimated=True))
        elif device.device_type == "splitter":
            inputs = [item for item in device_ports if item.port_kind == "splitter_input"]
            outputs = [item for item in device_ports if item.port_kind == "splitter_output"]
            if not inputs or not outputs:
                continue
            theoretical = round(10 * math.log10(len(outputs)) + 1.0, 3)
            loss = float(device.properties.get("splitter_loss_db", theoretical))
            input_node = _port_node(inputs[0].id, "a")
            labels.setdefault(input_node, f"{device.name} · entrada")
            for output in outputs:
                output_node = _port_node(output.id, "a")
                labels.setdefault(output_node, f"{device.name} · saída {output.position}")
                _connect(
                    graph,
                    input_node,
                    Edge(
                        output_node,
                        "splitter",
                        f"{device.name} · 1:{len(outputs)}",
                        loss,
                        estimated="splitter_loss_db" not in device.properties,
                    ),
                )
    return graph, labels, ports


def trace_from_port(
    db,
    port_id: uuid.UUID,
    tx_power_dbm: float,
    receiver_min_dbm: float,
) -> dict[str, Any]:
    graph, labels, ports = build_trace_graph(db)
    if port_id not in ports:
        raise KeyError("optical port not found")
    start_nodes = [node for node in graph if node.startswith(f"port:{port_id}:")]
    paths: list[dict[str, Any]] = []

    def walk(node: str, visited: set[str], steps: list[dict[str, Any]]) -> None:
        if len(steps) >= 256 or len(paths) >= 256:
            return
        candidates = [edge for edge in graph.get(node, []) if edge.target not in visited]
        is_other_port = node.startswith("port:") and node not in start_nodes
        if (is_other_port and not candidates) or (not candidates and steps):
            total_loss = round(sum(item["loss_db"] for item in steps), 3)
            length_m = round(sum(item["length_m"] for item in steps), 2)
            received = round(tx_power_dbm - total_loss, 3)
            paths.append(
                {
                    "destination": labels.get(node, node),
                    "destination_node": node,
                    "total_loss_db": total_loss,
                    "length_m": length_m,
                    "received_power_dbm": received,
                    "margin_db": round(received - receiver_min_dbm, 3),
                    "estimated": any(item["estimated"] for item in steps),
                    "complete": is_other_port,
                    "steps": steps,
                }
            )
            return
        for edge in candidates:
            walk(
                edge.target,
                visited | {edge.target},
                steps
                + [
                    {
                        "kind": edge.kind,
                        "label": edge.label,
                        "from": labels.get(node, node),
                        "to": labels.get(edge.target, edge.target),
                        "loss_db": edge.loss_db,
                        "length_m": edge.length_m,
                        "estimated": edge.estimated,
                    }
                ],
            )

    for start in start_nodes:
        walk(start, {start}, [])
    paths.sort(key=lambda item: (item["total_loss_db"], item["destination"]))
    return {
        "source_port_id": str(port_id),
        "tx_power_dbm": tx_power_dbm,
        "receiver_min_dbm": receiver_min_dbm,
        "paths": paths,
        "complete": any(path["complete"] for path in paths),
        "notice": (
            "Estimativa operacional: comprimentos, atenuação e perdas padrão devem ser "
            "confirmados com dados do fabricante e medições de campo."
        ),
    }

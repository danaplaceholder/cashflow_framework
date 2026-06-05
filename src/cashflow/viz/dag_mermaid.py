"""
Build a Mermaid `flowchart LR` string from a Pydantic container of graph nodes.

Example:

    from cashflow.models.example import ExampleCashflowModel
    from cashflow.viz.dag_mermaid import model_to_mermaid

    m = ExampleCashflowModel(graph_cache_key="g")
    print(model_to_mermaid(m))

Paste the result into a Mermaid viewer (e.g. GitHub markdown, Mermaid Live Editor).
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel

from cashflow.models.base import BaseSubModule
from cashflow.nodes.base import BaseNode

_ID_SANITIZE = re.compile(r"[^0-9a-zA-Z_]")


def _sanitize_mermaid_id(raw: str) -> str:
    s = _ID_SANITIZE.sub("_", raw)
    s = s.strip("_") or "node"
    if s[0].isdigit():
        s = f"n_{s}"
    return s


def _iter_input_base_node_refs(obj: Any) -> Iterator[BaseNode]:
    if isinstance(obj, BaseNode):
        yield obj
        return
    if isinstance(obj, BaseModel):
        for name in obj.model_fields:
            yield from _iter_input_base_node_refs(getattr(obj, name))
        return
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_input_base_node_refs(v)
        return
    if isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _iter_input_base_node_refs(item)
        return


def _build_registry(nodes: BaseModel) -> dict[int, tuple[str, str]]:
    """
    Map id(node) -> (mermaid_id, display label) for each BaseNode field on `nodes`.
    """
    out: dict[int, tuple[str, str]] = {}
    for field_name in nodes.model_fields:
        v = getattr(nodes, field_name, None)
        if isinstance(v, BaseNode):
            node_hash = v.get_hash()
            node_id = _sanitize_mermaid_id(field_name) + "_" + node_hash
            head = f"{field_name}: {node_hash}"
            if v.input_node_hashes:
                lines = "input_node_hashes: \n" + "\n".join(
                    f"    {h_name}: {h_val}" for h_name, h_val in v.input_node_hashes.items()
                )
                label = f"{head}\n (\n{lines}\n)"
            else:
                label = head
            out[id(v)] = (node_id, label)
    return out


def nodes_to_mermaid(nodes: BaseModel) -> str:
    """
    Directed edges: upstream `BaseNode` dependency -> consuming `BaseNode` (left to right
    in typical `flowchart LR` renderings: roots on the left).
    """
    reg = _build_registry(nodes)
    if not reg:
        return "flowchart LR\n  %% empty: no BaseNode fields on container\n"

    lines: list[str] = ["flowchart LR", ""]
    for mid, label in sorted(reg.values(), key=lambda x: x[0]):
        safe_label = label.replace('"', "'")
        lines.append(f'  {mid}["{safe_label}"]')

    edges: set[tuple[str, str]] = set()
    for field_name in nodes.model_fields:
        v = getattr(nodes, field_name, None)
        if not isinstance(v, BaseNode):
            continue
        consumer_id = id(v)
        if consumer_id not in reg:
            continue
        to_mid = reg[consumer_id][0]
        # this is were it actually looks at each node's input
        for dep in _iter_input_base_node_refs(v.input):
            did = id(dep)
            if did not in reg or did == consumer_id:
                continue
            from_mid = reg[did][0]
            # this is where it adds the edge to the graph
            edges.add((from_mid, to_mid))

    for a, b in sorted(edges):
        lines.append(f"  {a} --> {b}")

    lines.append("")
    return "\n".join(lines)


def model_to_mermaid(model: BaseSubModule) -> str:
    return nodes_to_mermaid(model._nodes)

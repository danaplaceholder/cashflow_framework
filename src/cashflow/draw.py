"""
Computational graph visualizer/drawing
    Written by ai with guidance from danaplaceholder
"""
from base import BaseNode, ElementStatus
import atexit
import re
import subprocess
import tempfile
import time
from pathlib import Path

color_key_legend = {}
color_key_legend[ElementStatus.CREATED] = "#888780"
color_key_legend[ElementStatus.CHECKING_IF_SHOULD_EXIST] = "#d3d2cb"
# light blue
color_key_legend[ElementStatus.CHECKING_IF_SHOULD_RECOMPUTE_OUTPUT] = "#a0e6e6"
color_key_legend[ElementStatus.COMPUTING_OUTPUT] = "#f9c74f"
color_key_legend[ElementStatus.UPDATING_OUTPUT] = "#577590"
color_key_legend[ElementStatus.WAITING_FOR_INPUT] = "#f8961e"
color_key_legend[ElementStatus.COMPLETED] = "#90be6d"
color_key_legend[ElementStatus.DELETED] = "#f94144"
color_key_legend[ElementStatus.STATIC] = "#d3d2cb"
color_cluster_fill = "#F1EFE8"

_TMP_DIR: str | None = None
_EXPORT_REGISTERED = False
_D2_KEY_RE = re.compile(r"[^A-Za-z0-9_]")


def _ensure_tmp_dir() -> str:
    global _TMP_DIR, _EXPORT_REGISTERED
    if _TMP_DIR is None:
        _TMP_DIR = tempfile.mkdtemp(prefix="cashflow_draw_")
    if not _EXPORT_REGISTERED:
        atexit.register(export_video)
        _EXPORT_REGISTERED = True
    return _TMP_DIR


def export_video() -> None:
    if _TMP_DIR is None:
        return
    tmp = Path(_TMP_DIR)
    svgs = sorted(tmp.glob("*.svg"))
    if not svgs:
        return

    for svg in svgs:
        subprocess.run(
            ["rsvg-convert", str(svg), "-o", str(svg.with_suffix(".png"))],
            check=True,
        )

    timestamp = int(time.time())
    out_path = Path.cwd() / f"output_{timestamp}.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-framerate", "24",
            "-pattern_type", "glob",
            "-i", "*.png",
            "-vf", "scale=iw*8:ih*8:flags=neighbor,pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            str(out_path),
        ],
        cwd=tmp,
        check=True,
    )
    print(f"Saved animation to {out_path}")


def _parse_status(name: str) -> ElementStatus:
    return ElementStatus(name.rsplit("__", 1)[-1])


def get_color_for_status(status: ElementStatus | str) -> str:
    if not isinstance(status, ElementStatus):
        status = ElementStatus(status)
    return color_key_legend[status]


def _d2_key(name: str) -> str:
    key = _D2_KEY_RE.sub("_", name)
    if not key or key[0].isdigit():
        key = f"n_{key}"
    return key


def _escape_d2_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _shape_block(name: str, *, is_container: bool, indent: str) -> list[str]:
    stroke = get_color_for_status(_parse_status(name))
    fill = color_cluster_fill if is_container else "#ffffff"
    label = _escape_d2_string(name)
    return [
        f'{indent}label: "{label}"',
        f"{indent}style: {{",
        f"{indent}  border-radius: 8",
        f'{indent}  fill: "{fill}"',
        f'{indent}  stroke: "{stroke}"',
        f"{indent}  stroke-width: 6",
        f"{indent}  font-size: 14",
        f"{indent}  bold: true",
        f"{indent}}}",
    ]


def _to_d2(nodes: dict, contains: dict, edges: list[tuple[str, str]]) -> str:
    container_ids = {cid for cid, kids in contains.items() if kids}
    parent_of: dict[str, str] = {}
    for parent, kids in contains.items():
        for kid in kids:
            parent_of[kid] = parent

    def path_of(nid: str) -> str:
        parts = [_d2_key(nid)]
        cur = nid
        while cur in parent_of:
            cur = parent_of[cur]
            parts.append(_d2_key(cur))
        return ".".join(reversed(parts))

    lines = [
        "direction: right",
        "vars: {",
        "  d2-config: {",
        "    layout-engine: elk",
        "    theme-id: 0",
        "  }",
        "}",
        'style.fill: "#ffffff"',
        "",
    ]

    def emit_container(cid: str, indent: str) -> None:
        key = _d2_key(cid)
        lines.append(f"{indent}{key}: {{")
        lines.extend(_shape_block(cid, is_container=True, indent=indent + "  "))
        for child in contains.get(cid, []):
            if child in container_ids:
                emit_container(child, indent + "  ")
            else:
                ckey = _d2_key(child)
                lines.append(f"{indent}  {ckey}: {{")
                lines.extend(_shape_block(child, is_container=False, indent=indent + "    "))
                lines.append(f"{indent}  }}")
        lines.append(f"{indent}}}")

    nested = set(parent_of)
    roots = [cid for cid in container_ids if cid not in nested]
    for cid in roots:
        emit_container(cid, "")

    placed = nested | container_ids
    for nid in nodes:
        if nid not in placed:
            key = _d2_key(nid)
            lines.append(f"{key}: {{")
            lines.extend(_shape_block(nid, is_container=False, indent="  "))
            lines.append("}")

    lines.append("")
    seen: set[tuple[str, str]] = set()
    for src, dst in edges:
        s_path, d_path = path_of(src), path_of(dst)
        if s_path == d_path or (s_path, d_path) in seen:
            continue
        seen.add((s_path, d_path))
        lines.append(f"{s_path} -> {d_path}: {{")
        lines.append('  style.stroke: "#888780"')
        lines.append("  style.stroke-width: 2")
        lines.append("}")

    return "\n".join(lines) + "\n"


def build(nodes, contains, edges, filename="graph"):
    tmp = Path(_ensure_tmp_dir())
    d2_path = tmp / f"{filename}.d2"
    svg_path = tmp / f"{filename}.svg"
    d2_path.write_text(_to_d2(nodes, contains, edges), encoding="utf-8")
    subprocess.run(
        ["d2", "--layout=elk", "--theme=0", str(d2_path), str(svg_path)],
        check=True,
    )
    return svg_path


def build_graph(node: BaseNode):

    def walk(node: BaseNode):
       nodes[node.element_name()] = node.element_name()
       output = node._output
       input = node.input
       if input:
           for field_name, field_info in input.__class__.model_fields.items():
             value = getattr(input, field_name)
             if isinstance(value, BaseNode):
               edges.append((value.element_name(), node.element_name()))
             elif isinstance(value, list ):
               for item in value:
                 edges.append((item.element_name(), node.element_name()))
       if output:
           contains[node.element_name()] = []
           for field_name, field_info in output.__class__.model_fields.items():
             value = getattr(output, field_name)
             if isinstance(value, BaseNode):
               contains[node.element_name()].append(value.element_name())
               walk(value)
             elif isinstance(value, list ):
               for item in value:
                 if isinstance(item, BaseNode):
                     contains[node.element_name()].append(item.element_name())
                     walk(item)

    nodes = {}
    contains = {}
    edges = []
    walk(node)
    build(nodes=nodes, contains=contains, edges=edges, filename=f"trade_analysis_graph{ time.time() }")

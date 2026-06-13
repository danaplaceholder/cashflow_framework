import pydot


def _fill_for(type_name: str) -> str:
    if "DbAccess" in type_name:
        return "#E1F5EE"   # teal 50
    if "Calculation" in type_name:
        return "#FAEEDA"   # amber 50
    return "#F1EFE8"       # gray 50


def _render_registry(reg, path):
    g = pydot.Dot(
    graph_type="digraph",
    rankdir="TB",            # back to vertical — more compact at this size
    compound="true",
    splines="ortho",      # fixes the invisible fmv edge
    nodesep="0.4",
    ranksep="0.6",
    bgcolor="transparent",
    fontname="sans-serif",   # SVG-safe
    fontnames="svg",         # emit generic names, no Times fallback
    concentrate="true",
)
    # defaults applied to every node/edge added after — the universal form,
    # works on all pydot versions (set_node_defaults is version-flaky)
    g.add_node(pydot.Node(
        "node", shape="box", style="rounded,filled", fontname="Helvetica",
        fontsize="11", margin="0.15,0.08", penwidth="0.5",
    ))
    g.add_node(pydot.Node(
        "edge", fontname="Helvetica", fontsize="10", penwidth="0.8", arrowsize="0.7",
    ))

    children = {}
    for p, c in reg["contains"]:
        children.setdefault(p, []).append(c)
    child_ids = {c for _, c in reg["contains"]}
    roots = [u for u in reg["units"] if u not in child_ids]

    cluster_name = {}
    anchor = {}

    def emit(uid, parent_graph):
        kids = children.get(uid)
        name = type(reg["units"][uid]).__name__
        if kids:
            cname = f"cluster_{uid}"
            cluster_name[uid] = cname
            sub = pydot.Cluster(
                str(uid), label=name, labelloc="t",
                style="filled", fillcolor="#E6F1FB", color="#185FA5", penwidth="0.5",
                fontname="Helvetica", fontsize="12",
            )
            a = f"__anchor_{uid}"
            anchor[uid] = a
            sub.add_node(pydot.Node(a, shape="point", style="invis", width="0"))
            for k in kids:
                emit(k, sub)
            parent_graph.add_subgraph(sub)
        else:
            parent_graph.add_node(pydot.Node(
                str(uid), label=name, fillcolor=_fill_for(name),
            ))

    for r in roots:
        emit(r, g)

    def endpoint(uid):
        return anchor.get(uid, str(uid))

    for dep, con, field in reg["edges"]:
        e = pydot.Edge(endpoint(dep), endpoint(con), label=field)
        if dep in cluster_name:
            e.set_ltail(cluster_name[dep])
        if con in cluster_name:
            e.set_lhead(cluster_name[con])
        g.add_edge(e)

    try:
        g.write_svg(path)
    except OSError as e:
        if "dot" in str(e).lower():
            raise RuntimeError(
                "Graphviz is required to render SVG. "
                "Install the system package (e.g. apt install graphviz, brew install graphviz)."
            ) from e
        raise
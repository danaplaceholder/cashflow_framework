"""
graph visualizer/drawing
by Dana K
by ai
"""
from base import BaseNode, ElementStatus
import graphviz
import os
import time
"""
for f in *.svg; do rsvg-convert "$f" -o "${f%.svg}.png"; done 
ffmpeg -framerate 24 -pattern_type glob -i '*.png'  -vf "scale=iw*8:ih*8:flags=neighbor,pad=ceil(iw/2)*2:ceil(ih/2)*2"  -c:v libx264 -pix_fmt yuv420p out5.mp4
"""

# -------------------------------------Visualization-------------------------------------
#class FirmEconomicsNode(BaseNode):
#    class Input(BaseNode.Input):
#        trade_analysis_node: TradeAnalysisNode
#        firm_info_node: FirmInfoNode
#    class Output(BaseNode.Output):
#        firm_economics: FirmEconomics
#    def _compute_output(self) -> Output:
#        return self.Output(firm_economics=FirmEconomics(trade_analysis=self.input.trade_analysis_node.output.trade_analysis, firm_info=self.input.firm_info_node.output.firm_info))
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
color_key_legend[ElementStatus.STATIC] = "#000000"
color_black = "#000000"
color_cluster_fill = "#F1EFE8"

def _parse_status(name: str) -> ElementStatus:
    return ElementStatus(name.rsplit("_STATUS_", 1)[-1])

def get_color_for_status(status: ElementStatus | str) -> str:
    if not isinstance(status, ElementStatus):
        status = ElementStatus(status)
    return color_key_legend[status]

def _node_attrs(name: str) -> dict:
    return dict(
        shape="box",
        style="rounded,filled,bold",
        fontname="Helvetica",
        fontsize="11",
        margin="0.18,0.10",
        fillcolor=get_color_for_status(_parse_status(name)),
        color=color_black,
        penwidth="2",
    )

def _default_node_attrs() -> dict:
    attrs = _node_attrs(f"x_STATUS_{ElementStatus.CREATED.value}")
    return attrs

def _cluster_attrs(name: str) -> dict:
    return dict(
        style="rounded,filled,bold",
        fillcolor=color_cluster_fill,
        color=color_black,
        penwidth="2",
        fontname="Helvetica",
        fontsize="12",
        labeljust="l",
    )

def build(nodes, contains, edges, filename="graph",
          rankdir="LR", engine="dot", ranksep="0.9", nodesep="0.4"):

    g = graphviz.Digraph("g", format="svg", engine=engine)
    g.attr(rankdir=rankdir, compound="true", splines="spline",
           nodesep=nodesep, ranksep=ranksep, newrank="true")
    g.attr("node", **_default_node_attrs())
    

    container_ids = {cid for cid, kids in contains.items() if kids}

    def first_leaf(cid):
        for ch in contains.get(cid, []):
            return first_leaf(ch) if ch in container_ids else ch
        return cid

    def emit(parent_graph, cid):
        with parent_graph.subgraph(name=f"cluster_{cid}") as c:
            c.attr("node", **_default_node_attrs())
            c.attr(label=nodes.get(cid, cid), **_cluster_attrs(cid))
            for child in contains[cid]:
                if child in container_ids:
                    emit(c, child)
                else:
                    c.node(child, nodes.get(child, child), **_node_attrs(child))

    nested = {ch for kids in contains.values() for ch in kids}
    for cid in container_ids:
        if cid not in nested:
            emit(g, cid)

    placed = nested | container_ids
    for nid, label in nodes.items():
        if nid not in placed:
            g.node(nid, label, **_node_attrs(nid))
    for src, dst in edges:
        kw = {"color": "#888780", "penwidth": "0.8", "arrowsize": "0.7"}
        s, d = src, dst
        if src in container_ids:
            s = first_leaf(src); kw["ltail"] = f"cluster_{src}"
        if dst in container_ids:
            d = first_leaf(dst); kw["lhead"] = f"cluster_{dst}"
        g.edge(s, d, **kw)

    g.render(filename, cleanup=True)
    print(f"{ os.path.join(os.path.dirname(__file__), filename)}")
    return g



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


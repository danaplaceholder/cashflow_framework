from pydantic import BaseModel
from typing import List, Dict, Any
from pydantic import PrivateAttr
from pydantic import Field
import os
import time
import graphviz
from enum import StrEnum

class Fingerprint(BaseModel):
    value: str
    _timestamp: float = PrivateAttr(default=time.time())
    def is_less_than_100ms_old(self) -> bool:
        fingerprint_age = time.time() - self._timestamp
        if fingerprint_age < 0.1:
            print(f"Fingerprint is less than 100ms old: {fingerprint_age}")
            return True
        else:
            print(f"Fingerprint is not less than 100ms old: {fingerprint_age}")
            return False

class ElementStatus(StrEnum):
    CREATED = "created"
    CHECKING_IF_SHOULD_EXIST = "checking_if_should_exist"
    CHECKING_IF_SHOULD_RECOMPUTE_OUTPUT = "checking_if_should_recompute_output"
    COMPUTING_OUTPUT = "computing_output"
    UPDATING_OUTPUT = "updating_output"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETED = "completed"
    DELETED = "deleted"

class BaseGraphElement(BaseModel):

    _status: ElementStatus = PrivateAttr(default=ElementStatus.CREATED)
    config: 'BaseGraphElement.GraphElementConfig' = Field(default=None)
    input: 'BaseGraphElement.Input' = Field(default=None)
    _output: 'BaseGraphElement.Output' = PrivateAttr(default=None)
    _last_input_fingerprint: Fingerprint = PrivateAttr(default=None)
    created_by: 'BaseGraphElement' = None

    def root_node(self) -> 'BaseGraphElement':
        if self.created_by is None:
            return self
        else:
            return self.created_by.root_node()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_status(ElementStatus.CREATED)
    
    def set_status(self, status: ElementStatus) -> None:
        if self._status == status:
            return
        self._status = status
        # render the graph with the new status
        if status in [ElementStatus.CREATED, ElementStatus.COMPUTING_OUTPUT, ElementStatus.COMPLETED, ElementStatus.DELETED, ElementStatus.WAITING_FOR_INPUT]:
            build_graph(self.root_node())

    def config_hash(self) -> str:
        return self.config.hash() if self.config else ""

    def element_name(self) -> str:
        return self.__class__.__name__ + "_" +  self.config_hash() + "_STATUS_" + self._status.value

    class GraphElementConfig(BaseModel):
        element_name: str = Field(default=None)
        def hash(self) -> str:
            return f''.join([field_name+str(getattr(self, field_name)) for field_name, field_info in self.__class__.model_fields.items() if getattr(self, field_name) is not None])
            
    class Input(BaseModel):
        def recursive_input_fingerprint(self) -> Fingerprint:
            print(f"recursive_input_fingerprint ")
            all_fields_fingerprints = []
            for field_name, field_info in self.__class__.model_fields.items():
                value = getattr(self, field_name)
                if isinstance(value, list):
                    all_fields_fingerprints.append({item.recursive_output_fingerprint() for item in value})
                elif isinstance(value, BaseGraphElement):
                    all_fields_fingerprints.append(value.recursive_output_fingerprint())
                else:
                    all_fields_fingerprints.append(str(value))
            return Fingerprint(value=f''.join(all_fields_fingerprints))

    class Output(BaseModel):
        def contains(self, node: 'BaseGraphElement') -> bool:
            for field_name, field_info in self.__class__.model_fields.items():
                value = getattr(self, field_name)
                if isinstance(value, list):
                    for item in value:
                        if item.identity_key() == node.identity_key():
                            return True
                elif isinstance(value, BaseGraphElement):
                    if value == node:
                        return True                
            return False
        def update(self, new_output: 'BaseGraphElement.Output') -> None:
            print(f"updating output {self.model_fields.keys()} with {new_output.model_fields.keys()}")
            if type(self) != type(new_output):
                raise ValueError(f"new_output must be of type {type(self)}")
            for field_name, field_info in self.__class__.model_fields.items():
                old_value = getattr(self, field_name)
                new_value = getattr(new_output, field_name)
                if isinstance(old_value, list) and issubclass(old_value[0].__class__, BaseGraphElement):
                    old_dict = {item.identity_key(): item for item in old_value}
                    new_dict = {item.identity_key(): item for item in new_value}
                    updated_list = []
                    for id_key in set(new_dict.keys()) | set(old_dict.keys()):
                        if id_key in new_dict:
                            if id_key not in old_dict:
                                updated_list.append(new_dict[id_key])
                            elif old_dict[id_key].input != new_dict[id_key].input: # any change in input... coming from diff instances of the same node.... should make us use the new instance
                                old_dict[id_key].set_input(new_dict[id_key].input) # hook up new input to old node 
                                updated_list.append(old_dict[id_key])
                            else:
                                updated_list.append(old_dict[id_key])
                        else:
                            old_dict[id_key].set_status(ElementStatus.DELETED)
                    setattr(self, field_name, updated_list)
                elif isinstance(old_value, BaseGraphElement):
                    if old_value.input != new_value.input:
                        old_value.set_input(new_value.input) # hook up new input to old node 
                else:
                    setattr(self, field_name, getattr(new_output, field_name))

    @property
    def output(self) -> Output:
        if not self.should_exist():
            return None
            raise ValueError(f"Node {self.config_hash()} of class {self.__class__.__name__} should not exist")
        if self._output is None:
            print(f"-----like 123 here?-----")
            self._last_input_fingerprint = self.recursive_input_fingerprint()
            self._output = self._outer_compute_output()
        elif self.should_recompute_output():
            print(f"-----like 456 here?-----")
            self._output.update(self._outer_compute_output())
        else:
            self.set_status(ElementStatus.COMPLETED)
        return self._output

    def identity_key(self) -> str:
        return self.created_by_identity_key() + self.__class__.__name__ + self.config_hash()

    def created_by_identity_key(self) -> str:
        return self.created_by.identity_key() if self.created_by else ""

    def _compute_output(self) -> Output:
        pass
    def _outer_compute_output(self) -> Output:
        self.set_status(ElementStatus.COMPUTING_OUTPUT)
        computed_output = self._compute_output()
        self.set_status(ElementStatus.COMPLETED)
        return computed_output

    def recursive_input_fingerprint(self) -> str:
        if self.input is None:
            return None
        elif self._last_input_fingerprint is not None and self._last_input_fingerprint.is_less_than_100ms_old():
            return self._last_input_fingerprint
        else:
            print(f"-------------------------------- getting new input fingerprint for {self.element_name()} --------------------------------")
            next_input_fingerprint = self.input.recursive_input_fingerprint()

            return next_input_fingerprint
    
    def set_input(self, new_input: Input) -> None:
        self.input = new_input
        self._last_input_fingerprint = self.recursive_input_fingerprint()

    def recursive_output_fingerprint(self) -> str:        
        
        fingerprint_dict = {}
        output = self.output
        if output is None:
            return "NONE"
        for field_name, field_info in output.__class__.model_fields.items():
            if isinstance(getattr(output, field_name), list) and issubclass(getattr(output, field_name)[0].__class__, BaseGraphElement):
                fingerprint_dict[field_name] = {item.recursive_output_fingerprint() for item in getattr(output, field_name)}
            elif isinstance(getattr(output, field_name), BaseGraphElement):
                fingerprint_dict[field_name] = getattr(output, field_name).recursive_output_fingerprint()
            elif isinstance(getattr(output, field_name), list) and issubclass(getattr(output, field_name)[0].__class__, BaseDataElement):
                fingerprint_dict[field_name] = {item.recursive_output_fingerprint() for item in getattr(output, field_name)}
            elif isinstance(getattr(output, field_name), BaseDataElement):
                fingerprint_dict[field_name] = getattr(output, field_name).recursive_output_fingerprint()
            else:
                fingerprint_dict[field_name] = str(getattr(output, field_name))
        return str(fingerprint_dict)
    def should_exist(self) -> bool:
        if self._status == ElementStatus.DELETED:
            return False
        else:
            return self.created_by is None or self.created_by.output.contains(self)
        
    def should_recompute_output(self) -> bool:
        # TODO: implement this
        latest_input_fingerprint = self.recursive_input_fingerprint()
        if self._output is None or self._last_input_fingerprint != latest_input_fingerprint:
            should_recompute = True
        else:
            should_recompute = False
        self._last_input_fingerprint = latest_input_fingerprint
        print(F"------------------------self._last_input_fingerprint: {self._last_input_fingerprint}------------------------")
        print(F"------------------------latest_input_fingerprint: {latest_input_fingerprint}------------------------")
        return should_recompute
class BaseDataElement(BaseModel):
    def recursive_output_fingerprint(self) -> str:
        return str(self)
class Trade(BaseDataElement):
    symbol: str
    trade_id: str
    direction: str
    volume: float
    price: float

class SymbolOntology(BaseDataElement):
    symbol: str
    symbol_type: str
    symbol_category: str

class Position(BaseDataElement):
    symbol: str
    position: float

class SymbolTradeAnalysis(BaseDataElement):
    symbol: str
    number_trades: int
    average_price: float

class SymbolConfig(BaseGraphElement.GraphElementConfig):
    symbol: str
class DataAccessNode(BaseGraphElement):
    class Input(BaseGraphElement.Input):
        pass
    class Output(BaseGraphElement.Output):
        pass
    def _compute_output(self) -> Output:
        pass


TRADES_IN_DB_1 = {"last_modified": 1, "trades": [ 
            Trade(symbol="AAPL", trade_id="1", direction="Buy", volume=100, price=150.75),
            Trade(symbol="AAPL", trade_id="2", direction="Sell", volume=50, price=152.25),
            Trade(symbol="AAPL", trade_id="3", direction="Buy", volume=75, price=151.50),
            Trade(symbol="AAPL", trade_id="4", direction="Sell", volume=25, price=153.00),
            Trade(symbol="AAPL", trade_id="5", direction="Buy", volume=125, price=154.25),
            Trade(symbol="AAPL", trade_id="6", direction="Sell", volume=100, price=155.50),
            Trade(symbol="AAPL", trade_id="7", direction="Buy", volume=150, price=156.75),
            Trade(symbol="AAPL", trade_id="8", direction="Sell", volume=75, price=158.00),
            Trade(symbol="AAPL", trade_id="9", direction="Buy", volume=100, price=159.25),
            Trade(symbol="AAPL", trade_id="10", direction="Sell", volume=50, price=160.50),
            Trade(symbol="TSLA", trade_id="11", direction="Buy", volume=100, price=161.75),
            Trade(symbol="TSLA", trade_id="12", direction="Sell", volume=50, price=163.00),
            Trade(symbol="TSLA", trade_id="13", direction="Buy", volume=75, price=164.25),
            Trade(symbol="TSLA", trade_id="14", direction="Sell", volume=25, price=165.50),
            Trade(symbol="TSLA", trade_id="15", direction="Buy", volume=125, price=166.75),
            Trade(symbol="TSLA", trade_id="16", direction="Sell", volume=100, price=168.00),
            Trade(symbol="TSLA", trade_id="17", direction="Buy", volume=150, price=169.25),
            Trade(symbol="TSLA", trade_id="18", direction="Sell", volume=75, price=170.50),
            Trade(symbol="TSLA", trade_id="19", direction="Buy", volume=100, price=171.75),
        ]}
TRADES_IN_DB_2 = {"last_modified": 2, "trades": [
    Trade(symbol="AAPL", trade_id="1", direction="Buy", volume=100, price=150.75),
    Trade(symbol="AAPL", trade_id="2", direction="Sell", volume=50, price=152.25),
    Trade(symbol="AAPL", trade_id="3", direction="Buy", volume=75, price=151.50),
    Trade(symbol="AAPL", trade_id="4", direction="Sell", volume=25, price=153.00),
    Trade(symbol="AAPL", trade_id="5", direction="Buy", volume=125, price=154.25),
    Trade(symbol="AAPL", trade_id="6", direction="Sell", volume=100, price=155.50),
    Trade(symbol="AAPL", trade_id="7", direction="Buy", volume=150, price=156.75),
    Trade(symbol="AAPL", trade_id="8", direction="Sell", volume=75, price=158.00),
    Trade(symbol="AAPL", trade_id="9", direction="Buy", volume=100, price=159.25),
    Trade(symbol="AAPL", trade_id="10", direction="Sell", volume=50, price=160.50),
]}
class GetAllTradesNode(DataAccessNode):
    _last_modified: int = PrivateAttr(default=TRADES_IN_DB_1["last_modified"])
    class Output(BaseGraphElement.Output):
        all_trades: list[Trade]
    def _compute_output(self) -> Output:
        output = self.Output(all_trades=TRADES_IN_DB_1["trades"])
        self._last_modified = TRADES_IN_DB_1["last_modified"]
        return output

    def should_recompute_output(self) -> bool:
        if self._last_modified != TRADES_IN_DB_1["last_modified"]:
            return True
        else:
            return False
class GetAllYesterdayPositionsNode(DataAccessNode):
    class Output(BaseGraphElement.Output):
        all_yesterday_positions: list[Position]
    def _compute_output(self) -> Output:
        return self.Output(all_yesterday_positions=[
            Position(symbol="AAPL", position=100),
            Position(symbol="TSLA", position=50),
        ])
class GetAllSymbolOntologyNode(DataAccessNode):
    class Output(BaseGraphElement.Output):
        all_symbol_ontology: list[SymbolOntology]
    def _compute_output(self) -> Output:
        return self.Output(all_symbol_ontology=[
            SymbolOntology(symbol="AAPL", symbol_type="stock_1", symbol_category="CAT_TECH"),
            SymbolOntology(symbol="TSLA", symbol_type="stock_2", symbol_category="CAT_AUTOMOTIVE"),
            SymbolOntology(symbol="SOME_OTHER_SYMBOL", symbol_type="option_1", symbol_category="CAT_TECH"),
        ])


class GetSymbolOntologyNode(BaseGraphElement):
    config: SymbolConfig
    class Input(BaseGraphElement.Input):
        get_all_symbol_ontology_node: GetAllSymbolOntologyNode
    class Output(BaseGraphElement.Output):
        symbol_ontology: SymbolOntology
    def _compute_output(self) -> Output:
        for symbol_ontology in self.input.get_all_symbol_ontology_node.output.all_symbol_ontology:
            if symbol_ontology.symbol == self.config.symbol:
                return self.Output(symbol_ontology=symbol_ontology)
        return self.Output(symbol_ontology=None)
    
class GetSymbolYesterdayPositionNode(BaseGraphElement):
    config: SymbolConfig
    class Input(BaseGraphElement.Input):
        get_all_yesterday_positions_node: GetAllYesterdayPositionsNode
    class Output(BaseGraphElement.Output):
        symbol_yesterday_position: Position
    def _compute_output(self) -> Output:
        for position in self.input.get_all_yesterday_positions_node.output.all_yesterday_positions:
            if position.symbol == self.config.symbol:
                return self.Output(symbol_yesterday_position=position)
        return self.Output(symbol_yesterday_position=None)

class GetSymbolTodayTradesNode(BaseGraphElement):
    config: SymbolConfig
    class Input(BaseGraphElement.Input):
        get_all_trades_node: GetAllTradesNode
    class Output(BaseGraphElement.Output):
        symbol_today_trades: list[Trade]
    def _compute_output(self) -> Output:
        return self.Output(symbol_today_trades=[trade for trade in self.input.get_all_trades_node.output.all_trades if trade.symbol == self.config.symbol])
class AnalyzeSymbolTradesNode(BaseGraphElement):
    config: SymbolConfig
    class Input(BaseGraphElement.Input):
        get_symbol_today_trades_node: GetSymbolTodayTradesNode
    class Output(BaseGraphElement.Output):
        symbol_trade_analysis: SymbolTradeAnalysis
    def _compute_output(self) -> Output:
        symbol_trade_analysis = SymbolTradeAnalysis(symbol=self.config.symbol, number_trades=len(self.input.get_symbol_today_trades_node.output.symbol_today_trades), average_price=sum([trade.price for trade in self.input.get_symbol_today_trades_node.output.symbol_today_trades]) / len(self.input.get_symbol_today_trades_node.output.symbol_today_trades))
        return self.Output(symbol_trade_analysis=symbol_trade_analysis)
class SymbolTradeAnalysisNode(BaseGraphElement):
    config: SymbolConfig
    class Input(BaseGraphElement.Input):
        get_all_today_trades_node: GetAllTradesNode
    class Output(BaseGraphElement.Output):
        get_symbol_today_trades_node: GetSymbolTodayTradesNode
        analyze_symbol_trades_node: AnalyzeSymbolTradesNode
    def _compute_output(self) -> Output:
        get_symbol_today_trades_node = GetSymbolTodayTradesNode(created_by=self, config=self.config, input=GetSymbolTodayTradesNode.Input(get_all_trades_node=self.input.get_all_today_trades_node))
        analyze_symbol_trades_node = AnalyzeSymbolTradesNode(created_by=self, config=self.config, input=AnalyzeSymbolTradesNode.Input(get_symbol_today_trades_node=get_symbol_today_trades_node))
        return self.Output(
            get_symbol_today_trades_node=get_symbol_today_trades_node,
            analyze_symbol_trades_node=analyze_symbol_trades_node,)
class SymbolsWithActiveTradesNode(BaseGraphElement):
    class Input(BaseGraphElement.Input):
        get_all_trades_node: GetAllTradesNode
    class Output(BaseGraphElement.Output):
        symbol_trade_analysis_nodes: list[SymbolTradeAnalysisNode]
    def _compute_output(self) -> Output:
        
        all_unique_symbols = set([trade.symbol for trade in self.input.get_all_trades_node.output.all_trades])
        symbol_trade_analysis_nodes = [
            SymbolTradeAnalysisNode(
                created_by=self,
                config=SymbolConfig(symbol=symbol), 
                input=SymbolTradeAnalysisNode.Input(
                    get_all_today_trades_node=self.input.get_all_trades_node,
            )) for symbol in all_unique_symbols]
        return self.Output(symbol_trade_analysis_nodes=symbol_trade_analysis_nodes)

class UpdatePositionsNode(BaseGraphElement):
    class Input(BaseGraphElement.Input):
        get_all_yesterday_positions_node: GetAllYesterdayPositionsNode
        new_trade_symbols_node: SymbolsWithActiveTradesNode
    class Output(BaseGraphElement.Output):
        updated_positions: list[Position]
    def _compute_output(self) -> Output:
        updated_positions = []
        for position in self.input.get_all_yesterday_positions_node.output.all_yesterday_positions:
            for symbol_trade_analysis_node in self.input.new_trade_symbols_node.output.symbol_trade_analysis_nodes:
                analysis = symbol_trade_analysis_node.output.analyze_symbol_trades_node.output.symbol_trade_analysis
                if analysis.symbol == position.symbol:
                    updated_positions.append(Position(symbol=position.symbol, position=position.position + analysis.number_trades))
        return self.Output(updated_positions=updated_positions)

class FirmEconomics(BaseModel):
    sum_of_positions: float
class FirmEconomicsNode(BaseGraphElement):
    class Input(BaseGraphElement.Input):
        update_positions_node: UpdatePositionsNode
        all_symbol_ontology_node: GetAllSymbolOntologyNode
    class Output(BaseGraphElement.Output):
        firm_economics: FirmEconomics
    def _compute_output(self) -> Output:
        sum_of_positions = sum([position.position for position in self.input.update_positions_node.output.updated_positions])
        return self.Output(firm_economics=FirmEconomics(sum_of_positions=sum_of_positions))
class TradeAnalysisNode(BaseGraphElement):
    class Output(BaseGraphElement.Output):
        all_today_trades_node: GetAllTradesNode
        all_yesterday_positions_node: GetAllYesterdayPositionsNode
        all_symbol_ontology_node: GetAllSymbolOntologyNode
        new_trade_symbols_node: SymbolsWithActiveTradesNode
        update_positions_node: UpdatePositionsNode
        firm_economics_node: FirmEconomicsNode

    def _compute_output(self) -> Output:
        all_today_trades_node = GetAllTradesNode(created_by=self)
        all_yesterday_positions_node = GetAllYesterdayPositionsNode(created_by=self)
        new_trade_symbols_node = SymbolsWithActiveTradesNode(created_by=self, input=SymbolsWithActiveTradesNode.Input(get_all_trades_node=all_today_trades_node))
        all_symbol_ontology_node = GetAllSymbolOntologyNode(created_by=self)
        update_positions_node = UpdatePositionsNode(created_by=self, input=UpdatePositionsNode.Input(get_all_yesterday_positions_node=all_yesterday_positions_node, new_trade_symbols_node=new_trade_symbols_node))
        firm_economics_node = FirmEconomicsNode(
            created_by=self,
            input=FirmEconomicsNode.Input(
                update_positions_node=update_positions_node,
                all_symbol_ontology_node=all_symbol_ontology_node,
            ))
        return self.Output(
            all_yesterday_positions_node=all_yesterday_positions_node,
            all_symbol_ontology_node=all_symbol_ontology_node,
            all_today_trades_node=all_today_trades_node,
            new_trade_symbols_node=new_trade_symbols_node,
            update_positions_node=update_positions_node,
            firm_economics_node=firm_economics_node)

#class FirmEconomicsNode(BaseGraphElement):
#    class Input(BaseGraphElement.Input):
#        trade_analysis_node: TradeAnalysisNode
#        firm_info_node: FirmInfoNode
#    class Output(BaseGraphElement.Output):
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



def build_graph(node: BaseGraphElement):


    def walk(node: BaseGraphElement):
       nodes[node.element_name()] = node.element_name()
       output = node._output
       input = node.input
       if input:
           for field_name, field_info in input.__class__.model_fields.items():
             value = getattr(input, field_name)
             if isinstance(value, BaseGraphElement):
               edges.append((value.element_name(), node.element_name()))
             elif isinstance(value, list ):
               for item in value:
                 edges.append((item.element_name(), node.element_name()))
       if output:
           contains[node.element_name()] = []
           for field_name, field_info in output.__class__.model_fields.items():
             value = getattr(output, field_name)
             if isinstance(value, BaseGraphElement):
               contains[node.element_name()].append(value.element_name())
               walk(value)   
             elif isinstance(value, list ):
               for item in value:
                 if isinstance(item, BaseGraphElement):
                     contains[node.element_name()].append(item.element_name())
                     walk(item)

    nodes = {}
    contains = {}
    edges = []
    walk(node)
    build(nodes=nodes, contains=contains, edges=edges, filename=f"trade_analysis_graph{ time.time() }")

if __name__ == "__main__":
    trade_analysis_node = TradeAnalysisNode()
    firm_economics_node = trade_analysis_node.output.firm_economics_node.output.firm_economics
    time.sleep(1)
    print(f"HEYYYYY")
    TRADES_IN_DB_1 = TRADES_IN_DB_2
    firm_economics_output_2 = trade_analysis_node.output.firm_economics_node.output.firm_economics




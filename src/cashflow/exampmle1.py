"""
trading data pipeline with dashed dependencies
"""
from base import BaseDataElement, BaseNode, Input, Output, GraphElementConfig
from pydantic import PrivateAttr
from pydantic import BaseModel
import time
#------------------------------------------Example------------------------------------------
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

class SymbolConfig(GraphElementConfig):
    symbol: str
class DataAccessNode(BaseNode):
    class Input(Input):
        pass
    class Output(Output):
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

ALL_SYMBOL_ONTOLOGY_1 = {"symbol_ontology": [
            SymbolOntology(symbol="AAPL", symbol_type="stock_1", symbol_category="CAT_TECH"),
            SymbolOntology(symbol="TSLA", symbol_type="stock_2", symbol_category="CAT_AUTOMOTIVE"),
            SymbolOntology(symbol="SOME_OTHER_SYMBOL", symbol_type="option_1", symbol_category="CAT_TECH"),
        ], "last_modified": 1}

ALL_SYMBOL_ONTOLOGY_2 = {"symbol_ontology": [
            SymbolOntology(symbol="AAPL", symbol_type="stock_1", symbol_category="CAT_TECH"),
            SymbolOntology(symbol="TSLA", symbol_type="stock_3", symbol_category="XCAT_AUTOMOTIVE"),
            SymbolOntology(symbol="SOME_OTHER_SYMBOL", symbol_type="option_2", symbol_category="CAT_TECH"),
        ], "last_modified": 2}

ALL_SYMBOL_ONTOLOGY_3 = {"symbol_ontology": [
            SymbolOntology(symbol="AAPL", symbol_type="stock_1", symbol_category="CAT_TECH"),
            SymbolOntology(symbol="TSLA", symbol_type="stock_4", symbol_category="XCAT_AUTOMOTIVE"),
            SymbolOntology(symbol="SOME_OTHER_SYMBOL", symbol_type="option_2", symbol_category="CAT_TECH"),
        ], "last_modified": 3}

        
class GetAllTradesNode(DataAccessNode):
    _last_modified: int = PrivateAttr(default=TRADES_IN_DB_1["last_modified"])
    class Output(Output):
        all_trades: list[Trade]

    def _compute_output(self) -> Output:
        output = self.Output(all_trades=TRADES_IN_DB_1["trades"])
        self._last_modified = TRADES_IN_DB_1["last_modified"]
        return output

    def _inner_should_recompute_output(self) -> bool:
        return self._last_modified != TRADES_IN_DB_1["last_modified"]

class GetAllYesterdayPositionsNode(DataAccessNode):
    class Output(Output):
        all_yesterday_positions: list[Position]
    def _compute_output(self) -> Output:
        return self.Output(all_yesterday_positions=[
            Position(symbol="AAPL", position=100),
            Position(symbol="TSLA", position=50),
        ])
class GetAllSymbolOntologyNode(DataAccessNode):
    _last_modified: int = PrivateAttr(default=ALL_SYMBOL_ONTOLOGY_1["last_modified"])
    class Output(Output):
        all_symbol_ontology: list[SymbolOntology]
    def _compute_output(self) -> Output:
        return self.Output(all_symbol_ontology=ALL_SYMBOL_ONTOLOGY_1["symbol_ontology"])
    def _inner_should_recompute_output(self) -> bool:
        if self._last_modified != ALL_SYMBOL_ONTOLOGY_1["last_modified"]:
            return True
        else:
            return False

class GetSymbolOntologyNode(BaseNode):
    config: SymbolConfig
    class Input(Input):
        get_all_symbol_ontology_node: GetAllSymbolOntologyNode
    class Output(Output):
        symbol_ontology: SymbolOntology
    def _compute_output(self) -> Output:
        for symbol_ontology in self.input.get_all_symbol_ontology_node.output.all_symbol_ontology:
            if symbol_ontology.symbol == self.config.symbol:
                return self.Output(symbol_ontology=symbol_ontology)
        return self.Output(symbol_ontology=None)
    
class GetSymbolYesterdayPositionNode(BaseNode):
    config: SymbolConfig
    class Input(Input):
        get_all_yesterday_positions_node: GetAllYesterdayPositionsNode
    class Output(Output):
        symbol_yesterday_position: Position
    def _compute_output(self) -> Output:
        for position in self.input.get_all_yesterday_positions_node.output.all_yesterday_positions:
            if position.symbol == self.config.symbol:
                return self.Output(symbol_yesterday_position=position)
        return self.Output(symbol_yesterday_position=None)

class GetSymbolTodayTradesNode(BaseNode):
    config: SymbolConfig
    class Input(Input):
        get_all_trades_node: GetAllTradesNode
    class Output(Output):
        symbol_today_trades: list[Trade]
    def _compute_output(self) -> Output:
        return self.Output(symbol_today_trades=[trade for trade in self.input.get_all_trades_node.output.all_trades if trade.symbol == self.config.symbol])
class AnalyzeSymbolTradesNode(BaseNode):
    config: SymbolConfig
    class Input(Input):
        get_symbol_today_trades_node: GetSymbolTodayTradesNode
    class Output(Output):
        symbol_trade_analysis: SymbolTradeAnalysis
    def _compute_output(self) -> Output:
        symbol_trade_analysis = SymbolTradeAnalysis(symbol=self.config.symbol, number_trades=len(self.input.get_symbol_today_trades_node.output.symbol_today_trades), average_price=sum([trade.price for trade in self.input.get_symbol_today_trades_node.output.symbol_today_trades]) / len(self.input.get_symbol_today_trades_node.output.symbol_today_trades))
        return self.Output(symbol_trade_analysis=symbol_trade_analysis)
class SymbolTradeAnalysisNode(BaseNode):
    config: SymbolConfig
    class Input(Input):
        get_all_today_trades_node: GetAllTradesNode
    class Output(Output):
        get_symbol_today_trades_node: GetSymbolTodayTradesNode
        analyze_symbol_trades_node: AnalyzeSymbolTradesNode
    def _compute_output(self) -> Output:
        get_symbol_today_trades_node = GetSymbolTodayTradesNode(created_by=self, config=self.config, input=GetSymbolTodayTradesNode.Input(get_all_trades_node=self.input.get_all_today_trades_node))
        analyze_symbol_trades_node = AnalyzeSymbolTradesNode(created_by=self, config=self.config, input=AnalyzeSymbolTradesNode.Input(get_symbol_today_trades_node=get_symbol_today_trades_node))
        return self.Output(
            get_symbol_today_trades_node=get_symbol_today_trades_node,
            analyze_symbol_trades_node=analyze_symbol_trades_node,)
class SymbolsWithActiveTradesNode(BaseNode):
    class Input(Input):
        get_all_trades_node: GetAllTradesNode
    class Output(Output):
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

class UpdatePositionsNode(BaseNode):
    class Input(Input):
        get_all_yesterday_positions_node: GetAllYesterdayPositionsNode
        new_trade_symbols_node: SymbolsWithActiveTradesNode
    class Output(Output):
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
class FirmEconomicsNode(BaseNode):
    class Input(Input):
        update_positions_node: UpdatePositionsNode
        all_symbol_ontology_node: GetAllSymbolOntologyNode
    class Output(Output):
        firm_economics: FirmEconomics
    def _compute_output(self) -> Output:
        sum_of_positions = sum([position.position for position in self.input.update_positions_node.output.updated_positions])
        return self.Output(firm_economics=FirmEconomics(sum_of_positions=sum_of_positions))
class TradeAnalysisNode(BaseNode):
    class Output(Output):
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


if __name__ == "__main__":
    trade_analysis_node = TradeAnalysisNode()
    firm_economics_node = trade_analysis_node.output.firm_economics_node.output.firm_economics
    time.sleep(1)

    print("HEYYYYY")
    # change TSLA
    ALL_SYMBOL_ONTOLOGY_1 = ALL_SYMBOL_ONTOLOGY_2
    firm_economics_output_2 = trade_analysis_node.output.firm_economics_node.output.firm_economics
    time.sleep(1)
    # RM TSLA
    TRADES_IN_DB_1 = TRADES_IN_DB_2
    firm_economics_output_2 = trade_analysis_node.output.firm_economics_node.output.firm_economics
    time.sleep(1)
    # CHANGE TSLA again
    ALL_SYMBOL_ONTOLOGY_1 = ALL_SYMBOL_ONTOLOGY_3
    firm_economics_output_3 = trade_analysis_node.output.firm_economics_node.output.firm_economics  



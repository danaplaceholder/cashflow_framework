"""
trading data pipeline with dashed dependencies
by Dana K
NOT by ai
"""
from base import BaseDataElement, BaseNode, Input, Output, StaticOutputNode
from pydantic import BaseModel
import time
from abc import abstractmethod
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

class Symbol(BaseDataElement):
    name: str
class SymbolConfigNode(StaticOutputNode):
    class Output(Output):
        symbol: BaseDataElement

class DataAccessNode(BaseNode):
    class Input(Input):
        pass
    class Output(Output):
        pass
    def _compute_output(self) -> Output:
        pass

    @abstractmethod
    def get_external_data_last_modified(self) -> int:
        raise NotImplementedError("Subclasses must implement this method")

class ComputationOnlyNode(BaseNode):
    class Input(Input):
        pass
    class Output(Output):
        pass
    def _compute_output(self) -> Output:
        pass
    def get_external_data_last_modified(self) -> int | None:
        return None

TRADES_IN_DB_1 = {"data": [ 
            Trade(symbol="AAPL", trade_id="1", direction="Buy", volume=100, price=150.75),
            Trade(symbol="TSLA", trade_id="11", direction="Buy", volume=100, price=161.75),
        ], "last_modified": 1}
TRADES_IN_DB_2 = {"data": [
    Trade(symbol="AAPL", trade_id="1", direction="Buy", volume=100, price=150.75),
], "last_modified": 2}

ALL_SYMBOL_ONTOLOGY_1 = {"data": [
            SymbolOntology(symbol="AAPL", symbol_type="stock_1", symbol_category="CAT_TECH"),
            SymbolOntology(symbol="TSLA", symbol_type="stock_2", symbol_category="CAT_AUTOMOTIVE"),
            SymbolOntology(symbol="SOME_OTHER_SYMBOL", symbol_type="option_1", symbol_category="CAT_TECH"),
        ], "last_modified": 1}

ALL_SYMBOL_ONTOLOGY_2 = {"data": [
            SymbolOntology(symbol="AAPL", symbol_type="stock_1", symbol_category="CAT_TECH"),
            SymbolOntology(symbol="TSLA", symbol_type="stock_3", symbol_category="XCAT_AUTOMOTIVE"),
            SymbolOntology(symbol="SOME_OTHER_SYMBOL", symbol_type="option_2", symbol_category="CAT_TECH"),
        ], "last_modified": 2}

ALL_SYMBOL_ONTOLOGY_3 = {"data": [
            SymbolOntology(symbol="AAPL", symbol_type="stock_1", symbol_category="CAT_TECH"),
            SymbolOntology(symbol="TSLA", symbol_type="stock_4", symbol_category="XCAT_AUTOMOTIVE"),
            SymbolOntology(symbol="SOME_OTHER_SYMBOL", symbol_type="option_2", symbol_category="CAT_TECH"),
        ], "last_modified": 3}
POSITIONS_IN_DB_1 = {"data": [
            Position(symbol="AAPL", position=100),
            Position(symbol="TSLA", position=50),
        ], "last_modified": 1}
        
MOCK_DB = {
    "trades": TRADES_IN_DB_1,
    "symbol_ontology": ALL_SYMBOL_ONTOLOGY_1,
    "positions": POSITIONS_IN_DB_1,
}
class GetAllTradesNode(DataAccessNode):
    class Output(Output):
        all_trades: list[Trade]

    def _compute_output(self) -> Output:
        output = self.Output(all_trades=MOCK_DB["trades"]["data"])
        return output

    def get_external_data_last_modified(self) -> int:
        return MOCK_DB["trades"]["last_modified"]


class GetAllYesterdayPositionsNode(DataAccessNode):
    class Output(Output):
        all_yesterday_positions: list[Position]
    
    def get_external_data_last_modified(self) -> int:
        return None # should be made real

    def _compute_output(self) -> Output:
        return self.Output(all_yesterday_positions=MOCK_DB["positions"]["data"])
class GetAllSymbolOntologyNode(DataAccessNode):
    class Output(Output):
        all_symbol_ontology: list[SymbolOntology]
    def _compute_output(self) -> Output:
        return self.Output(all_symbol_ontology=MOCK_DB["symbol_ontology"]["data"])
    def get_external_data_last_modified(self) -> int:
        return MOCK_DB["symbol_ontology"]["last_modified"]


class GetSymbolTodayTradesNode(ComputationOnlyNode):
    class Input(Input):
        symbol_config_node: SymbolConfigNode
        get_all_trades_node: GetAllTradesNode
    class Output(Output):
        symbol_today_trades: list[Trade]
    def _compute_output(self) -> Output:
        symbol = self.input.symbol_config_node.output.symbol.name
        return self.Output(symbol_today_trades=[trade for trade in self.input.get_all_trades_node.output.all_trades if trade.symbol == symbol])
class AnalyzeSymbolTradesNode(ComputationOnlyNode):
    class Input(Input):
        symbol_config_node: SymbolConfigNode
        get_symbol_today_trades_node: GetSymbolTodayTradesNode
    class Output(Output):
        symbol_trade_analysis: SymbolTradeAnalysis
    def _compute_output(self) -> Output:
        symbol = self.input.symbol_config_node.output.symbol.name
        symbol_trade_analysis = SymbolTradeAnalysis(symbol=symbol, number_trades=len(self.input.get_symbol_today_trades_node.output.symbol_today_trades), average_price=sum([trade.price for trade in self.input.get_symbol_today_trades_node.output.symbol_today_trades]) / len(self.input.get_symbol_today_trades_node.output.symbol_today_trades))
        return self.Output(symbol_trade_analysis=symbol_trade_analysis)
class SymbolTradeAnalysisNode(ComputationOnlyNode):
    class Input(Input):
        symbol_config_node: SymbolConfigNode
        get_all_today_trades_node: GetAllTradesNode
    class Output(Output):
        get_symbol_today_trades_node: GetSymbolTodayTradesNode
        analyze_symbol_trades_node: AnalyzeSymbolTradesNode
    def _compute_output(self) -> Output:
        get_symbol_today_trades_node = GetSymbolTodayTradesNode(alias=self.input.symbol_config_node.output.symbol.name, input=GetSymbolTodayTradesNode.Input(symbol_config_node=self.input.symbol_config_node, get_all_trades_node=self.input.get_all_today_trades_node))
        analyze_symbol_trades_node = AnalyzeSymbolTradesNode(alias=self.input.symbol_config_node.output.symbol.name, input=AnalyzeSymbolTradesNode.Input(symbol_config_node=self.input.symbol_config_node, get_symbol_today_trades_node=get_symbol_today_trades_node))
        return self.Output(
            get_symbol_today_trades_node=get_symbol_today_trades_node,
            analyze_symbol_trades_node=analyze_symbol_trades_node)
class SymbolsWithActiveTradesNode(ComputationOnlyNode):
    class Input(Input):
        get_all_trades_node: GetAllTradesNode
    class Output(Output):
        symbol_config_nodes: list[SymbolConfigNode]
        symbol_trade_analysis_nodes: list[SymbolTradeAnalysisNode]

    def _compute_output(self) -> Output:
        all_unique_symbols = set([trade.symbol for trade in self.input.get_all_trades_node.output.all_trades])
        symbol_config_nodes = []
        symbol_trade_analysis_nodes = []
        for symbol in all_unique_symbols:
            symbol_config_node = SymbolConfigNode(alias=symbol, output=SymbolConfigNode.Output(symbol=Symbol(name=symbol)))
            symbol_trade_analysis_node = SymbolTradeAnalysisNode(
                alias=symbol,
                input=SymbolTradeAnalysisNode.Input(
                    symbol_config_node=symbol_config_node,
                    get_all_today_trades_node=self.input.get_all_trades_node,
                ))
            symbol_config_nodes.append(symbol_config_node)
            symbol_trade_analysis_nodes.append(symbol_trade_analysis_node)
        return self.Output(symbol_config_nodes=symbol_config_nodes, symbol_trade_analysis_nodes=symbol_trade_analysis_nodes)

class UpdatePositionsNode(ComputationOnlyNode):
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
class FirmEconomicsNode(ComputationOnlyNode):
    class Input(Input):
        update_positions_node: UpdatePositionsNode
        all_symbol_ontology_node: GetAllSymbolOntologyNode
    class Output(Output):
        firm_economics: FirmEconomics
    def _compute_output(self) -> Output:
        sum_of_positions = sum([position.position for position in self.input.update_positions_node.output.updated_positions])
        return self.Output(firm_economics=FirmEconomics(sum_of_positions=sum_of_positions))

class TradeAnalysisNode(ComputationOnlyNode):
    class Output(Output):
        all_today_trades_node: GetAllTradesNode
        all_yesterday_positions_node: GetAllYesterdayPositionsNode
        all_symbol_ontology_node: GetAllSymbolOntologyNode
        new_trade_symbols_node: SymbolsWithActiveTradesNode
        update_positions_node: UpdatePositionsNode
        firm_economics_node: FirmEconomicsNode

    def _compute_output(self) -> Output:
        all_today_trades_node = GetAllTradesNode()
        all_yesterday_positions_node = GetAllYesterdayPositionsNode()
        new_trade_symbols_node = SymbolsWithActiveTradesNode( input=SymbolsWithActiveTradesNode.Input(get_all_trades_node=all_today_trades_node))
        all_symbol_ontology_node = GetAllSymbolOntologyNode()
        update_positions_node = UpdatePositionsNode( input=UpdatePositionsNode.Input(get_all_yesterday_positions_node=all_yesterday_positions_node, new_trade_symbols_node=new_trade_symbols_node))
        firm_economics_node = FirmEconomicsNode(
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
#
    print("HEYYYYY")
    # change TSLA
    MOCK_DB["symbol_ontology"] = ALL_SYMBOL_ONTOLOGY_2
    firm_economics_output_2 = trade_analysis_node.output.firm_economics_node.output.firm_economics
    time.sleep(1)
    # RM TSLA
    MOCK_DB["trades"] = TRADES_IN_DB_2
    firm_economics_output_2 = trade_analysis_node.output.firm_economics_node.output.firm_economics
    time.sleep(1)
    # CHANGE TSLA again
    MOCK_DB["symbol_ontology"] = ALL_SYMBOL_ONTOLOGY_3
    firm_economics_output_3 = trade_analysis_node.output.firm_economics_node.output.firm_economics  


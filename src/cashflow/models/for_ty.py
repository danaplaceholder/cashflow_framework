
from datetime import datetime, timedelta

from cashflow.models.base import ComputeUnitInput, AbstractComputeUnit, ComputeUnitOutput, ModelConfig, Scalar, TimeSeries, TradeList
from cashflow.models.layers import Layers
import os
from pydantic import BaseModel


"""
table of trades 
build ...... map from trade_id_to_trade 
symbol, category, 

auto generate nested map from sym to 
 .... everything grouped by symbol 

 ..... everything grouped by category ..... 



"""
class TradeTablePayload:
    title: str
    rows: list[list[str]]
    



class DbConnectionClient(Scalar):
    def get_all_trades(self) -> list[TradeList.Trade]:
        return RAW_DB_TRADES

RAW_DB_TRADES = [
    TradeList.Trade(symbol="AAPL", category="Technology", trade_id="1234567890", direction="buy"),
    TradeList.Trade(symbol="AAPL", category="Technology", trade_id="1234567891", direction="sell"),
    TradeList.Trade(symbol="AAPL", category="Technology", trade_id="1234567892", direction="buy"),
    TradeList.Trade(symbol="AAPL", category="Technology", trade_id="1234567893", direction="sell"),
    TradeList.Trade(symbol="AAPL", category="Technology", trade_id="1234567894", direction="buy"),
    TradeList.Trade(symbol="AAPL", category="Technology", trade_id="1234567895", direction="sell"),
    TradeList.Trade(symbol="TSLA", category="Technology", trade_id="1234567896", direction="buy"),
    TradeList.Trade(symbol="TSLA", category="Technology", trade_id="1234567897", direction="sell"),
    TradeList.Trade(symbol="TSLA", category="Technology", trade_id="1234567898", direction="buy"),
    TradeList.Trade(symbol="TSLA", category="Technology", trade_id="1234567899", direction="sell"),
    TradeList.Trade(symbol="TSLA", category="Technology", trade_id="1234567890", direction="buy"),
]

class UiConnectionClient(Scalar):
    def send_to_client(self, trades: TradeList) -> TradeList:
        print(f"Sending {len(trades.trades)} trades to client")
        for trade in trades.trades:
            print(f"Trade: {trade.symbol} {trade.category} {trade.trade_id} {trade.direction}")
        return trades

class TradeQueryConfig(BaseModel):
    symbol: str|None = None
    category: str|None = None
    direction: str|None = None
    

class TradeSummaryConfig(ModelConfig):
    db_access_config: str
    external_ui_access_config: str


# DB STUFF
class ConnectToDbNode(Layers.Node):
    class Output(ComputeUnitOutput):
        db_connection_client: DbConnectionClient
    def _compute_output(self) -> Output:
        return self.Output(db_connection_client=DbConnectionClient(value="some_db_connection_client"))

        return RAW_DB_TRADES

class QueryDbNode(Layers.Node):

    class Input(ComputeUnitInput):
        connect_to_db_node: ConnectToDbNode
    class Output(ComputeUnitOutput):
        trades: TradeList

    def _compute_output(self) -> Output:
        all_trades = self.input.connect_to_db_node.output.db_connection_client.get_all_trades()
        filtered_trades = all_trades
        if self.symbol:
            filtered_trades = [trade for trade in filtered_trades if trade.symbol == self.symbol]
        if self.category:
            filtered_trades = [trade for trade in filtered_trades if trade.category == self.category]
        if self.direction:
            filtered_trades = [trade for trade in filtered_trades if trade.direction == self.direction]
        return self.Output(trades=TradeList(trades=filtered_trades))

    @property
    def symbol(self) -> str:
        return None

    @property
    def category(self) -> str:
        return None

    @property
    def direction(self) -> str:
        return None

class APPLQueryNode(QueryDbNode):
    @property
    def symbol(self) -> str:
        return "AAPL"

class TechnologyQueryNode(QueryDbNode):
    @property
    def category(self) -> str:
        return "Technology"

class DbSubmodule(Layers.Submodule):
    class Output(ComputeUnitOutput):
        connect_to_db_node: ConnectToDbNode
        query_technology_node: QueryDbNode
        query_symbol_node: QueryDbNode

    def _compute_output(self) -> Output:
        connect_to_db_node = ConnectToDbNode(my_config=self.my_config)
        query_technology_node = TechnologyQueryNode(my_config=self.my_config, input=QueryDbNode.Input(connect_to_db_node=connect_to_db_node))
        query_symbol_node = APPLQueryNode(my_config=self.my_config, input=QueryDbNode.Input(connect_to_db_node=connect_to_db_node))
        return self.Output(connect_to_db_node=connect_to_db_node, query_technology_node=query_technology_node, query_symbol_node=query_symbol_node)


# Analysis STUFF

class AnalysisNode(Layers.Node):
    class Input(ComputeUnitInput):
        db_query_node: QueryDbNode
    class Output(ComputeUnitOutput):
        analysis_result: TradeList
    def _compute_output(self) -> Output:
        return self.Output(analysis_result=self.input.db_query_node.output.trades)

class AnalysisSubmodule(Layers.Submodule):
    class Input(ComputeUnitInput):
        db_submodule: DbSubmodule
    class Output(ComputeUnitOutput):
        technology_analysis_node: AnalysisNode
        symbol_analysis_node: AnalysisNode
    def _compute_output(self) -> Output:
        return self.Output(
            technology_analysis_node=AnalysisNode(my_config=self.my_config, input=AnalysisNode.Input(db_query_node=self.input.db_submodule.output.query_technology_node)), 
            symbol_analysis_node=AnalysisNode(my_config=self.my_config, input=AnalysisNode.Input(db_query_node=self.input.db_submodule.output.query_symbol_node)))

# UI STUFF
class UiConnectionNode(Layers.Node):
    class Output(ComputeUnitOutput):
        ui_connection_client: UiConnectionClient
    def _compute_output(self) -> Output:
        return self.Output(ui_connection_client=UiConnectionClient(value="some_ui_connection_client"))

class UiDisplayNode(Layers.Node):
    class Input(ComputeUnitInput):
        ui_connection_node: UiConnectionNode
        analysis_node: AnalysisNode
    class Output(ComputeUnitOutput):
        ui_display_result: TradeList 
    def _compute_output(self) -> Output:
        return self.Output(ui_display_result=self.input.ui_connection_node.output.ui_connection_client.send_to_client(self.input.analysis_node.output.analysis_result))



class UiSubmodule(Layers.Submodule):
    class Input(ComputeUnitInput):
        analysis_submodule: AnalysisSubmodule
    class Output(ComputeUnitOutput):
        ui_connection_node: UiConnectionNode
        ui_display_technology_node: UiDisplayNode
        ui_display_symbol_node: UiDisplayNode
    def _compute_output(self) -> Output:
        ui_connection_node = UiConnectionNode(my_config=self.my_config)
        ui_display_technology_node = UiDisplayNode(my_config=self.my_config, input=UiDisplayNode.Input(ui_connection_node=ui_connection_node, analysis_node=self.input.analysis_submodule.output.technology_analysis_node))
        ui_display_symbol_node = UiDisplayNode(my_config=self.my_config, input=UiDisplayNode.Input(ui_connection_node=ui_connection_node, analysis_node=self.input.analysis_submodule.output.symbol_analysis_node))
        return self.Output(ui_connection_node=ui_connection_node, ui_display_technology_node=ui_display_technology_node, ui_display_symbol_node=ui_display_symbol_node)


# CashFlowModelNetwork STUFF
class TradeSummarizationModel(Layers.CashFlow):
    class Output(ComputeUnitOutput):
        db_submodule: DbSubmodule
        analysis_submodule: AnalysisSubmodule
        ui_submodule: UiSubmodule
    def _compute_output(self) -> Output:
            db_submodule=DbSubmodule(my_config=self.my_config) 
            analysis_submodule=AnalysisSubmodule(
                my_config=self.my_config, 
                input=AnalysisSubmodule.Input(db_submodule=db_submodule)) 
            ui_submodule=UiSubmodule(
                my_config=self.my_config, 
                input=UiSubmodule.Input(analysis_submodule=analysis_submodule))
            return self.Output(db_submodule=db_submodule, analysis_submodule=analysis_submodule, ui_submodule=ui_submodule)

# run 
if __name__ == "__main__":
    model = TradeSummarizationModel(my_config=TradeSummaryConfig(name="trade_summarization", db_access_config="some_db_access_config", external_ui_access_config="some_external_ui_access_config"))
    model.run()
    print(model.output.db_submodule.output.query_symbol_node.output.trades.trades)
    print(model.output.db_submodule.output.query_technology_node.output.trades.trades)
    print(model.output.analysis_submodule.output.technology_analysis_node.output.analysis_result)
    print(model.output.ui_submodule.output.ui_display_technology_node.output.ui_display_result)
    print(model.output.ui_submodule.output.ui_display_symbol_node.output.ui_display_result)
    name = f"trade_summarization_{model.my_config.name}"
    full_path = os.path.join(os.path.dirname(__file__), f"{name}.svg")  
    model.render(full_path)
    print(f"wrote {full_path}")
"""
extract results from an iteration of the cashflow model for use in subsequent run 
"""
from cashflow.submodules.base import BaseSubModule
from cashflow.nodes.record import BaseRecordsNode
from cashflow.nodes.indexed_series import BaseIndexedSeriesNode
from cashflow.nodes.base import ComputationNodeMixin
from cashflow.nodes.data_access import DbDataAccessNodeMixin, ExternalApiDataAccessNodeMixin
from pydantic import BaseModel
from pydantic import PrivateAttr
from cashflow.nodes.indexed_series import TimeSeries
from cashflow.nodes.record import Record
from pydantic import computed_field
from functools import cached_property   


if TYPE_CHECKING:
    from models.example import ExampleCashflowModel
    
class PreviousIterationAnalysisSubModule(BaseSubModule):
    class Input(BaseSubModule.Input):
        previous_iteration_of_cash_flow_model: 'ExampleCashflowModel'

    class Nodes(BaseModel):
        pass

    @computed_field
    @cached_property
    def _nodes(self) -> Nodes:
        return self.Nodes() 
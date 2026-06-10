
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

class TaxationSubModule(BaseSubModule):
    class Input(BaseSubModule.Input):
        db_param_a: int
        db_param_b: str

    class Nodes(BaseModel):
        pass

    @computed_field
    @cached_property
    def _nodes(self) -> Nodes:
        return self.Nodes() 
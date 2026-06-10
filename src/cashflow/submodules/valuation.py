from submodules.base import BaseSubModule
from pydantic import BaseModel
from pydantic import computed_field
from functools import cached_property

class ValuationSubModule(BaseSubModule):
    class Input(BaseSubModule.Input):
        db_param_a: int
        db_param_b: str

    class Nodes(BaseModel):
        pass

    @computed_field
    @cached_property
    def _nodes(self) -> Nodes:
        return self.Nodes()
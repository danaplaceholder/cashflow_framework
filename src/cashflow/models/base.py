"""
Final Cashflow Models are made up of SubModules
"""
from pydantic import BaseModel
from pydantic import computed_field
from functools import cached_property
from abc import abstractmethod

class BaseCashflowModel(BaseModel):
    """
    BaseCashflowModel is the main class for the cashflow model
    """
    graph_cache_key: str
    class SubModules(BaseModel):
        pass

    @computed_field
    @cached_property
    @abstractmethod
    def _submodules(self) -> SubModules:
        raise NotImplementedError("must be implemented by subclass")
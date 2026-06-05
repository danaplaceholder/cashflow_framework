"""
Example Cashflow Model 
"""

from cashflow.models.base import BaseCashflowModel
from cashflow.submodules.proforma import ModuleProforma
from pydantic import BaseModel
from pydantic import computed_field
from functools import cached_property
from cashflow.cache.cache import CacheLayer, FileStorageBackend

class ExampleCashflowModel(BaseCashflowModel):
    class SubModules(BaseModel):
        valuation: ModuleValuation
        proforma: ModuleProforma
        depreciation: ModuleDepreciation

    @computed_field
    @cached_property
    def _cache_layer(self) -> CacheLayer:
        return CacheLayer(graph_cache_key=self.graph_cache_key, storage_backend_class=FileStorageBackend)


    @computed_field
    @cached_property
    def _submodules(self) -> SubModules:
        valuation = SubModuleValuation(cache_layer=self._cache_layer, input=SubModuleValuation.Input(db_param_a=1, db_param_b="test"))
        proforma = SubModuleProforma(cache_layer=self._cache_layer, input=SubModuleProforma.Input(db_param_a=1, db_param_b="test", valuation_module=valuation))
        depreciation = SubModuleDepreciation(cache_layer=self._cache_layer, input=SubModuleDepreciation.Input(db_param_a=1, db_param_b="test", valuation_module=valuation))
        return self.SubModules(
            valuation=valuation,
            proforma=proforma,
            depreciation=depreciation) 
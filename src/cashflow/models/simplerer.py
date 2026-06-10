from abc import ABC, abstractmethod
from pydantic import BaseModel, PrivateAttr
from datetime import datetime, timedelta

class BaseDataElement(ABC, BaseModel):
    pass

class TimeSeries(BaseDataElement):
    values: list[float]
    dates: list[datetime]

class Scalar(BaseDataElement):
    value: float | int | bool | str


class ModelConfig(BaseModel):
    name: str
class ComputeUnitInput(BaseModel):
    pass
class ComputeUnitOutput(BaseModel):
    pass

CASHFLOW_HIERARCHY: list[type] = []

class BaseComputeUnit(ABC, BaseModel):
    my_config: ModelConfig
    input: ComputeUnitInput | None = None
    _output: ComputeUnitOutput = PrivateAttr(default=None)

    class Input(ComputeUnitInput):
        pass

    class Output(ComputeUnitOutput):
        pass

    def __init__subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if CASHFLOW_HIERARCHY:
            cls._validate_class_structure()

    @classmethod
    def get_class_in_hierarchy(cls) -> type['BaseComputeUnit']:
        for k in reversed(CASHFLOW_HIERARCHY):
            if cls is k or issubclass(cls, k):
                return k
        raise ValueError(f"class {cls} not found in hierarchy")

    @classmethod
    def get_child_in_hierarchy(cls) -> type['BaseComputeUnit']:
        index_in_hierarchy = CASHFLOW_HIERARCHY.index(cls.get_class_in_hierarchy())
        if index_in_hierarchy == len(CASHFLOW_HIERARCHY) - 1:
            return BaseDataElement
        return CASHFLOW_HIERARCHY[index_in_hierarchy + 1]

    @classmethod
    def _validate_class_structure(cls) -> None:
        # validate is instance of get_class_in_hierarchy()
        class_in_hierarchy = cls.get_class_in_hierarchy()
        # validate all input_elements are the same type as cls
        for field_name, field_info in cls.Input.model_fields.items():
            field_type = field_info.annotation
            if not issubclass(field_type, class_in_hierarchy):
                raise ValueError(f"field {field_name} must be of type {class_in_hierarchy}")
        # validate all output_elements are one level down from cls in the class hierarchy
        one_level_down_from_cls = cls.get_child_in_hierarchy()
        for field_name, field_info in cls.Output.model_fields.items():
            field_type = field_info.annotation
            if not issubclass(field_type, one_level_down_from_cls):
                raise ValueError(f"field {field_name} must be of type {one_level_down_from_cls}")

    @property
    def output(self) -> ComputeUnitOutput:
        if self._output is None:
            self.run()
        return self._output

    def run(self) -> ComputeUnitOutput:
        self._output = self._compute_output()

    def _compute_output(self) -> ComputeUnitOutput:
        raise NotImplementedError("must be implemented by subclass")




class Node(BaseComputeUnit):
    pass


class Submodule(BaseComputeUnit):
    pass

class CashFlow(BaseComputeUnit):
    pass

class CashFlowAggregator(BaseComputeUnit):
    pass


class ValuationDbAccessNode(Node):
        input: None = None
        class Output(ComputeUnitOutput):
            fmv_from_db: Scalar
            step_up_pct_from_db: Scalar
        
        def _compute_output(self) -> Output:
            return self.Output(fmv_from_db=Scalar(value=1000000), step_up_pct_from_db=Scalar(value=0.05))

class ValuationSubmodule( Submodule):
    input: None = None
    class Output(ComputeUnitOutput):
        fmv_node: ValuationDbAccessNode
    def _compute_output(self) -> ValuationDbAccessNode.Output:
            return self.Output(fmv_node=ValuationDbAccessNode(my_config=self.my_config))

class ProformaDbAccessNode(Node):
    input: None = None
    class Output(ComputeUnitOutput):
        revenue_fmv_multiplier_per_year: Scalar
    def _compute_output(self) -> Output:
            return self.Output(revenue_fmv_multiplier_per_year=Scalar(value=1.10))

class ProformaCalculationNode(Node):
    class Input(ComputeUnitInput):
        proforma_db_access_node: ProformaDbAccessNode
        fmv_db_access_node: ValuationDbAccessNode
    class Output(ComputeUnitOutput):
        revenue_timeseries: TimeSeries
    def _compute_output(self) -> Output:
        revenue_timeseries = TimeSeries(
            values=[
                self.input.fmv_db_access_node.output.fmv_from_db.value * ( self.input.proforma_db_access_node.output.revenue_fmv_multiplier_per_year.value ** j)
                    for j in range(10)], dates=[datetime.now() + timedelta(days=i) for i in range(10)])
        
        return self.Output(
            revenue_timeseries=revenue_timeseries)


class ProformaSubmodule( Submodule):
    class Input(ComputeUnitInput):
        valuation_submodule: ValuationSubmodule
    class Output(ComputeUnitOutput):
        proforma_db_access_node: ProformaDbAccessNode
        proforma_calculation_node: ProformaCalculationNode


    def _compute_output(self) -> Output:
        proforma_db_access_node = ProformaDbAccessNode(my_config=self.my_config)
        proforma_calculation_node = ProformaCalculationNode(
            my_config=self.my_config, 
            input=ProformaCalculationNode.Input(
                proforma_db_access_node=proforma_db_access_node, 
                fmv_db_access_node=self.input.valuation_submodule.output.fmv_node))
        return self.Output(proforma_db_access_node=proforma_db_access_node, proforma_calculation_node=proforma_calculation_node)

class CashFlowModel(CashFlow):
    input: None = None
    class Output(ComputeUnitOutput):
        valuation: ValuationSubmodule
        proforma: ProformaSubmodule
        
    def _compute_output(self) -> Output:
        valuation  = ValuationSubmodule(my_config=self.my_config)
        proforma  = ProformaSubmodule(my_config=self.my_config, input=ProformaSubmodule.Input(valuation_submodule=valuation ))

        return self.Output(valuation=valuation, proforma=proforma, extra_output=Scalar(value=1000000))


class CashFlowAnalysisModel(CashFlow):
    input: None = None
    class Input(ComputeUnitInput):
        cashflow_model_Q1: CashFlowModel
        cashflow_model_Q2: CashFlowModel
        cashflow_model_Q3: CashFlowModel
        cashflow_model_Q4: CashFlowModel
    class Output(ComputeUnitOutput):
        cashflow_model: CashFlow
    def _compute_output(self) -> Output:
        return self.Output(cashflow_model=self.input.cashflow_model)

class QuarterlyCashFlowAggregatorModel(CashFlowAggregator):
    input: None = None
    class Output(ComputeUnitOutput):
        cashflow_model_Q1: CashFlowModel
        cashflow_model_Q2: CashFlowModel
        cashflow_model_Q3: CashFlowModel
        cashflow_model_Q4: CashFlowModel
        cashflow_analysis_model: CashFlowAnalysisModel
        

CASHFLOW_HIERARCHY = [CashFlow, Submodule, Node, BaseDataElement]

def _all_compute_unit_subclasses() -> list[type['BaseComputeUnit']]:
    result: list[type['BaseComputeUnit']] = []
    def walk(compute_unit_cls: type['BaseComputeUnit']) -> None:
        result.append(compute_unit_cls)
        for subclass in compute_unit_cls.__subclasses__():
            walk(subclass)
    for subclass in BaseComputeUnit.__subclasses__():
        walk(subclass)
    return result

for _compute_unit_cls in _all_compute_unit_subclasses():
    _compute_unit_cls._validate_class_structure()

def main():
    cashflow_model = CashFlowModel(my_config=ModelConfig(name="cashflow"))
    print(cashflow_model.output.proforma.output.proforma_calculation_node.output.revenue_timeseries.values)

if __name__ == "__main__":
    main()
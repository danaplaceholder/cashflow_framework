
from datetime import datetime, timedelta

from cashflow.models.base import ComputeUnitInput, AbstractComputeUnit, ComputeUnitOutput, ModelConfig, Scalar, TimeSeries
from cashflow.models.layers import Layers

class DbAccessNode(Layers.Node, AbstractComputeUnit ):
    pass

class CalculationNode(Layers.Node, AbstractComputeUnit ):
    pass

class ValuationDbAccessNode(DbAccessNode):
    input: None = None

    class Output(ComputeUnitOutput):
        fmv_from_db: Scalar
        step_up_pct_from_db: Scalar

    def _compute_output(self) -> Output:
        return self.Output(fmv_from_db=Scalar(value=1000000), step_up_pct_from_db=Scalar(value=0.05))


class ProformaDbAccessNode(DbAccessNode):
    input: None = None

    class Output(ComputeUnitOutput):
        revenue_fmv_multiplier_per_year: Scalar

    def _compute_output(self) -> Output:
        return self.Output(revenue_fmv_multiplier_per_year=Scalar(value=1.10))
    

class ProformaCalculationNode(CalculationNode):
    class Input(ComputeUnitInput):
        proforma_db_access_node: ProformaDbAccessNode
        fmv_db_access_node: ValuationDbAccessNode

    class Output(ComputeUnitOutput):
        revenue_timeseries: TimeSeries

    def _compute_output(self) -> Output:
        revenue_timeseries = TimeSeries(
            values=[
                self.input.fmv_db_access_node.output.fmv_from_db.value
                * (self.input.proforma_db_access_node.output.revenue_fmv_multiplier_per_year.value ** j)
                for j in range(10)
            ],
            dates=[datetime.now() + timedelta(days=i) for i in range(10)],
        )
        return self.Output(revenue_timeseries=revenue_timeseries)

class AbstractLoanDbAccessNode(DbAccessNode, AbstractComputeUnit):
    class Output(ComputeUnitOutput):
        loan_amount: Scalar
        interest_rate: Scalar
        fee_schedule: TimeSeries

class AbstractLoanCalculationeNode(CalculationNode, AbstractComputeUnit): 
    class Input(ComputeUnitInput):
        loan_db_access_node: AbstractLoanDbAccessNode
    class Output(ComputeUnitOutput):
        principal: TimeSeries
        interest: TimeSeries
class AbstractLoanSubmodule(Layers.Submodule, AbstractComputeUnit):
    class Output(ComputeUnitOutput):
        loan_db_access_node: AbstractLoanDbAccessNode
        debt_service_node: AbstractLoanCalculationeNode

class ConstructionLoanDbAccessNode(DbAccessNode):
    class Output(ComputeUnitOutput):
        construction_amount: Scalar
        construction_schedule: TimeSeries

class ValuationSubmodule(Layers.Submodule):
    input: None = None

    class Output(ComputeUnitOutput):
        fmv_node: ValuationDbAccessNode

    def _compute_output(self) -> Output:
        return self.Output(fmv_node=ValuationDbAccessNode(my_config=self.my_config))


class ProformaSubmodule(Layers.Submodule):
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
                fmv_db_access_node=self.input.valuation_submodule.output.fmv_node,
            ),
        )
        return self.Output(
            proforma_db_access_node=proforma_db_access_node,
            proforma_calculation_node=proforma_calculation_node,
        )

class CashFlowModel(Layers.CashFlow):
    input: None = None

    class Output(ComputeUnitOutput):
        valuation: ValuationSubmodule
        proforma: ProformaSubmodule

    def _compute_output(self) -> Output:
        valuation = ValuationSubmodule(my_config=self.my_config)
        proforma = ProformaSubmodule(
            my_config=self.my_config,
            input=ProformaSubmodule.Input(valuation_submodule=valuation),
        )
        return self.Output(valuation=valuation, proforma=proforma)


def main():
    valuation_submodule = ValuationSubmodule(my_config=ModelConfig(name="valuation"))
    print(valuation_submodule.output.fmv_node.output.fmv_from_db.value)

    #outermost_compute_model = CashFlowModel(my_config=ModelConfig(name="outmost"))
    #print(outermost_compute_model.output.proforma.output.proforma_calculation_node.output.revenue_timeseries.values)


if __name__ == "__main__":
    main()

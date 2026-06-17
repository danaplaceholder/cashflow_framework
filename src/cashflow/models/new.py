
from datetime import datetime, timedelta

from cashflow.models.base import ComputeUnitInput, AbstractComputeUnit, ComputeUnitOutput, ModelConfig, Scalar, TimeSeries
from cashflow.models.layers import Layers
import os

class DataAccessNode(Layers.Node, AbstractComputeUnit ):
    def _write_to_external_data_access_layer(self, optional_message: str = None) -> None:
        # DO Something 
        print("writing to external data access layer")
        if optional_message:
            print(optional_message)
    
    def _inner_compute_output(self) -> ComputeUnitOutput:
        """this is the function that data access nodes will actually modify"""

    def _compute_output(self) -> ComputeUnitOutput:
        """ data access nodes will leave this alone"""
        self._write_to_external_data_access_layer()
        try:    
            return self._inner_compute_output()
        except Exception as e:
            self._write_to_external_data_access_layer(f"{self.__class__.__name__} at {datetime.now().isoformat()} failed to compute output: {e}")
            raise e

class ApiAccessNode(DataAccessNode, AbstractComputeUnit):
    pass       

class TaxDbAccessNode(DataAccessNode):
    class Output(ComputeUnitOutput):
        tax_rate: Scalar
    def _inner_compute_output(self) -> ComputeUnitOutput:
        return self.Output(tax_rate=Scalar(value=0.21))

class BondApiAccessNode(ApiAccessNode):
    class Output(ComputeUnitOutput):
        coupon_amount: Scalar
        number_of_bonds: Scalar
        realized_gain: Scalar
    
    def _inner_compute_output(self) -> ComputeUnitOutput:
        return self.Output(coupon_amount=Scalar(value=110), number_of_bonds=Scalar(value=11), realized_gain=Scalar(value=101))


class StockApiAccessNode(ApiAccessNode):
    class Output(ComputeUnitOutput):
        dividend_rate: Scalar
        dividend_amount: Scalar
        number_of_shares: Scalar
        realized_gain: Scalar
    
    def _inner_compute_output(self) -> ComputeUnitOutput:
        return self.Output(dividend_rate=Scalar(value=0.05), dividend_amount=Scalar(value=100), number_of_shares=Scalar(value=1000), realized_gain=Scalar(value=100))




class TaxBurdenCalculationNode(Layers.Node, AbstractComputeUnit ):
    pass

class BondTaxBurdenCalculationNode(TaxBurdenCalculationNode):
    class Input(ComputeUnitInput):
        tax_db_access_node: TaxDbAccessNode
        bond_api_access: BondApiAccessNode  
    class Output(ComputeUnitOutput):
        coupon_tax_burden: Scalar
        realized_gain_tax_burden: Scalar
        total_tax_burden: Scalar
    def _inner_compute_output(self) -> ComputeUnitOutput:
        coupon_tax_burden = Scalar(value=self.input.tax_db_access_node.output.tax_rate.value * self.input.bond_api_access.output.coupon_amount.value)
        realized_gain_tax_burden = Scalar(value=self.input.tax_db_access_node.output.tax_rate.value * self.input.bond_api_access.output.realized_gain.value)
        total_tax_burden = Scalar(value=coupon_tax_burden.value + realized_gain_tax_burden.value)
        return self.Output(coupon_tax_burden=coupon_tax_burden, realized_gain_tax_burden=realized_gain_tax_burden, total_tax_burden=total_tax_burden)

    def _compute_output(self) -> Output:
        return self._inner_compute_output()


class StockTaxBurdenCalculationNode(TaxBurdenCalculationNode):
    class Input(ComputeUnitInput):
        tax_db_access_node: TaxDbAccessNode
        stock_api_access: StockApiAccessNode
    class Output(ComputeUnitOutput):
        dividend_tax_burden: Scalar
        realized_gain_tax_burden: Scalar
        total_tax_burden: Scalar
    def _inner_compute_output(self) -> ComputeUnitOutput:
        dividend_tax_burden = self.input.tax_db_access_node.output.tax_rate.value * self.input.stock_api_access.output.dividend_amount.value
        realized_gain_tax_burden = self.input.tax_db_access_node.output.tax_rate.value * self.input.stock_api_access.output.realized_gain.value
        total_tax_burden = dividend_tax_burden + realized_gain_tax_burden
        return self.Output(dividend_tax_burden=Scalar(value=dividend_tax_burden), realized_gain_tax_burden=Scalar(value=realized_gain_tax_burden), total_tax_burden=Scalar(value=total_tax_burden))
    
    def _compute_output(self) -> Output:
        return self._inner_compute_output()


class CalculationNode(Layers.Node, AbstractComputeUnit ):
    pass

class CashflowApiAccessNode(ApiAccessNode, AbstractComputeUnit):
    class Output(ComputeUnitOutput):
        pass
    def _inner_compute_output(self) -> ComputeUnitOutput:
        return Scalar(value=100)


class AssetSubmodule(Layers.Submodule, AbstractComputeUnit):
    class Input(ComputeUnitInput):
        pass

    class Output(ComputeUnitOutput):
        pass

class BondSubmodule(AssetSubmodule):
    class Output(ComputeUnitOutput):
        bond_api_access: BondApiAccessNode
        bond_tax_burden_calculation_node: TaxBurdenCalculationNode

    def _compute_output(self) -> Output:
        api_access = BondApiAccessNode(my_config=self.my_config)
        tax_db_access_node = TaxDbAccessNode(my_config=self.my_config)
        tax_burden_calculation_node = BondTaxBurdenCalculationNode(my_config=self.my_config, input=BondTaxBurdenCalculationNode.Input(tax_db_access_node=tax_db_access_node, bond_api_access=api_access))
        return self.Output(bond_api_access=api_access, bond_tax_burden_calculation_node=tax_burden_calculation_node)


class StockSubmodule(AssetSubmodule):
    class Output(ComputeUnitOutput):
        stock_api_access: StockApiAccessNode
        stock_tax_burden_calculation_node: TaxBurdenCalculationNode

    def _compute_output(self) -> Output:
        api_access = StockApiAccessNode(my_config=self.my_config)
        tax_db_access_node = TaxDbAccessNode(my_config=self.my_config)
        tax_burden_calculation_node = StockTaxBurdenCalculationNode(my_config=self.my_config, input=StockTaxBurdenCalculationNode.Input(tax_db_access_node=tax_db_access_node, stock_api_access=api_access))
        return self.Output(stock_api_access=api_access, stock_tax_burden_calculation_node=tax_burden_calculation_node)


class TaxBurdenSubmodule(Layers.Submodule):
    class Output(ComputeUnitOutput):
        tax_db_access_node: TaxDbAccessNode
        bond_tax_burden_calculation_node: BondTaxBurdenCalculationNode
        stock_tax_burden_calculation_node: StockTaxBurdenCalculationNode
    
    def _compute_output(self) -> Output:
        tax_db_access_node = TaxDbAccessNode(my_config=self.my_config)
        bond_tax_burden_calculation_node = BondTaxBurdenCalculationNode(my_config=self.my_config, input=BondTaxBurdenCalculationNode.Input(tax_db_access_node=tax_db_access_node, bond_api_access=BondApiAccessNode(my_config=self.my_config)))
        stock_tax_burden_calculation_node = StockTaxBurdenCalculationNode(my_config=self.my_config, input=StockTaxBurdenCalculationNode.Input(tax_db_access_node=tax_db_access_node, stock_api_access=StockApiAccessNode(my_config=self.my_config)))
        return self.Output(
            tax_db_access_node=tax_db_access_node,
            bond_tax_burden_calculation_node=bond_tax_burden_calculation_node,
            stock_tax_burden_calculation_node=stock_tax_burden_calculation_node
        )

class CashFlowModel(Layers.CashFlow):
    input: None = None

    class Output(ComputeUnitOutput):
        tax_burden_submodule: TaxBurdenSubmodule

    
    def _compute_output(self) -> Output:
        
        return self.Output(tax_burden_submodule=TaxBurdenSubmodule(my_config=self.my_config))


def main():
    #valuation_submodule = ValuationSubmodule(my_config=ModelConfig(name="valuation"))
    #print(valuation_submodule.output.fmv_node.output.fmv_from_db.value)

    outermost_compute_model = CashFlowModel(my_config=ModelConfig(name="outmost"))
    bond_total_tax_burden = outermost_compute_model.output.tax_burden_submodule.output.bond_tax_burden_calculation_node.output.total_tax_burden.value
    stock_total_tax_burden = outermost_compute_model.output.tax_burden_submodule.output.stock_tax_burden_calculation_node.output.total_tax_burden.value
    print(f"bond total tax burden: {bond_total_tax_burden}")
    print(f"stock total tax burden: {stock_total_tax_burden}")
    name = f"cashflow_{outermost_compute_model.my_config.name}"
    full_path = os.path.join(os.path.dirname(__file__), f"{name}.svg")  
    outermost_compute_model.render(full_path)
    print(f"svg written to {os.path.join(os.path.dirname(__file__), f"cashflow_{outermost_compute_model.my_config.name}.svg")}")

if __name__ == "__main__":
    main()

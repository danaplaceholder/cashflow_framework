"""
Cash flows out 

previous month savings: 1000

job: 
    inflow 100 

taxes: 


bills:

public transit 

food:

end_of_month_savings


class Node(BaseComputeUnit):
    input: Input
    output: Output

    class Input(BaseComputeUnitInput):
         input_1: Node
         input_2: list[Node]

    class Output(BaseComputeUnitOutput):
        output_1: BaseDataElement
        output_2: list[BaseDataElement]
         

    
my_node = Node(
     input=Node.Input(
         input_1=
         input_2=[]
         )
      output=Node.Output(
          output_1=BaseDataElement(value=100),
          output_2=[]
          )
    )


class Submodule(BaseComputeUnit):
    class Input(BaseComputeUnitInput):
        input_1: Submodule  
        input_2: list[Submodule]
    class Output(BaseComputeUnitOutput):
        output_1: Node
        output_2: list[Node]
        output_3: Submodule
        output_4: list[Submodule]

"""


from datetime import datetime, timedelta

from cashflow.models.base import ComputeUnitInput, AbstractComputeUnit, ComputeUnitOutput, ModelConfig, Scalar, TimeSeries, TradeList
from cashflow.models.layers import Layers
import os
from pydantic import BaseModel


TAX_RATE = 0.2





class JobIncomeNode(Layers.Node):
    class Output(ComputeUnitOutput):
        job_income: Scalar
    def _compute_output(self) -> Output:
        return self.Output(job_income=Scalar(value=100))
        
class InvestmentIncomeNode(Layers.Node):
    class Output(ComputeUnitOutput):
        investment_income: Scalar
    def _compute_output(self) -> Output:
        return self.Output(investment_income=Scalar(value=100))

class TaxBurdenNode(Layers.Node):
    class Input(ComputeUnitInput):
        job_income_node: JobIncomeNode
    
    class Output(ComputeUnitOutput):
        tax_burden: Scalar
    def _compute_output(self) -> Output:
        return self.Output(tax_burden=Scalar(value=100 * TAX_RATE))

class ExpensesNode(Layers.Node):
    class Input(ComputeUnitInput):
        pass
    class Output(ComputeUnitOutput):
        bills: Scalar
        public_transit: Scalar
        food: Scalar
        total_expenses: Scalar
    def _compute_output(self) -> Output:
        bills = Scalar(value=100)
        public_transit = Scalar(value=100)
        food = Scalar(value=100)
        total_expenses = Scalar(value=bills.value + public_transit.value + food.value)
        return self.Output(bills=bills, public_transit=public_transit, food=food, total_expenses=total_expenses)

class SavingsNode(Layers.Node):
    class Input(ComputeUnitInput):
        job_income_node: JobIncomeNode
        investment_income_node: InvestmentIncomeNode
        tax_burden_node: TaxBurdenNode
        expenses_node: ExpensesNode
    class Output(ComputeUnitOutput):
        savings: Scalar
    def _compute_output(self) -> Output:
        job_income = self.input.job_income_node.output.job_income.value
        investment_income = self.input.investment_income_node.output.investment_income.value
        tax_burden = self.input.tax_burden_node.output.tax_burden.value
        expenses = self.input.expenses_node.output.total_expenses.value
        savings = job_income + investment_income - tax_burden - expenses + self.my_config.previous_month_savings.value
        return self.Output(savings=Scalar(value=savings))

class IncomeSubmodule(Layers.Submodule):
    class Output(ComputeUnitOutput):
        job_income_node: JobIncomeNode
        investment_income_node: InvestmentIncomeNode
    def _compute_output(self) -> Output:
        job_income_node = JobIncomeNode(my_config=self.my_config)
        investment_income_node = InvestmentIncomeNode(my_config=self.my_config)
        return self.Output(job_income_node=job_income_node, investment_income_node=investment_income_node)
class TaxSubmodule(Layers.Submodule):
    class Input(ComputeUnitInput):
        income_submodule: IncomeSubmodule
    class Output(ComputeUnitOutput):
        tax_burden_node: TaxBurdenNode
    def _compute_output(self) -> Output:
        tax_burden_node = TaxBurdenNode(my_config=self.my_config, input=TaxBurdenNode.Input(job_income_node=self.input.income_submodule.output.job_income_node))
        return self.Output(tax_burden_node=tax_burden_node)

class ExpensesSubmodule(Layers.Submodule):
    class Output(ComputeUnitOutput):
        expenses_node: ExpensesNode
    def _compute_output(self) -> Output:
        expenses_node = ExpensesNode(my_config=self.my_config)
        return self.Output(expenses_node=expenses_node)

class SavingsSubmodule(Layers.Submodule):
    class Input(ComputeUnitInput):
        income_submodule: IncomeSubmodule
        tax_submodule: TaxSubmodule
        expenses_submodule: ExpensesSubmodule
    class Output(ComputeUnitOutput):
        savings_node: SavingsNode
    def _compute_output(self) -> Output:
        savings_node = SavingsNode(my_config=self.my_config, input=SavingsNode.Input(
            job_income_node=self.input.income_submodule.output.job_income_node,
            investment_income_node=self.input.income_submodule.output.investment_income_node,
            tax_burden_node=self.input.tax_submodule.output.tax_burden_node,
            expenses_node=self.input.expenses_submodule.output.expenses_node))
        return self.Output(savings_node=savings_node)

class KrisMonthly(Layers.CashFlow):

    class Output(ComputeUnitOutput):
        income_submodule: IncomeSubmodule
        tax_submodule: TaxSubmodule
        expenses_submodule: ExpensesSubmodule
        savings_submodule: SavingsSubmodule

    def _compute_output(self) -> Output:
        income_submodule = IncomeSubmodule(my_config=self.my_config)
        tax_submodule = TaxSubmodule(my_config=self.my_config, input=TaxSubmodule.Input(income_submodule=income_submodule))
        expenses_submodule = ExpensesSubmodule(my_config=self.my_config)
        savings_submodule = SavingsSubmodule(my_config=self.my_config, input=SavingsSubmodule.Input(income_submodule=income_submodule, tax_submodule=tax_submodule, expenses_submodule=expenses_submodule))
        return self.Output(income_submodule=income_submodule, tax_submodule=tax_submodule, expenses_submodule=expenses_submodule, savings_submodule=savings_submodule)

class KrisMonthlyConfig(ModelConfig):
    name: str
    previous_month_savings: Scalar
# run 
if __name__ == "__main__":

    model = KrisMonthly(my_config=KrisMonthlyConfig(name="kris_monthly", previous_month_savings=Scalar(value=1000)))
    model.run()
    print(model.output.income_submodule.output.job_income_node.output.job_income.value)
    print(model.output.income_submodule.output.investment_income_node.output.investment_income.value)
    print(model.output.tax_submodule.output.tax_burden_node.output.tax_burden.value)
    print(model.output.expenses_submodule.output.expenses_node.output.total_expenses.value)
    print(model.output.savings_submodule.output.savings_node.output.savings.value)
    name = f"kris_monthly_{model.my_config.name}"
    full_path = os.path.join(os.path.dirname(__file__), f"{name}.svg")  
    model.render(full_path)
    print(f"wrote {full_path}")



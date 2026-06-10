from cashflow.models.base import BaseComputeUnit, BaseDataElement, ModelHierarchy


class Layers(ModelHierarchy):
    class Node(BaseComputeUnit):
        pass

    class Submodule(BaseComputeUnit):
        pass

    class CashFlow(BaseComputeUnit):
        pass

    class CashFlowModelNetwork(BaseComputeUnit):
        pass

    @classmethod
    def get_hierarchy(cls) -> list[type]:
        return [cls.CashFlowModelNetwork, cls.CashFlow, cls.Submodule, cls.Node, BaseDataElement]

from cashflow.models.base import BaseComputeUnit, BaseDataElement, ModelHierarchy


class Layers(ModelHierarchy):
    class Node(BaseComputeUnit):
        pass

    class CashFlow(BaseComputeUnit):
        pass



    @classmethod
    def get_hierarchy(cls) -> list[type]:
        return [cls.CashFlow, cls.Node, BaseDataElement]

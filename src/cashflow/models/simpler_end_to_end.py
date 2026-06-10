from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import PrivateAttr

class BaseDataFlowElement(ABC, BaseModel):
    class InputElements(BaseModel):
        """
        e.g. element_1: BaseDataFlowElement
        """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._validate_class_structure()
    




class BaseComputeUnit(ABC, BaseModel):
    def InputElements(BaseModel):
        pass
    def OutputElements(BaseModel):
        pass
    input_elements: InputElements
    hierarchy_index: list[type[BaseComputeUnit]]
    _output: OutputElements = PrivateAttr()
    model_config: ModelConfig


    def output(self) -> OutputElements:
        return self._output

    def run(self) -> OutputElements:
        if self._output is None:
            self._output = self._compute_output()

    def _compute_output(self) -> OutputElements:
        raise NotImplementedError("must be implemented by subclass")

    def get_class_in_hierarchy(cls) -> type[BaseComputeUnit]:
        for k in CASHFLOW_HIERARCHY:
            if issubclass(cls, k):
                return k
        raise ValueError(f"class {cls} not found in hierarchy")
    def get_child_in_hierarchy(cls) -> type[BaseComputeUnit]:
        class_in_hierarchy = cls.get_class_in_hierarchy()
        index_in_hierarchy = CASHFLOW_HIERARCHY.index(class_in_hierarchy)
        if index_in_hierarchy == len(CASHFLOW_HIERARCHY) - 1:
            return BaseDataFlowElement
        return CASHFLOW_HIERARCHY[index_in_hierarchy + 1]
   
    @classmethod
    def recursive_validate_class_structure(cls, index_in_hierarchy: int) -> None:
        for element in cls.input_elements.model_fields.values():
            if not issubclass(element.type, cls.hierarchy[index_in_hierarchy]):
                raise ValueError(f"input element {element.name} must be of type {cls.hierarchy[index_in_hierarchy]}")
            else:
                cls.recursive_validate_class_structure(element.get_class_in_hierarchy(), CASHFLOW_HIERARCHY[index_in_hierarchy + 1])

        for element in cls.output.model_fields.values():
            if not issubclass(element.type, cls.hierarchy[index_in_hierarchy + 1]):
                raise ValueError(f"output element {element.name} must be of type {cls.hierarchy[index_in_hierarchy + 1]}")
            else:
                cls.recursive_validate_class_structure(element.get_class_in_hierarchy(), CASHFLOW_HIERARCHY[index_in_hierarchy + 2])
    def __init__subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        index_in_hierarchy = CASHFLOW_HIERARCHY.index(cls)
        cls.recursive_validate_class_structure(index_in_hierarchy)

class Node(BaseComputeUnit):
    pass
 

class Submodule(BaseComputeUnit):
    pass
 

class OutermostComputeModel(BaseComputeUnit):
    class InputElements(BaseModel):
        pass
    class ModelConfig(BaseModel):
        name: str

    class Output(BaseModel):
        pass

    input_elements: InputElements | None = None
    model_config: ModelConfig
    _output: Output | None = PrivateAttr()


CASHFLOW_HIERARCHY = [OutermostComputeModel, Submodule, Node, BaseDataFlowElement]
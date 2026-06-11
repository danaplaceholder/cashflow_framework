from abc import ABC
from typing import ClassVar
from pydantic import BaseModel, PrivateAttr
from datetime import datetime


class AbstractComputeUnit(ABC):
    pass


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


class BaseComputeUnit(ABC, BaseModel):
    my_config: ModelConfig
    input: ComputeUnitInput | None = None
    _output: ComputeUnitOutput = PrivateAttr(default=None)
    hierarchy: ClassVar[type['ModelHierarchy'] | None] = None

    class Input(ComputeUnitInput):
        pass

    class Output(ComputeUnitOutput):
        pass

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        try:
            hierarchy = cls.hierarchy_for_class().get_hierarchy()
        except ValueError:
            return
        cls._validate_single_layer_inheritance(hierarchy)
        cls._validate_class_structure(hierarchy)

    def __init__(self, my_config: ModelConfig, input: ComputeUnitInput | None = None):
        super().__init__(my_config=my_config, input=input)
        layer = self.get_class_in_hierarchy(type(self).hierarchy_for_class().get_hierarchy())
        if type(self) is layer:
            raise ValueError(f"class {self} must not be an instance of type {layer}")
        if AbstractComputeUnit in self.__class__.__bases__:
            raise ValueError(f"class {self.__class__.__name__} is abstract and cannot be instantiated")

    @classmethod
    def _class_in_hierarchy(cls, hierarchy: list[type]) -> type['BaseComputeUnit']:
        for k in reversed(hierarchy):
            if cls is k or issubclass(cls, k):
                return k
        raise ValueError(f"class {cls} not found in hierarchy")

    @classmethod
    def _child_in_hierarchy(cls, hierarchy: list[type]) -> type:
        index_in_hierarchy = hierarchy.index(cls._class_in_hierarchy(hierarchy))
        if index_in_hierarchy == len(hierarchy) - 1:
            return BaseDataElement
        return hierarchy[index_in_hierarchy + 1]

    @classmethod
    def hierarchy_for_class(cls) -> type['ModelHierarchy']:
        for klass in cls.__mro__:
            hierarchy = getattr(klass, 'hierarchy', None)
            if hierarchy is not None:
                return hierarchy
        raise ValueError(
            f"{cls.__name__} has no hierarchy; subclass a layer nested inside a ModelHierarchy"
        )
        

    @classmethod
    def _validate_single_layer_inheritance(cls, hierarchy: list[type]) -> None:
        layer_types = [t for t in hierarchy if issubclass(t, BaseComputeUnit)]
        matched = [layer for layer in layer_types if issubclass(cls, layer)]
        if not matched:
            raise ValueError(f"{cls.__name__} is not a subclass of any layer in {layer_types}")
        if len(matched) > 1:
            names = [layer.__name__ for layer in matched]
            raise ValueError(
                f"{cls.__name__} inherits from multiple layers in the same hierarchy: {names}"
            )

    @classmethod
    def get_class_in_hierarchy(cls, hierarchy: list[type['BaseComputeUnit']]) -> type['BaseComputeUnit']:
        return cls._class_in_hierarchy(hierarchy)

    @classmethod
    def get_child_in_hierarchy(cls, hierarchy: list[type['BaseComputeUnit']]) -> type['BaseComputeUnit']:
        return cls._child_in_hierarchy(hierarchy)

    @classmethod
    def _validate_class_structure(cls, hierarchy: list[type['BaseComputeUnit']]) -> None:
        class_in_hierarchy = cls._class_in_hierarchy(hierarchy)
        for field_name, field_info in cls.Input.model_fields.items():
            field_type = field_info.annotation
            if not issubclass(field_type, class_in_hierarchy):
                raise ValueError(f"field {field_name} must be a subclass of type {class_in_hierarchy}")
        one_level_down_from_cls = cls._child_in_hierarchy(hierarchy)
        if len(cls.Output.model_fields) == 0 and AbstractComputeUnit not in cls.__bases__:
            raise ValueError(f"class {cls.__name__} has no output fields")
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


class ModelHierarchyMeta(type):
    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: dict, **kwargs):
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        layer_classes = [
            attr
            for attr in namespace.values()
            if isinstance(attr, type) and issubclass(attr, BaseComputeUnit)
        ]
        for layer in layer_classes:
            layer.hierarchy = cls
        return cls


class ModelHierarchy(metaclass=ModelHierarchyMeta):
    @classmethod
    def get_hierarchy(cls) -> list[type]:
        raise ValueError("ModelHierarchy is an abstract class and cannot be instantiated")

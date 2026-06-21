from abc import ABC
from ast import Pass
from typing import ClassVar
from pydantic import BaseModel, PrivateAttr
from datetime import datetime
from cashflow.viz import _render_registry
from functools import cached_property
import hashlib
from pydantic import ConfigDict
from typing import Any

"""
TODO:
- hash functions 
- caching ......
- time series implementation with bucjeting etc ......  
--....... not much else ! 

"""
class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    # make immutable 
    def __setattr__(self, name: str, value: Any) -> None:
        # allow setting of private attributes
        if name.startswith("_"):
            super().__setattr__(name, value)
            return
        else:
            raise AttributeError(f"cannot set attribute {name} of {self.__class__.__name__}")
    
    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"cannot delete attribute {name} of {self.__class__.__name__}")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._validate()

    def _validate(self) -> None:
        pass
class AbstractComputeUnit(ABC, FrozenModel):
    pass


class BaseDataElement(ABC, FrozenModel):
    input_hash: str = "" # can add an input hash per model_config or other things so don't have to hash really long time series values or dates
    _source_compute_unit: 'BaseComputeUnit' = PrivateAttr(default=None)

    def set_source_compute_unit(self, source_compute_unit: 'BaseComputeUnit') -> None:
        self._source_compute_unit = source_compute_unit
    
    def get_source_compute_unit(self) -> 'BaseComputeUnit':
        return self._source_compute_unit

    def hash(self) -> str:
        if self.input_hash:
            return self.input_hash
        else:
            return hashlib.sha256(str(self.model_dump()).encode()).hexdigest()
class TimeSeries(BaseDataElement):
    values: list[float]
    dates: list[datetime]

class Scalar(BaseDataElement):
    value: float | int | bool | str

class TradeList(BaseDataElement):
    class Trade(BaseModel):
        symbol: str
        category: str
        trade_id: str
        direction: str
    trades: list[Trade]

class ModelConfig(BaseModel):
    name: str
    @cached_property
    def hash(self) -> str:
        return "model_config_hash"


class ComputeUnitInput(BaseModel):
    pass # TODO: add input hash
    


class ComputeUnitOutput(BaseModel):
    pass  

class BaseComputeUnit(ABC, BaseModel):

    my_config: ModelConfig
    input: ComputeUnitInput | None = None
    _output: ComputeUnitOutput = PrivateAttr(default=None)
    _dependents: list['BaseComputeUnit'] = PrivateAttr(default_factory=list)
    _source_compute_unit: 'BaseComputeUnit' = PrivateAttr(default=None)
    hierarchy: ClassVar[type['ModelHierarchy'] | None] = None

    class Input(ComputeUnitInput):
        pass

    class Output(ComputeUnitOutput):
        pass

    def hash(self) -> str:
        pass

    @property
    def name(self) -> str:
        memory_address = id(self)
        return f"{self.__class__.__name__}_{memory_address}"


    def set_source_compute_unit(self, source_compute_unit: 'BaseComputeUnit') -> None:
        self._source_compute_unit = source_compute_unit

    def get_source_compute_unit(self) -> 'BaseComputeUnit':
        return self._source_compute_unit
    
    def get_dependents(self) -> list['BaseComputeUnit']:
        return self._dependents
    




    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        cls._validate_class()

    def __init__(self, my_config: ModelConfig, input: ComputeUnitInput | None = None):
        super().__init__(my_config=my_config, input=input)
        self._validate_instance()
        self._add_instance_to_input_node_dependents()
    
    def add_dependent(self, dependent: 'BaseComputeUnit') -> None:
        self._dependents.append(dependent)

    def _add_instance_to_input_node_dependents(self) -> None:
        if self.input:
            for field_name, field_info in self.Input.model_fields.items():
                value = getattr(self.input, field_name)
                if issubclass(field_info.annotation, BaseComputeUnit):
                    value.add_dependent(self)
                else:
                    raise ValueError(f"field {field_name} must be a subclass of BaseComputeUnit")

    def _validate_instance(self) -> None:
        layer = self.get_class_in_hierarchy(type(self).hierarchy_for_class().get_hierarchy())
        if type(self) is layer:
            raise ValueError(f"class {self.__class__.__name__} cannot be instantiated as it is the layer itself")
        if AbstractComputeUnit in self.__class__.__bases__:
            raise ValueError(f"class {self.__class__.__name__} cannot be instantiated as it has been tagged as abstract")

    @classmethod
    def _validate_class(cls) -> None:
        try:
            hierarchy = cls.hierarchy_for_class().get_hierarchy()
        except ValueError:
             #TODO : should this be an error?
            return
        cls._validate_single_layer_inheritance(hierarchy)
        cls._validate_class_structure(hierarchy)

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
            if field_type == list:
                field_type = field_info.annotation[0]
            if not issubclass(field_type, class_in_hierarchy):
                raise ValueError(f"field {field_name} must be a subclass of type {class_in_hierarchy}")
        one_level_down_from_cls = cls._child_in_hierarchy(hierarchy)
        if len(cls.Output.model_fields) == 0 and AbstractComputeUnit not in cls.__bases__:
            raise ValueError(f"class {cls.__name__} has no output fields")
        for field_name, field_info in cls.Output.model_fields.items():
            field_type = field_info.annotation
            if field_type == list:
                field_type = field_info.annotation[0]
            if not issubclass(field_type, one_level_down_from_cls):
                raise ValueError(f"field {field_name} must be of type {one_level_down_from_cls}")
        # make sure no extra fields added to model 
        for field_name, field_info in cls.model_fields.items():
            if field_name not in BaseComputeUnit.model_fields.keys():
                raise ValueError(f"field {field_name} is not a valid field for {cls.__name__}")

    @property
    def output(self) -> ComputeUnitOutput:
        if self._output is None:
            self.run()
        return self._output

    def run(self) -> ComputeUnitOutput:
        t_output = self._compute_output()
        for output_name, output_info in self.Output.model_fields.items():
            value = getattr(t_output, output_name)
            if issubclass(output_info.annotation, BaseDataElement):
                value.set_source_compute_unit(self)
            elif issubclass(output_info.annotation, BaseComputeUnit):
                value.set_source_compute_unit(self)
            else:
                raise ValueError(f"field {output_name} must be a subclass of BaseDataElement or BaseComputeUnit")
        self._output = t_output

    def _compute_output(self) -> ComputeUnitOutput:
        raise NotImplementedError("must be implemented by subclass")

    # visualizing the DAG
    def _walk(self, reg):
        uid = id(self)
        if uid in reg["units"]:
            return
        reg["units"][uid] = self
    
        inp = getattr(self, "input", None)
        if inp:
            for f in type(inp).model_fields:
                dep = getattr(inp, f)
                if isinstance(dep, BaseComputeUnit):
                    reg["edges"].append((id(dep), uid, f))
                    dep._walk(reg)

        try:
            out = self.output
        except Exception:
            out = None
        if out:
            for f in type(out).model_fields:
                child = getattr(out, f)
                if isinstance(child, BaseComputeUnit):
                    reg["contains"].append((uid, id(child)))
                    child._walk(reg)
                elif isinstance(child, BaseDataElement):
                    print(f"data element {f} comes from the base compute unit {child.get_source_compute_unit().name}")
                    
    
    def render(self, path="graph.svg"):
        reg = {"units": {}, "contains": [], "edges": []}
        self._walk(reg)
        _render_registry(reg, path)
        return path




class ModelHierarchyMeta(type):
    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: dict, **kwargs):
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        layer_classes = [
            attr
            for attr in namespace.values()
            if isinstance(attr, type) and issubclass(attr, BaseComputeUnit)
        ]
        for layer in layer_classes:
            # Attach the outer class as heirarchy to each inner class
            layer.hierarchy = cls
        return cls


class ModelHierarchy(metaclass=ModelHierarchyMeta):
    @classmethod
    def get_hierarchy(cls) -> list[type]:
        raise ValueError("ModelHierarchy is an abstract class and cannot be instantiated")

from abc import ABC
from datetime import datetime
from typing import Any
from pydantic import BaseModel, PrivateAttr

class StaleDataException(Exception):
    pass

class BaseDataElement(ABC):
    time_created: datetime
    source_compute_unit: 'BaseComputeUnit'

    # immutable
    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError(f"cannot set attribute {name} of {self.__class__.__name__}")
    
    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"cannot delete attribute {name} of {self.__class__.__name__}")
    
    def __init__(self, value: Any):
        self.value = value
        self.time_created = datetime.now()

class BaseComputeUnit(ABC):

    class Input(BaseModel):
        def is_fresh(self) -> bool:
            for field_name, _ in self.model_fields.items():
                value = getattr(self, field_name)
                if not value.is_fresh():
                    return False
            return True

    class Output(BaseModel):
        pass
    input: Input
    _output: Output = PrivateAttr(default=None)

    def is_fresh(self) -> bool:
        raise NotImplementedError("must be implemented by subclass")

    @property
    def output(self) -> Output:
        if self._output is None:
            self.run()
        elif not self.is_fresh():
            temp_output = self._compute_output()
        return self._output

    def run(self):
        max_retries = 3
        for retry in range(max_retries):
            try:
                self._output = self._compute_output()
                return
            except StaleDataException as e:
                if retry == max_retries - 1:
                    raise e

    def _compute_output(self) -> Output:
        raise NotImplementedError("must be implemented by subclass")


    def _external_data_has_changed(self) -> bool:
        raise NotImplementedError("must be implemented by subclass")

class ExternalDataAccessMixin(ABC):
    def is_fresh(self) -> bool:
    def _external_data_has_changed(self) -> bool:
        raise NotImplementedError("must be implemented by subclass")

class FunctionalComputeMixin(ABC):
    def is_fresh(self) -> bool:
        return self.input.is_fresh()
    def _external_data_has_changed(self) -> bool:
        return False
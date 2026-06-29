import datetime
from cashflow.models.base import BaseComputeUnit, BaseDataElement, ModelConfig, Scalar, TimeSeries, TradeList
from cashflow.models.layers import Layers
from pydantic import BaseModel
from typing import PrivateAttr

"""
TODO: 
- support external data access nodes
- 
"""




class BaseElement(BaseModel):
    class ElementStatus(str, Enum):
        ACTIVE = "active"
        DELETED = "deleted"

    class ElementConfig(BaseModel):
        def fingerprint(self) -> str:
            pass
    created_by: 'Node'
    _status: ElementStatus = PrivateAttr(default=ElementStatus.ACTIVE)
    config: ElementConfig
    def should_exist(self) -> bool:
        if self.is_deleted():
            return False
        else:
            return True
    def identity_key(self) -> str:
        # TODO
        return self.config.fingerprint()

    def fingerprint(self) -> str:
        pass

    def set_status_deleted(self) -> None:
        self._status = BaseElement.ElementStatus.DELETED
        for field_name, _ in self.model_fields.items():
            value = getattr(self, field_name)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, BaseElement):
                        item.set_status_deleted()
            elif isinstance(value, BaseElement):
                value.set_status_deleted()
    def is_deleted(self) -> bool:
        return self._status == BaseElement.ElementStatus.DELETED

class Fingerprint(BaseModel):
        pass
    


class BaseDataElement(BaseElement):
    def fingerprint(self) -> str:
        # TODO
        pass


class Node(BaseElement):
    input: Input | None = None
    _output: Output = PrivateAttr(default=None)

    class Input(BaseModel):
        """

        """
        def fingerprint(self) -> str:
            # TODO
            fingerprint_dict = {}
            for field_name, _ in self.model_fields.items():
                value = getattr(self, field_name)
                if isinstance(value, list):
                    newfingerprints = {item.fingerprint() for item in value}
                else:
                    newfingerprints = {value.fingerprint()}
                fingerprint_dict[field_name] = newfingerprints
            return str(fingerprint_dict)
    
        def is_fresh(self) -> bool:
            # TODO
            for field_name, _ in self.model_fields.items():
                value = getattr(self, field_name)
                if isinstance(value, list):
                    for item in value:
                        if not item.is_fresh():
                            return False
                else:
                    if not value.is_fresh():
                        return False
            return True


    class Output(BaseModel):
        input_fingerprint: Node.Input.Fingerprint

        def fingerprint(self) -> str:
            fingerprint_dict = {}
            for field_name, _ in self.model_fields.items():
                value = getattr(self, field_name)
                if isinstance(value, list):
                    newfingerprints = {item.identity_key() for item in value}
                else:
                    newfingerprints = {value.identity_key()}
                fingerprint_dict[field_name] = newfingerprints
            return str(fingerprint_dict)

        def contains(self, node: 'Node') -> bool:
            for field_name, _ in self.model_fields.items():
                value = getattr(self, field_name)
                if isinstance(value, list):
                    for item in value:
                        if item == node:
                            return True
                elif value == node:
                        return True
            return False
    
        def update(self, new_output: Node.Output) -> None:
            # TODO
            for field_name, _ in new_output.model_fields.items():
                value = getattr(new_output, field_name)
                if isinstance(value, list):
                    updated_list = []
                    old_dict = {item.identity_key(): item for item in value}
                    new_dict = {item.identity_key(): item for item in value}
                    for id_key in set(new_dict.keys()) , set(old_dict.keys()):
                        if id_key in new_dict:
                            if id_key not in old_dict:
                                updated_list.append(new_dict[id_key])
                            else:
                                updated_list.append(old_dict[id_key]) # use the old value
                        else:
                            old_dict[id_key].set_status_deleted()
                    self.setattr(field_name, updated_list)
                elif isinstance(value, BaseElement):
                    old_value = getattr(self, field_name)
                    if old_value.identity_key() != value.identity_key():
                        old_value.set_status_deleted()
                        self.setattr(field_name, value)
                    else:
                        # do nothing 


    @property
    def output(self) -> Output:
        if self._should_exist():
            if self._output is None:
                self._output = self._compute_output()
            elif not self._current_output_is_fresh():
                self._output.update(self._compute_output(self.input.fingerprint()))
            return self._output
        else:
            raise ValueError(f"Node {self.name} should not exist")


    def is_fresh(self) -> bool:
        return self._current_output_is_fresh()

    def _current_output_is_fresh(self) -> bool:
        if self._output.input_fingerprint() != self.input.fingerprint():
            return False
        elif not self._external_data_access_fingerprint_is_fresh():
            return False
        else:
            return True

    def _external_data_access_fingerprint_is_fresh(self) -> bool:
        # TODO
        return True

    def _compute_output(self, input_fingerprint: Node.Input.Fingerprint) -> Output:
        pass


    def _recursive_fingerprint(self) -> str:
        fingerprint_dict = {}
        for field_name, _ in self.model_fields.items():
            value = getattr(self, field_name)
            if isinstance(value, list):
                for item in value:
                    newfingerprints = {item.recursive_fingerprint()}
                fingerprint_dict[field_name] = newfingerprints
            else:
                newfingerprints = {value.recursive_fingerprint()}
            fingerprint_dict[field_name] = newfingerprints
        return str(fingerprint_dict)
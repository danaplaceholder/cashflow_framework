from pydantic import BaseModel
from typing import List, Dict, Any
from pydantic import PrivateAttr
from pydantic import Field
import os
import time
from enum import StrEnum


class Fingerprint(BaseModel):
    identity_key: str
    result_fingerprint_value: str # combination of identity keys (for BaseGraphElements) and values (for BaseDataElements)
    version_number: int
    _timestamp: float = PrivateAttr(default=time.time())
    def is_less_than_100ms_old(self) -> bool:
        fingerprint_age = time.time() - self._timestamp
        if fingerprint_age < 0.01:
            return True
        else:
            return False

    def results_match(self, other: 'Fingerprint') -> bool:
        return self.result_fingerprint_value == other.result_fingerprint_value

    def version_number_matches(self, other: 'Fingerprint') -> bool:
        return self.version_number == other.version_number

    def update(self, other: 'Fingerprint') -> None:
        pass
        # TODO: implement this

    @classmethod
    def combine_fingerprints(self, other: 'Fingerprint') -> 'Fingerprint':
        # TODO: implement this
        pass

class ElementStatus(StrEnum):
    CREATED = "created"
    CHECKING_IF_SHOULD_EXIST = "checking_if_should_exist"
    CHECKING_IF_SHOULD_RECOMPUTE_OUTPUT = "checking_if_should_recompute_output"
    COMPUTING_OUTPUT = "computing_output"
    UPDATING_OUTPUT = "updating_output"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETED = "completed"
    DELETED = "deleted"

class BaseGraphElement(BaseModel):
    # TODO Caching layer ? 

    _status: ElementStatus = PrivateAttr(default=ElementStatus.CREATED)
    config: 'BaseGraphElement.GraphElementConfig' = Field(default=None)
    input: 'BaseGraphElement.Input' = Field(default=None)
    _output: 'BaseGraphElement.Output' = PrivateAttr(default=None)
    _last_input_fingerprint: Fingerprint = PrivateAttr(default=None)
    created_by: 'BaseGraphElement' = None

    def root_node(self) -> 'BaseGraphElement':
        if self.created_by is None:
            return self
        else:
            return self.created_by.root_node()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_status(ElementStatus.CREATED)
    
    def set_status(self, status: ElementStatus) -> None:
        if self._status == status:
            return
        self._status = status
        # render the graph with the new status
        if status in [ElementStatus.CREATED, ElementStatus.COMPUTING_OUTPUT, ElementStatus.COMPLETED, ElementStatus.DELETED, ElementStatus.WAITING_FOR_INPUT, ElementStatus.CHECKING_IF_SHOULD_RECOMPUTE_OUTPUT]:
            from draw import build_graph
            build_graph(self.root_node())

    def config_hash(self) -> str:
        return self.config.hash() if self.config else ""

    def element_name(self) -> str:
        return self.__class__.__name__ + "_" +  self.config_hash() + "_STATUS_" + self._status.value

    class GraphElementConfig(BaseModel):
        element_name: str = Field(default=None)
        def hash(self) -> str:
            return f''.join([field_name+str(getattr(self, field_name)) for field_name, field_info in self.__class__.model_fields.items() if getattr(self, field_name) is not None])
            
    class Input(BaseModel):
        def recursive_input_fingerprint(self) -> Fingerprint:
            all_fields_fingerprints = []
            for field_name, _ in self.__class__.model_fields.items():
                value = getattr(self, field_name)
                if isinstance(value, list):
                    all_fields_fingerprints.append({item.recursive_output_fingerprint() for item in value})
                elif isinstance(value, BaseGraphElement):
                    all_fields_fingerprints.append(value.recursive_output_fingerprint())
                else:
                    all_fields_fingerprints.append(str(value))
            return Fingerprint(value=f''.join(all_fields_fingerprints))
        def update(self, new_input: 'BaseGraphElement.Input') -> None:
            """
            Simpler than updating output. We won't delete any nodes we just make sure we are pointing to the correct nodes per identity keys
            """
            for field_name, _ in self.__class__.model_fields.items():
                old_input_value = getattr(self, field_name)
                new_input_value = getattr(new_input, field_name)

                if isinstance(old_input_value, list):
                    if len(old_input_value) and issubclass(old_input_value[0].__class__, BaseGraphElement) or len(new_input_value) and issubclass(new_input_value[0].__class__, BaseGraphElement):
                        old_dict = {item.identity_key(): item for item in old_input_value}
                        new_dict = {item.identity_key(): item for item in new_input_value}
                        updated_list = []
                        for key, _ in new_dict.items():
                            if key in old_dict:
                                updated_list.append(old_dict[key])
                            else:
                                updated_list.append(new_dict[key])
                            # leave things as is if old_dict has the key but new_dict does not.... just cause a node is no longer in our output, doesn't mean we should delete it from the graph
                        setattr(self, field_name, updated_list)
                elif issubclass(old_input_value.__class__, BaseGraphElement):
                    if old_input_value.identity_key() == new_input_value.identity_key():
                        # do nothing 
                        pass
                    else:
                        setattr(self, field_name, new_input_value)
                
    class Output(BaseModel):
        def contains(self, node: 'BaseGraphElement') -> bool:
            for field_name, _ in self.__class__.model_fields.items():
                value = getattr(self, field_name)
                if isinstance(value, list) and issubclass(value[0].__class__, BaseGraphElement):
                    for item in value:
                        if item.identity_key() == node.identity_key():
                            return True
                elif issubclass(value.__class__, BaseGraphElement):
                    if value.identity_key() == node.identity_key():
                        return True      
            return False
        def update(self, new_output: 'BaseGraphElement.Output') -> None:
            if type(self) != type(new_output):
                raise ValueError(f"new_output must be of type {type(self)}")
            for field_name, field_info in self.__class__.model_fields.items():

                    old_value = getattr(self, field_name)
                    new_value = getattr(new_output, field_name)
                    if isinstance(old_value, list):
                        if len(old_value) and issubclass(old_value[0].__class__, BaseGraphElement) or len(new_value) and issubclass(new_value[0].__class__, BaseGraphElement):
                            old_dict = {item.identity_key(): item for item in old_value}
                            new_dict = {item.identity_key(): item for item in new_value}
                            updated_list = []
                            for key, _ in new_dict.items():
                                if key in old_dict:
                                    updated_old_value = old_dict[key]
                                    updated_old_value.input.update(new_dict[key].input)
                                    updated_list.append(updated_old_value)
                                else:
                                    updated_list.append(new_dict[key])
                            for key, _ in old_dict.items():
                                if key not in new_dict:
                                    old_dict[key].set_status_deleted()
                            setattr(self, field_name, updated_list)
                        else:
                            setattr(self, field_name, new_value)
                    elif issubclass(old_value.__class__, BaseGraphElement):
                        if old_value.identity_key() == new_value.identity_key():
                          old_value.input.update(new_value.input)
                        else:
                            old_value.set_status_deleted()
                            setattr(self, field_name, new_value)
                    else:
                        setattr(self, field_name, new_value)
    @property                       
    def output(self) -> Output:
        if not self.should_exist():
            self.should_exist(logging=True)
            raise ValueError(f"Node {self.config_hash()} of class {self.__class__.__name__} should not exist")
        if self._output is None:
            self._last_input_fingerprint = self.recursive_input_fingerprint()
            self._output = self._outer_compute_output()
        else:
            should_recompute, latest_input_fingerprint = self._outer_should_recompute_output()
            if should_recompute:
                self._last_input_fingerprint = latest_input_fingerprint
                self._output.update( self._outer_compute_output())
            
        return self._output

    def identity_key(self) -> str:
        return self.created_by_identity_key() + self.__class__.__name__ + self.config_hash()

    def created_by_identity_key(self) -> str:
        return self.created_by.identity_key() if self.created_by else ""

    def _compute_output(self) -> Output:
        pass

    def _get_current_cache_key(self) -> str:
        return self.identity_key() + self._last_input_fingerprint.result_fingerprint_value

    def _get_from_cache(self) -> Output:
        # TODO: implement this
        pass

    def _put_in_cache(self, output: Output) -> None:
        # TODO: implement this
        pass


    def _outer_compute_output(self) -> Output:
        # check if in cache
        cache_result = self._get_from_cache()
        if cache_result is not None:
            return cache_result

        self.set_status(ElementStatus.COMPUTING_OUTPUT)
        computed_output = self._compute_output()
        self.set_status(ElementStatus.COMPLETED)
        self._put_in_cache(computed_output)
        return computed_output

    def recursive_input_fingerprint(self) -> str:
        if self.input is None:
            return None
        elif self._last_input_fingerprint is not None and self._last_input_fingerprint.is_less_than_100ms_old():
            return self._last_input_fingerprint
        else:
            next_input_fingerprint = self.input.recursive_input_fingerprint()

            return next_input_fingerprint
    
    def set_input(self, new_input: Input) -> None:
        self.input = new_input
       # self._last_input_fingerprint = self.recursive_input_fingerprint()

    def recursive_output_fingerprint(self) -> str:        
        
        fingerprint_dict = {}
        output = self.output
        if output is None:
            return "NONE"
        for field_name, field_info in output.__class__.model_fields.items():
            if isinstance(getattr(output, field_name), list) and issubclass(getattr(output, field_name)[0].__class__, BaseGraphElement):
                fingerprint_dict[field_name] = {item.recursive_output_fingerprint() for item in getattr(output, field_name)}
            elif isinstance(getattr(output, field_name), BaseGraphElement):
                fingerprint_dict[field_name] = getattr(output, field_name).recursive_output_fingerprint()
            elif isinstance(getattr(output, field_name), list) and issubclass(getattr(output, field_name)[0].__class__, BaseDataElement):
                fingerprint_dict[field_name] = {item.recursive_output_fingerprint() for item in getattr(output, field_name)}
            elif isinstance(getattr(output, field_name), BaseDataElement):
                fingerprint_dict[field_name] = getattr(output, field_name).recursive_output_fingerprint()
            else:
                fingerprint_dict[field_name] = str(getattr(output, field_name))
        return str(fingerprint_dict)
    def should_exist(self ) -> bool:
        if self._status == ElementStatus.DELETED:
            return False
        else:
            if self.created_by is None:
                return True
            elif self.created_by.should_exist():
                return self.created_by.output.contains(self)
            else:
                return False
          
    def set_status_deleted(self) -> None:
        self._status = ElementStatus.DELETED
        output_to_delete = self._output
        for field_name, _ in output_to_delete.__class__.model_fields.items():
            value = getattr(output_to_delete, field_name)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, BaseGraphElement):
                        item.set_status_deleted()
            elif isinstance(value, BaseGraphElement):
                value.set_status_deleted()
        
    def _inner_should_recompute_output(self) -> bool:
        # TODO: implement this
        return False
    def _outer_should_recompute_output(self) -> bool:
        # TODO: implement this
        if self._inner_should_recompute_output():
            return True, self.recursive_input_fingerprint()
        latest_input_fingerprint = self.recursive_input_fingerprint()
        if self._output is None or self._last_input_fingerprint != latest_input_fingerprint:
            should_recompute = True
        else:
            should_recompute = False

        return should_recompute, latest_input_fingerprint
class BaseDataElement(BaseModel):
    def recursive_output_fingerprint(self) -> str:
        return str(self)
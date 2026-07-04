from pydantic import BaseModel
from typing import List, Dict, Any
from pydantic import PrivateAttr
from pydantic import Field
import os
import time
import logging
from enum import StrEnum


class Fingerprint(BaseModel):
    identity_key: str = ""
    field_value_dict: dict
    _version_number: int = PrivateAttr(default=0)
    _timestamp: float = PrivateAttr(default=time.time())

    def __eq__(self, other: 'Fingerprint') -> bool:
        print(f"Checking if {self.identity_key} == {other.identity_key} and {self.version_number_matches(other)}")
        return self.identity_key == other.identity_key and self.version_number_matches(other) # TODO: implement this

    def version_number(self) -> int:
        return self._version_number
    def timestamp(self) -> float:
        return self._timestamp
    
    def _bump_version_number(self) -> None:
        self._version_number += 1
        self._timestamp = time.time()

    def update(self, field_value_dict: dict) -> None:
        if self.field_value_dict != field_value_dict:
            self._bump_version_number()
            self.field_value_dict = field_value_dict
        else:
            pass
    def cache_key(self) -> str:
        return self.identity_key()


    def version_number_matches(self, other: 'Fingerprint') -> bool:
        return self._version_number == other._version_number

    def update(self, input_fingerprint: 'Fingerprint', output_fingerprint: 'Fingerprint') -> None:
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
    _fingerprint: Fingerprint = PrivateAttr(default=None)
    _status: ElementStatus = PrivateAttr(default=ElementStatus.CREATED)
    config: 'BaseGraphElement.GraphElementConfig' = Field(default=None)
    input: 'BaseGraphElement.Input' = Field(default=None)
    _output: 'BaseGraphElement.Output' = PrivateAttr(default=None)
    created_by: 'BaseGraphElement' = None

    @property
    def fingerprint(self) -> Fingerprint:
        return self._fingerprint

    @property
    def root_node(self) -> 'BaseGraphElement':
        if self.created_by is None:
            return self
        else:
            return self.created_by.root_node
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
            build_graph(self.root_node)

    def config_hash(self) -> str:
        return self.config.hash() if self.config else ""

    def element_name(self) -> str:
        return self.__class__.__name__ + "_" +  self.config_hash() + "_STATUS_" + self._status.value

    class GraphElementConfig(BaseModel):
        element_name: str = Field(default=None)
        def hash(self) -> str:
            return f''.join([field_name+str(getattr(self, field_name)) for field_name, field_info in self.__class__.model_fields.items() if getattr(self, field_name) is not None])
            
    class Input(BaseModel):
        _fingerprint: Fingerprint = PrivateAttr(default=None)
        def current_input_fingerprint(self) -> Fingerprint:
            return self._fingerprint
        def get_fresh_input_fingerprint(self, identity_key: str) -> Fingerprint:
            all_field_value_dict = {}
            for field_name, _ in self.__class__.model_fields.items():
                value = getattr(self, field_name)
                if isinstance(value, list):
                    all_field_value_dict[field_name] = [item.recursive_output_fingerprint(identity_key = item.identity_key()) for item in value]
                else:
                    all_field_value_dict[field_name] = value.recursive_output_fingerprint(identity_key = value.identity_key())
            return Fingerprint(field_value_dict=all_field_value_dict, identity_key="INPUT_" + identity_key)

                    
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
        _input_fingerprint: Fingerprint = PrivateAttr(default=None)
        _fingerprint: Fingerprint = PrivateAttr(default=None)

        @property
        def input_fingerprint(self) -> Fingerprint:
            return self._input_fingerprint

        def set_input_fingerprint(self, input_fingerprint: Fingerprint) -> None:
            self._input_fingerprint = input_fingerprint

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
        def update(self, new_output: 'BaseGraphElement.Output', input_fingerprint: Fingerprint) -> None:
            if type(self) != type(new_output):
                raise ValueError(f"new_output must be of type {type(self)}")
            self.set_input_fingerprint(input_fingerprint)
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
                                    updated_old_value.set_input(new_dict[key].input)
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
                          old_value.set_input(new_value.input)
                        else:
                            old_value.set_status_deleted()
                            setattr(self, field_name, new_value)
                    else:
                        setattr(self, field_name, new_value)
            
        def recursive_output_fingerprint(self, identity_key: str) -> str:
            fingerprint_dict = {}
            for field_name, field_info in self.__class__.model_fields.items():
                value = getattr(self, field_name)
                if isinstance(value, list):
                    fingerprint_dict[field_name] = [item.recursive_output_fingerprint(identity_key = item.identity_key()) for item in value]
                else:
                    fingerprint_dict[field_name] = value.recursive_output_fingerprint(identity_key = value.identity_key())
            return Fingerprint(field_value_dict=fingerprint_dict, identity_key="OUTPUT_" + identity_key)
            
                
    @property                       
    def output(self) -> Output:
        if not self.should_exist():
            self.should_exist(logging=True)
            raise ValueError(f"Node {self.config_hash()} of class {self.__class__.__name__} should not exist")
        latest_input_fingerprint = self.get_fresh_input_fingerprint(self.identity_key())
        if self._output is None:
            self._outer_compute_output(pre_compute_input_fingerprint=latest_input_fingerprint)
        else:
            should_recompute = self._outer_should_recompute_output(latest_input_fingerprint=latest_input_fingerprint)
            if should_recompute:
                self._outer_compute_output(pre_compute_input_fingerprint=latest_input_fingerprint)
            
        return self._output

    def identity_key(self) -> str:
        return self.created_by_identity_key() + self.__class__.__name__ + self.config_hash()

    def created_by_identity_key(self) -> str:
        return self.created_by.identity_key() if self.created_by else ""

    def _compute_output(self) -> Output:
        pass

    def _get_current_cache_key(self) -> str:
        return self.fingerprint.cache_key()

    def _get_from_cache(self) -> Output:
        # TODO: implement this
        pass

    def _put_in_cache(self, output: Output) -> None:
        # TODO: implement this
        pass


    def _outer_compute_output(self, pre_compute_input_fingerprint: Fingerprint) -> Output:
        # check if in cache
        cache_result = self._get_from_cache()
        if cache_result is not None:
            return cache_result
        
        # mark as computing output
        self.set_status(ElementStatus.COMPUTING_OUTPUT)

        computed_output = self._compute_output()
        post_compute_input_fingerprint = self.get_fresh_input_fingerprint(self.identity_key())
        
        if pre_compute_input_fingerprint != post_compute_input_fingerprint:
            logging.warning(f"Input fingerprints changed after computation for {self.identity_key()}....recomputing")
            self._outer_compute_output(pre_compute_input_fingerprint=post_compute_input_fingerprint)
        else:
            self._put_in_cache(computed_output)

            if self._output is None:
                self._output = computed_output
                self._output.set_input_fingerprint(pre_compute_input_fingerprint)
            else:
                self._output.update(computed_output, input_fingerprint=pre_compute_input_fingerprint)

            # mark as completed
            self.set_status(ElementStatus.COMPLETED)


    def get_fresh_input_fingerprint(self, identity_key: str) -> str:
        if self.input is None:
            return None
        else:
            next_input_fingerprint = self.input.get_fresh_input_fingerprint(identity_key = identity_key)

            return next_input_fingerprint
    
    def recursive_output_fingerprint(self, identity_key: str) -> str:  
        output = self.output
        if output is None:
            return None
        else:
            return output.recursive_output_fingerprint(identity_key = identity_key)
        
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

    def current_input_fingerprint(self, identity_key: str) -> Fingerprint:
        if self.input is None:
            return None
        else:
            return self.input.current_input_fingerprint()
    def _outer_should_recompute_output(self, latest_input_fingerprint: Fingerprint) -> bool:
        # TODO: implement this
        if self._inner_should_recompute_output():
            return True
        if self._output is None or self._output.input_fingerprint != latest_input_fingerprint:
            print(f"Should recompute output for {self.identity_key()} because input fingerprint changed from {self._output.input_fingerprint} to {latest_input_fingerprint}")
            return True
        else:
            return False

    def set_input(self, new_input: 'BaseGraphElement.Input') -> None:
        if self.input is None:
            self.input = new_input
        else:
            self.input.update(new_input)
class BaseDataElement(BaseModel):
    _fingerprint: Fingerprint = PrivateAttr(default=None)
    
    def identity_key(self) -> str:
        return "DATA_" + str(self)

    
    def recursive_output_fingerprint(self, identity_key: str) -> str:
        return str(self)
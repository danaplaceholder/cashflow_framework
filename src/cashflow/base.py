from pydantic import BaseModel
from typing import List, Dict, Any
from pydantic import PrivateAttr
from pydantic import Field
import os
import time
import graphviz
from enum import StrEnum
import logging

"""
TODO: 
1. epoch verification of freshness 
also 
1. Verification-order early exit. Early cutoff on values is table stakes; the subtler one is bailing mid-verification. If a node demanded A then B then C last run, and A's hash already mismatches, do you stop — without ever demanding B and C? Matters because demanding them isn't free: verification recursively brings them up to date first. A naive "check all recorded deps" verifier does a full subtree of work to confirm what the first hash already told you.
2. The aliasing hazard. When two consumers demand the same node, do they get the same live object? If yes: a node that mutates a demanded DataFrame in place silently corrupts its sibling and the cached value — and worse, the cached value-hash was computed pre-mutation, so verification will happily vouch for a value that no longer matches its own fingerprint. Mine has this bug. Does yours? (Defensive copies, freezing, or hash-on-read all fix it, each with a different cost.)
3. Identity across process death. Pydantic BaseModel gives you great in-process structure, but the question is whether Cell(rate=0.05) constructed next Tuesday resolves to the same durable key as today's — with what happens to that key when you refactor the class but the semantics don't change. Source-hashing over-invalidates on refactors; class-name keys under-invalidate on logic changes. Whichever you chose, you chose a failure mode. Which one?

"""
class GraphEpoch(BaseModel):
    epoch_number: int
    _timestamp: float = PrivateAttr(default=time.time())

class Fingerprint(BaseModel):
    value: str
    epoch_dict: dict[int, GraphEpoch] = PrivateAttr(default={})

    """
    Fingerprint creation must provide the epoch signatures, to make sure current to "state of the world" 
    Fingerprints can be compared to see their actual values , whether they have changed. 
    """

    def __init__(self, value: str, input_epoch_dicts: list[dict[int, GraphEpoch]]):
        # validate the epoch dicts have the save values for the same keys 
        all_keys = set()
        for epoch_dict in input_epoch_dicts:
            all_keys.update(epoch_dict.keys())
        for key in all_keys:
            all_values = [epoch_dict[key] for epoch_dict in input_epoch_dicts if key in epoch_dict]
            if len(set(all_values)) != 1:
                raise ValueError(f"Epoch dicts have different values for key {key}")
        self.epoch_dict = {key: epoch_dict[key] for key in all_keys}



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
        from src.cashflow.draw import build_graph
        if self._status == status:
            return
        self._status = status
        # render the graph with the new status
        if status in [ElementStatus.CREATED, ElementStatus.COMPUTING_OUTPUT, ElementStatus.COMPLETED, ElementStatus.DELETED, ElementStatus.WAITING_FOR_INPUT, ElementStatus.CHECKING_IF_SHOULD_RECOMPUTE_OUTPUT]:
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
        def recursive_input_fingerprint(self, current_only: bool = False) -> Fingerprint:
            all_fields_fingerprints = []
            for field_name, _ in self.__class__.model_fields.items():
                value = getattr(self, field_name)
                if isinstance(value, list):
                    all_fields_fingerprints.append({item.recursive_output_fingerprint(current_only=current_only) for item in value})
                elif isinstance(value, BaseGraphElement):
                    all_fields_fingerprints.append(value.recursive_output_fingerprint(current_only=current_only))
                else:
                    all_fields_fingerprints.append(str(value))
            return Fingerprint(value=f''.join([fingerprint.value for fingerprint in all_fields_fingerprints]), epoch_dicts=[fingerprint.epoch_dict for fingerprint in all_fields_fingerprints])
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
                        for key in set([k for k in old_dict.keys() ] + [k for k in new_dict.keys()]):
                            if key in old_dict and key in new_dict:
                                updated_list.append(old_dict[key])
                            elif key in new_dict:
                                updated_list.append(new_dict[key])
                            else: # this is a delete
                                pass
                            # leave things as is if old_dict has the key but new_dict does not.... just cause a node is no longer in our output, doesn't mean we should delete it from the graph
                        setattr(self, field_name, updated_list)
                elif issubclass(old_input_value.__class__, BaseGraphElement):
                    if old_input_value.identity_key() == new_input_value.identity_key():
                        # do nothing 
                        pass
                    else:
                        setattr(self, field_name, new_input_value)
                
    class Output(BaseModel):
        _epoch_id: int = PrivateAttr(default=0)
        input_fingerprint: Fingerprint = PrivateAttr(default=None)
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

        @property
        def epoch_id(self) -> int:
            return self._epoch_id

        def __eq__(self, other: 'BaseGraphElement.Output') -> bool:
            if type(self) != type(other):
                return False
            for field_name, field_info in self.__class__.model_fields.items():
                old_value = getattr(self, field_name)
                new_value = getattr(other, field_name)
                if old_value != new_value:
                    return False
            return True

        def update(self, new_output: 'BaseGraphElement.Output', new_input_fingerprint: Fingerprint) -> None:
            if self.input_fingerprint == new_input_fingerprint:
                logging.warning(f"Input fingerprint has not changed for node {self.config_hash()} of class {self.__class__.__name__}")
                return
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
                                    # TODO: how to tell if input has changed ? 
                                else:
                                    updated_list.append(new_dict[key])
                            for key, _ in old_dict.items():
                                if key not in new_dict:
                                    old_dict[key]._set_status_deleted()
                            setattr(self, field_name, updated_list)
                        else:
                            setattr(self, field_name, new_value)
                            # TODO: how to tell if output has changed ? 
                    elif issubclass(old_value.__class__, BaseGraphElement):
                        if old_value.identity_key() == new_value.identity_key():
                          old_value.input.update(new_value.input)
                          # TODO: how to tell if input has changed ? 
                        else:
                            old_value._set_status_deleted()
                            setattr(self, field_name, new_value)
                    else:
                        setattr(self, field_name, new_value)

        def recursive_output_fingerprint(self, current_only: bool = False) -> str: 
            fingerprint_dict = {}
            for field_name, field_info in self.__class__.model_fields.items():
                value = getattr(self, field_name)
                if current_only:
                    if isinstance(value, list) and issubclass(value[0].__class__, BaseGraphElement):
                        fingerprint_dict[field_name] = {item.recursive_output_fingerprint(current_only=current_only) for item in value}
                    elif isinstance(value, BaseGraphElement):
                        fingerprint_dict[field_name] = value.recursive_output_fingerprint(current_only=current_only)
                    elif isinstance(value, list) and issubclass(value[0].__class__, BaseDataElement):
                        fingerprint_dict[field_name] = {item.recursive_output_fingerprint(current_only=current_only) for item in value}
                    elif isinstance(value, BaseDataElement):
                        fingerprint_dict[field_name] = value.recursive_output_fingerprint(current_only=current_only)
                    else:
                        fingerprint_dict[field_name] = str(value)

            return Fingerprint(value=str(fingerprint_dict), epoch_id=self.epoch_id)

    @property                       
    def output(self) -> Output:
        if not self.should_exist():
            raise ValueError(f"Node {self.config_hash()} of class {self.__class__.__name__} should not exist you should not be looking here")
        
        refreshed_input_fingerprint = self.recursive_input_fingerprint(current_only=False) # refresh input
        if self._output is None:
            self._output = self._outer_compute_output()
        else:
            while True:
                # keep recomputing until stabilized
                should_recompute = self._outer_should_recompute_output()
                if not should_recompute:
                    break
                else:
                    latest_output = self._outer_compute_output()
                    if self.recursive_input_fingerprint(current_only=True) != refreshed_input_fingerprint:
                        logging.warning(f"Input fingerprint changed during computation for node {self.config_hash()} of class {self.__class__.__name__}")
                        continue
                    else:
                        self._output.update(latest_output, refreshed_input_fingerprint)
                        self.set_status(ElementStatus.COMPLETED)
                        break

        return self._output


    def identity_key(self) -> str:
        return self._created_by_identity_key() + self.__class__.__name__ + self.config_hash()

    def _created_by_identity_key(self) -> str:
        return self.created_by.identity_key() if self.created_by else ""

    def _compute_output(self) -> Output:
        pass

    def _get_current_cache_key(self) -> str:
        return self.identity_key() + self.recursive_input_fingerprint(current_only=True).value

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
        self._put_in_cache(computed_output)
        return computed_output


    def recursive_input_fingerprint(self, current_only: bool = False) -> str:
        if self.input is None:
            return None
        else:
            return self.input.recursive_input_fingerprint(current_only=current_only)


    def recursive_output_fingerprint(self, current_only: bool = False) -> str:    
        if current_only:
            output_to_fingerprint = self._output
        else:
            output_to_fingerprint = self.output
        if output_to_fingerprint is None:
            return "NONE"
        else:
            return output_to_fingerprint.recursive_output_fingerprint(current_only=current_only)

    def current_recursive_output_fingerprint(self) -> str:
        return self._output.recursive_output_fingerprint(current_only=True)

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
          
    def _set_status_deleted(self) -> None:
        self._status = ElementStatus.DELETED
        output_to_delete = self._output
        for field_name, _ in output_to_delete.__class__.model_fields.items():
            value = getattr(output_to_delete, field_name)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, BaseGraphElement):
                        item._set_status_deleted()
            elif isinstance(value, BaseGraphElement):
                value._set_status_deleted()
        
    def _inner_should_recompute_output(self) -> bool:
        # TODO: implement this
        return False
    def _outer_should_recompute_output(self, refreshed_input_fingerprint: Fingerprint) -> bool:
        if self._inner_should_recompute_output():
            return True
        else:
            return self._output.input_epoch_dict != refreshed_input_fingerprint.epoch_dict
            

class BaseDataElement(BaseModel):
    def recursive_output_fingerprint(self) -> str:
        return str(self)



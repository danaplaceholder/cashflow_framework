from pydantic import BaseModel
from pydantic import PrivateAttr
from pydantic import Field
import logging
from enum import StrEnum
from cashflow.fingerprint import DataFingerprint, NodeFingerprint, InputFingerprint, OutputFingerprint
from abc import ABC, abstractmethod
from pprint import pprint
class GraphStateError(Exception):
    """
    Currently only raised when a DELETED Node is accessed
    """
    pass

class Collection(BaseModel, ABC):

    def recursive_output_fingerprint(self) -> InputFingerprint | OutputFingerprint:
        """
        Recurse inward into a node, taking the fingerprint of output at every level
        """
        field_fingerprint_dict = {}
        for field_name, _ in self.__class__.model_fields.items():
            value = getattr(self, field_name)
            if isinstance(value, list) :
                field_fingerprint_dict[field_name] = [item.recursive_output_fingerprint() for item in value]
            else:
                field_fingerprint_dict[field_name] = value.recursive_output_fingerprint()
        return self.__class__.make_fingerprint(field_fingerprint_dict=field_fingerprint_dict)
        
    @classmethod
    @abstractmethod
    def make_fingerprint(cls, field_fingerprint_dict: dict[str, DataFingerprint | NodeFingerprint | list[DataFingerprint | NodeFingerprint] | None]) -> InputFingerprint | OutputFingerprint:
        raise NotImplementedError("Subclasses must implement this method")

class Input(Collection):
        
        @classmethod
        def make_fingerprint(cls, field_fingerprint_dict: dict[str, DataFingerprint | NodeFingerprint | list[DataFingerprint | NodeFingerprint] | None]) -> InputFingerprint:
            return InputFingerprint(identity_key="some_input", field_fingerprint_dict=field_fingerprint_dict)
                    
        def update(self, new_input: 'BaseNode.Input') -> None:
            """
            Simpler than updating output. 
            We won't delete any nodes from the graph,
                we just make sure we are pointing to the correct nodes per identity keys
            """
            for field_name, _ in self.__class__.model_fields.items():
                old_input_value = getattr(self, field_name)
                new_input_value = getattr(new_input, field_name)

                if isinstance(old_input_value, list):
                    if len(old_input_value) and issubclass(old_input_value[0].__class__, BaseNode) or len(new_input_value) and issubclass(new_input_value[0].__class__, BaseNode):
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
                elif issubclass(old_input_value.__class__, BaseNode):
                    if old_input_value.identity_key() == new_input_value.identity_key():
                        # do nothing 
                        pass
                    else:
                        setattr(self, field_name, new_input_value)
                        

class Output(Collection):
        # tracks the input and external data_last_modified used to produce the output in its current state
        _upstream_data_fingerprint: NodeFingerprint = PrivateAttr(default=None)

        @property
        def upstream_data_fingerprint(self) -> NodeFingerprint:
            return self._upstream_data_fingerprint

        @classmethod
        def make_fingerprint(cls, field_fingerprint_dict: dict[str, DataFingerprint | NodeFingerprint | list[DataFingerprint | NodeFingerprint] | None]) -> OutputFingerprint:
            return OutputFingerprint(identity_key="some_output", field_fingerprint_dict=field_fingerprint_dict)
       
        def set_upstream_data_fingerprint(self, new_upstream_data_fingerprint: NodeFingerprint) -> None:
            if self._upstream_data_fingerprint is None:
                self._upstream_data_fingerprint = new_upstream_data_fingerprint
            else:
                self._upstream_data_fingerprint.update(new_upstream_data_fingerprint)

        def set_created_by(self, created_by: 'BaseNode') -> None:
            """
            Attach node creating this Output to every Node in the Output
            """
            for field_name, _ in self.__class__.model_fields.items():
                value = getattr(self, field_name)
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, BaseNode):
                            item.set_created_by(created_by)
                elif isinstance(value, BaseNode):
                    value.set_created_by(created_by)

        def contains(self, node: 'BaseNode') -> bool:
            """
            Supports sanity check/QA e.g. some_node.created_by.contains(some_node) should always be True, otherwise we are referring to a deleted Node
            """
            for field_name, _ in self.__class__.model_fields.items():
                value = getattr(self, field_name)
                if isinstance(value, list) and issubclass(value[0].__class__, BaseNode):
                    for item in value:
                        if item.identity_key() == node.identity_key():
                            return True
                elif issubclass(value.__class__, BaseNode):
                    if value.identity_key() == node.identity_key():
                        return True      
            return False

        def update(self, new_output: 'BaseNode.Output', new_upstream_data_fingerprint: NodeFingerprint) -> None:
            """
            (1) (UPDATE) make sure all Nodes in Output are pointing to the latest correct Nodes in their Input
            (2) DELETE Nodes that are no longer in Output. 
            (3) ADD new Nodes
            """
            if type(self) is not type(new_output):
                raise ValueError(f"new_output must be of type {type(self)}")
            for field_name, _ in self.__class__.model_fields.items():

                    old_value = getattr(self, field_name)
                    new_value = getattr(new_output, field_name)
                    if isinstance(old_value, list):
                        if len(old_value) and issubclass(old_value[0].__class__, BaseNode) or len(new_value) and issubclass(new_value[0].__class__, BaseNode):
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
                    elif issubclass(old_value.__class__, BaseNode):
                        if old_value.identity_key() == new_value.identity_key():
                          old_value.set_input(new_value.input)
                        else:
                            old_value.set_status_deleted()
                            setattr(self, field_name, new_value)
                    else:
                        setattr(self, field_name, new_value)
            self.set_upstream_data_fingerprint( new_upstream_data_fingerprint=new_upstream_data_fingerprint)



class ElementStatus(StrEnum):
    CREATED = "created"
    CHECKING_IF_SHOULD_EXIST = "checking_if_should_exist"
    CHECKING_IF_SHOULD_RECOMPUTE_OUTPUT = "checking_if_should_recompute_output"
    COMPUTING_OUTPUT = "computing_output"
    UPDATING_OUTPUT = "updating_output"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETED = "completed"
    DELETED = "deleted"
    STATIC = "static"

class BaseGraphElement(BaseModel, ABC):
    """
    Nodes and Data are BOTH BaseGraphElements with various methods for identifying and updating them
    """
    _created_by: 'BaseNode' = PrivateAttr(default=None)
    alias: str = ""
    @abstractmethod
    def identity_key(self) -> str:
        raise NotImplementedError("Subclasses must implement this method")
    

    @abstractmethod
    def recursive_output_fingerprint(self) -> DataFingerprint:
        raise NotImplementedError("Subclasses must implement this method")
        
    def set_created_by(self, created_by: 'BaseNode') -> None:
        self._created_by = created_by

    @property
    def created_by(self) -> 'BaseNode':
        return self._created_by

class BaseDataElement(BaseGraphElement):
    
    # Data has no input/output
    input: None = None
    output: None = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseDataElement):
            return False
        return self.data_hash() == other.data_hash()
    
    def identity_key(self) -> str:
        return "DATA_" + str(self)

    def data_hash(self) -> str:
        return self.identity_key() 
    
    def recursive_output_fingerprint(self) -> DataFingerprint:
        return DataFingerprint(
            identity_key=self.identity_key(), 
            data_hash=self.data_hash(),
        )
class BaseNode(BaseGraphElement):
    # TODO Caching layer ? 
    input: Input = Field(default=None)
    _output: Output = PrivateAttr(default=None)
    _upstream_data_fingerprint: NodeFingerprint = PrivateAttr(default=None)
    _fingerprint: NodeFingerprint = PrivateAttr(default=None)
    _status: ElementStatus = PrivateAttr(default=ElementStatus.CREATED)

    @property
    def fingerprint(self) -> NodeFingerprint:
        return self._fingerprint

    def recursive_output_fingerprint(self) -> DataFingerprint:
        item_output = self.output
        return NodeFingerprint(
            identity_key=self.identity_key(), 
            input_fingerprint=None,
            output_fingerprint=item_output.recursive_output_fingerprint() if item_output is not None else None,
            external_data_last_modified=None,
        )

    def upstream_data_fingerprint(self ) -> NodeFingerprint:
        """
        A node should recompute if its created_by, input, or external data has changed since last computation
        """
        #IMPORTANT: refresh created_by.output to make sure node is configured up-to-date with correct input etc. 
        if self.created_by is not None and not self.created_by.output.contains(self):
            raise GraphStateError(f"Node {self.created_by.identity_key()} of class {self.created_by.__class__.__name__} should not exist. This can happen if you specifically ask for a node that has been deleted but should not happen asynchronously.")

        return NodeFingerprint(
            identity_key=self.identity_key(),
            input_fingerprint=self.input.recursive_output_fingerprint() if self.input is not None else None,
            external_data_last_modified=self.get_external_data_last_modified(),
            output_fingerprint=None,
        )

    @abstractmethod
    def get_external_data_last_modified(self) -> int | None:
        raise NotImplementedError("Subclasses must implement this method")

    @property
    def root_node(self) -> 'BaseNode':
        if self.created_by is None:
            return self
        else:
            return self.created_by.root_node
    
    def set_status(self, status: ElementStatus) -> None:
        if self._status == status:
            return
        self._status = status
        # render the graph with the new status
        if status in [ElementStatus.CREATED, ElementStatus.COMPUTING_OUTPUT, ElementStatus.COMPLETED, ElementStatus.DELETED, ElementStatus.WAITING_FOR_INPUT, ElementStatus.CHECKING_IF_SHOULD_RECOMPUTE_OUTPUT]:
            from draw import build_graph
            build_graph(self.root_node)


    def element_name(self) -> str:
        return self.__class__.__name__ + "_" +  self.alias + "_STATUS_" + self._status.value
    
    @property                       
    def output(self) -> Output:
            """
            The engine of the graph. Checks if should recompute, updates the graph if so. 
            """     
            # refresh created by 
            latest_upstream_data_fingerprint = self.upstream_data_fingerprint()
            if self._output is None or self._outer_should_recompute_output(latest_upstream_data_fingerprint=latest_upstream_data_fingerprint):
                self._outer_compute_output(pre_compute_upstream_data_fingerprint=latest_upstream_data_fingerprint)

            return self._output

    def identity_key(self) -> str:
        return f"___{self.created_by_identity_key()}->{self.__class__.__name__}::{self.alias}|"

    def created_by_identity_key(self) -> str:
        return f"{self.created_by.identity_key()}" if self.created_by else ""

    def _compute_output(self) -> Output:
        raise NotImplementedError("Subclasses must implement this method")

    def _get_current_cache_key(self) -> str:
        return self.fingerprint.cache_key()

    def _get_from_cache(self) -> Output:
        # TODO: implement this
        pass

    def _put_in_cache(self, output: Output) -> None:
        # TODO: implement this
        pass


    def _outer_compute_output(self, pre_compute_upstream_data_fingerprint: NodeFingerprint) -> Output:
        # check if in cache
        cache_result = self._get_from_cache()
        if cache_result is not None:
            return cache_result
        
        # mark as computing output
        self.set_status(ElementStatus.COMPUTING_OUTPUT)

        # COMPUTE
        computed_output = self._compute_output()
        # IMPORTANT: attach self to all output nodes as .created_by
        computed_output.set_created_by(self) 

        # check if upstream data changed since computation
        post_compute_upstream_data_fingerprint = self.upstream_data_fingerprint()
        if pre_compute_upstream_data_fingerprint.upstream_data_modified(post_compute_upstream_data_fingerprint):
            logging.warning(f"Full upstream fingerprint changed after computation for {self.identity_key()}....recomputing")
            self._outer_compute_output(pre_compute_upstream_data_fingerprint=post_compute_upstream_data_fingerprint)
        
        else:
            self._put_in_cache(computed_output)

            if self._output is None:
                self._output = computed_output
                self._output.set_upstream_data_fingerprint(pre_compute_upstream_data_fingerprint)
            else:
                self._output.update(computed_output, new_upstream_data_fingerprint=pre_compute_upstream_data_fingerprint)

            # mark as completed
            self.set_status(ElementStatus.COMPLETED)

          
    def set_status_deleted(self) -> None:
        self._status = ElementStatus.DELETED
        output_to_delete = self._output
        for field_name, _ in output_to_delete.__class__.model_fields.items():
            value = getattr(output_to_delete, field_name)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, BaseNode):
                        item.set_status_deleted()
            elif isinstance(value, BaseNode):
                value.set_status_deleted()
        
    def _outer_should_recompute_output(self, latest_upstream_data_fingerprint: NodeFingerprint) -> bool:
        """
        Checks if the output should be recomputed based on the latest upstream data fingerprint.
        """
        if self._output is None:
            print(f"Should recompute output for {self.identity_key()} because output is None")
            return True
        else:
            diffs = self._output.upstream_data_fingerprint.underlying_upstream_data_diffs(latest_upstream_data_fingerprint)
            if diffs:
                pprint(f"\n \n Should recompute output for {self.identity_key()} because full upstream fingerprint changed")
                pprint( diffs)
                return True
            else:
                return False

    def set_input(self, new_input: 'BaseNode.Input') -> None:
        if self.input is None:
            self.input = new_input
        else:
            self.input.update(new_input)
        
    
class StaticOutputNode(BaseNode):
    """
    Useful for injecting "input" data into other Nodes. E.g. as pseudo-configs for nodes
    """
    def __init__(self, output: 'StaticOutputNode.Output', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._output = output
        self.set_status(ElementStatus.STATIC)

    @property
    def output(self) -> Output:
        if not self.created_by.output.contains(self):
            raise ValueError(f"Node {self.identity_key()} of class {self.__class__.__name__} should not exist. This can happen if you specifically ask for a node that has been deleted but should not happen asynchronously.")
        return self._output

    def _compute_output(self) -> Output:
        raise ValueError("StaticOutputNode should not be computed")

    def set_input(self, new_input: 'BaseNode.Input') -> None:
        if new_input is not None:
            raise ValueError("StaticOutputNode should not have input")
        return

    def get_external_data_last_modified(self) -> int | None:
        return None
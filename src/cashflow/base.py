from pydantic import BaseModel
from pydantic import PrivateAttr
from pydantic import Field
import time
import logging
from enum import StrEnum


class Fingerprint(BaseModel):
    identity_key: str = ""
    input_identity_keys: dict[str, 'Fingerprint | list[Fingerprint]'] | None
    created_by_fingerprint: 'Fingerprint | None'
    output_identity_keys: dict[str, 'Fingerprint | list[Fingerprint]'] | None

class GraphStateError(Exception):
    pass

class GraphElementCollection:

    @staticmethod
    def add_to_running_dict(running_dict: dict, key: str, value: dict | str | None ) -> None:
        new_fingerprint = Fingerprint(identity_key=key, key_value_dict=value)
        if key in running_dict:
            if running_dict[key] is not None:
                if running_dict[key] != new_fingerprint:
                    raise GraphStateError(f"Fingerprint changed for {key} from {running_dict[key]} to {new_fingerprint}")
            else:
                running_dict[key] = new_fingerprint
        else:
            running_dict[key] = new_fingerprint
        return running_dict

class Input(BaseModel, GraphElementCollection):

        def recursive_fingerprint(self ) -> dict[str, Fingerprint | list[Fingerprint]]:
            running_dict = {}
            for field_name, _ in self.__class__.model_fields.items():
                value = getattr(self, field_name)
                if isinstance(value, list) and len(value) and issubclass(value[0].__class__, BaseNode):
                    running_dict[field_name] = [Fingerprint(
                        identity_key=item.identity_key(), 
                        input_identity_keys=item.input.recursive_fingerprint() if item.input is not None else None,
                        created_by_fingerprint=item.created_by_fingerprint() if item.created_by is not None else None,
                        output_identity_keys=item.output.recursive_fingerprint() if item.output is not None else None,
                    ) for item in value]
            
                elif issubclass(value.__class__, BaseNode):
                    running_dict[field_name] = Fingerprint(
                        identity_key=value.identity_key(), 
                        input_identity_keys=value.input.recursive_fingerprint() if value.input is not None else None,
                        created_by_fingerprint=value.created_by_fingerprint() if value.created_by is not None else None,
                        output_identity_keys=value.output.recursive_fingerprint() if value.output is not None else None,
                    )
                else:
                    raise ValueError(f"Invalid type for {field_name}: {type(value)}")
                
            return running_dict
                    
        def update(self, new_input: 'BaseNode.Input') -> None:
            """
            Simpler than updating output. We won't delete any nodes we just make sure we are pointing to the correct nodes per identity keys
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

class Output(BaseModel, GraphElementCollection):
        _upstream_fingerprint: Fingerprint = PrivateAttr(default=None)

        def recursive_fingerprint(self ) -> dict[str, Fingerprint | list[Fingerprint]]:
            running_dict = {}
            for field_name, _ in self.__class__.model_fields.items():
                value = getattr(self, field_name)
                if isinstance(value, list) and len(value) and issubclass(value[0].__class__, BaseNode):
                    running_dict[field_name] = [Fingerprint(
                        identity_key=item.identity_key(), 
                        input_identity_keys=item.input.recursive_fingerprint() if item.input is not None else None,
                        created_by_fingerprint=item.created_by_fingerprint() if item.created_by is not None else None,
                        output_identity_keys=item.output.recursive_fingerprint() if item.output is not None else None,
                    ) for item in value]
                elif isinstance(value, list) and len(value) and issubclass(value[0].__class__, BaseDataElement):
                    running_dict[field_name] = [Fingerprint(
                        identity_key=item.identity_key(), 
                        input_identity_keys=None,
                        created_by_fingerprint=None,
                        output_identity_keys=None,
                    ) for item in value]
                elif issubclass(value.__class__, BaseNode):
                    running_dict[field_name] = Fingerprint(
                        identity_key=value.identity_key(), 
                        input_identity_keys=value.input.recursive_fingerprint() if value.input is not None else None,
                        created_by_fingerprint=value.created_by_fingerprint() if value.created_by is not None else None,
                        output_identity_keys=value.output.recursive_fingerprint() if value.output is not None else None,
                    )
                elif isinstance(value, BaseDataElement):
                    running_dict[field_name] = Fingerprint(
                        identity_key=value.identity_key(), 
                        input_identity_keys=None,
                        created_by_fingerprint=None,
                        output_identity_keys=None,
                    )
            return running_dict
        @property
        def input_fingerprint(self) -> Fingerprint:
            return self._upstream_fingerprint

        def set_upstream_fingerprint(self, input_fingerprint: Fingerprint) -> None:
            self._upstream_fingerprint = input_fingerprint

        def contains(self, node: 'BaseNode') -> bool:
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
        def update(self, new_output: 'BaseNode.Output', input_fingerprint: Fingerprint) -> None:
            if type(self) is not type(new_output):
                raise ValueError(f"new_output must be of type {type(self)}")
            self.set_upstream_fingerprint(input_fingerprint)
            for field_name, field_info in self.__class__.model_fields.items():

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



class ElementStatus(StrEnum):
    CREATED = "created"
    CHECKING_IF_SHOULD_EXIST = "checking_if_should_exist"
    CHECKING_IF_SHOULD_RECOMPUTE_OUTPUT = "checking_if_should_recompute_output"
    COMPUTING_OUTPUT = "computing_output"
    UPDATING_OUTPUT = "updating_output"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETED = "completed"
    DELETED = "deleted"

class GraphElementConfig(BaseModel):
        created_by: 'BaseNode' = None
        element_name: str = Field(default=None)
        def hash(self) -> str:
            return ''.join([field_name+str(getattr(self, field_name)) for field_name, field_info in self.__class__.model_fields.items() if getattr(self, field_name) is not None])

class BaseGraphElement(BaseModel):
    pass

class BaseDataElement(BaseGraphElement):

    input: None = None
    output: None = None
    
    def identity_key(self) -> str:
        return "DATA_" + str(self)
class BaseNode(BaseGraphElement):
    # TODO Caching layer ? 
    created_by: 'BaseNode' = None
    config: GraphElementConfig = Field(default=None)
    input: Input = Field(default=None)
    _output: Output = PrivateAttr(default=None)
    _fingerprint: Fingerprint = PrivateAttr(default=None)
    _status: ElementStatus = PrivateAttr(default=ElementStatus.CREATED)

    @property
    def fingerprint(self) -> Fingerprint:
        return self._fingerprint

    @property
    def root_node(self) -> 'BaseNode':
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
    

    def created_by_fingerprint(self) -> Fingerprint:
        if self.created_by is None:
            return None
        return Fingerprint(
            identity_key=self.created_by.identity_key(),
            input_identity_keys=self.created_by.input.recursive_fingerprint() if self.created_by.input is not None else None,
            created_by_fingerprint=self.created_by.created_by_fingerprint() if self.created_by.created_by is not None else None,
            output_identity_keys=None,
        )


    @property                       
    def output(self) -> Output:
        if not self.should_exist():
            raise ValueError(f"Node {self.config_hash()} of class {self.__class__.__name__} should not exist. This can happen if you specifically ask for a node that has been deleted but should not happen asynchronously.")
        else:
            latest_upstream_fingerprint = self.input.recursive_fingerprint() if self.input is not None else None
            if self._output is None:
                self._outer_compute_output(pre_compute_upstream_fingerprint=latest_upstream_fingerprint)
            else:
                if self._outer_should_recompute_output(latest_upstream_fingerprint=latest_upstream_fingerprint):
                    self._outer_compute_output(pre_compute_upstream_fingerprint=latest_upstream_fingerprint)
                
            return self._output

    def identity_key(self) -> str:
        return self.created_by_identity_key() + self.__class__.__name__ + self.config_hash()

    def created_by_identity_key(self) -> str:
        return self.created_by.identity_key() if self.created_by else ""

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


    def _outer_compute_output(self, pre_compute_upstream_fingerprint: Fingerprint) -> Output:
        # check if in cache
        cache_result = self._get_from_cache()
        if cache_result is not None:
            return cache_result
        
        # mark as computing output
        self.set_status(ElementStatus.COMPUTING_OUTPUT)

        computed_output = self._compute_output()
        post_compute_upstream_fingerprint = self.input.recursive_fingerprint() if self.input is not None else None
        
        if pre_compute_upstream_fingerprint != post_compute_upstream_fingerprint:
            logging.warning(f"Input fingerprints changed after computation for {self.identity_key()}....recomputing")
            self._outer_compute_output(pre_compute_upstream_fingerprint=post_compute_upstream_fingerprint)
        else:
            self._put_in_cache(computed_output)

            if self._output is None:
                self._output = computed_output
                self._output.set_upstream_fingerprint(pre_compute_upstream_fingerprint)
            else:
                self._output.update(computed_output, input_fingerprint=pre_compute_upstream_fingerprint)

            # mark as completed
            self.set_status(ElementStatus.COMPLETED)



    def check_all_upstream_node_versions_for_current_output(self) -> bool:
        """
        Walk up the input tree(s) for this node and check for multiple versions of the same node_x being used in the current _output of different paths
        Also make sure we really have kept track of the whole trail all along ..... 
        """

    

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
                    if isinstance(item, BaseNode):
                        item.set_status_deleted()
            elif isinstance(value, BaseNode):
                value.set_status_deleted()
        
    def _inner_should_recompute_output(self) -> bool:
        # TODO: implement this
        return False

    def _outer_should_recompute_output(self, latest_upstream_fingerprint: Fingerprint) -> bool:
        # TODO: implement this
        if self._inner_should_recompute_output():
            # useful for db access nodes that set _inner_compute_output to check on 'last_modified' in a db for example
            return True
        if self._output is None or self._output.input_fingerprint != latest_upstream_fingerprint:
            print(f"Should recompute output for {self.identity_key()} because input fingerprint changed from {self._output.input_fingerprint} to {latest_upstream_fingerprint}")
            return True
        else:
            return False

    def set_input(self, new_input: 'BaseNode.Input') -> None:
        if self.input is None:
            self.input = new_input
        else:
            self.input.update(new_input)

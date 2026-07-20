"""
Fingerprint for graph elements
    Written entirely by danaplaceholder
    NOT by ai
"""
from pydantic import PrivateAttr
from pydantic import BaseModel
 

class GraphElementFingerprint(BaseModel):
    identity_key: str
    _version: int = PrivateAttr(default=0)

    def _bump_version(self) -> None:
        self._version += 1

    @property
    def version(self) -> int:
        return self._version

    def update(self, new_fingerprint: 'GraphElementFingerprint') -> None:
        self._inner_update(new_fingerprint)
        self._bump_version()

    def _inner_compare(self, new_fingerprint: 'GraphElementFingerprint') -> None:
        raise NotImplementedError("Subclasses must implement this method")

    def _inner_update(self, new_fingerprint: 'GraphElementFingerprint') -> None:
        raise NotImplementedError("Subclasses must implement this method")


    


class CollectionFingerprint(GraphElementFingerprint):
    def _inner_update(self, new_fingerprint: 'OutputFingerprint') -> None:
        """
        Recurse through nested field_fingerprint_dict for Input/Output instances of a Node
        Supports version-tracting/incrementing of Fingerprint objects inside the field_fingerprint_dict, instead of just replacing them. 
        """
        for field_name in self.field_fingerprint_dict.keys():
            old_value = self.field_fingerprint_dict.get(field_name)
            new_value = new_fingerprint.field_fingerprint_dict.get(field_name)
            if old_value == new_value:
                continue
            elif old_value is None or new_value is None:
                self.field_fingerprint_dict[field_name] = new_value
            elif isinstance(old_value, list):  # handles both DataFingerprint and NodeFingerprint
                updated_list = []
                old_identity_key_dict = { node_fingerprint.identity_key: node_fingerprint for node_fingerprint in old_value }
                new_identity_key_dict = { node_fingerprint.identity_key: node_fingerprint for node_fingerprint in new_value }
                for identity_key, old_node_fingerprint in old_identity_key_dict.items():
                    if identity_key not in new_identity_key_dict:
                        continue
                    elif new_identity_key_dict[identity_key] != old_node_fingerprint:
                        old_node_fingerprint.update(new_identity_key_dict[identity_key])
                        updated_list.append(old_node_fingerprint)
                    else:
                        updated_list.append(old_node_fingerprint)
                for identity_key, new_node_fingerprint in new_identity_key_dict.items():
                    if identity_key not in old_identity_key_dict:
                        updated_list.append(new_node_fingerprint)
                    else:
                        continue
                self.field_fingerprint_dict[field_name] = updated_list
            elif old_value != new_value:
                self.field_fingerprint_dict[field_name].update(new_value)
    def _inner_compare(self,  new_fingerprint: 'GraphElementFingerprint', ignore_external_data_last_modified: bool) -> list:
        """
        Could be replaced with a "dry-run" version of _inner_update..... 
        """
        diffs = {}
        for field_name in self.field_fingerprint_dict.keys():
            field_diffs = []
            old_value = self.field_fingerprint_dict.get(field_name)
            new_value = new_fingerprint.field_fingerprint_dict.get(field_name)
            if old_value == new_value:
                continue
            elif old_value is None or new_value is None:
                field_diffs.append((field_name, old_value, new_value))
            elif isinstance(old_value, list):
                old_identity_key_dict = { node_fingerprint.identity_key: node_fingerprint for node_fingerprint in old_value }
                new_identity_key_dict = { node_fingerprint.identity_key: node_fingerprint for node_fingerprint in new_value }
                for identity_key, old_node_fingerprint in old_identity_key_dict.items():
                    if identity_key not in new_identity_key_dict:
                        field_diffs.append({identity_key: "REFERENCE_REMOVED"})
                    else:
                        new_diffs = old_node_fingerprint._inner_compare(new_identity_key_dict[identity_key], ignore_external_data_last_modified=ignore_external_data_last_modified)
                        if new_diffs:
                            field_diffs.append(new_diffs) 
                    
                for identity_key, _ in new_identity_key_dict.items():
                    if identity_key not in old_identity_key_dict:
                        field_diffs.append({identity_key: "REFERENCE_ADDED"}) 
            else:
                old_value = self.field_fingerprint_dict.get(field_name)
                new_value = new_fingerprint.field_fingerprint_dict.get(field_name)
                if old_value.identity_key != new_value.identity_key:
                    field_diffs.append({"REFERENCED_CHANGED: FROM": old_value.identity_key, "TO": new_value.identity_key})
                else:
                    new_diffs = old_value._inner_compare(new_value, ignore_external_data_last_modified=ignore_external_data_last_modified)
                    if new_diffs:
                        field_diffs.append(new_diffs)
            if field_diffs:
                diffs[field_name] = field_diffs 
        return diffs
            

class DataFingerprint(GraphElementFingerprint):
    data_hash: str

    def _inner_update(self, new_fingerprint: 'DataFingerprint') -> None:
        if self.data_hash != new_fingerprint.data_hash:
            self.data_hash = new_fingerprint.data_hash
    def _inner_compare(self, new_fingerprint: 'DataFingerprint', ignore_external_data_last_modified: bool) -> None:
        if self.data_hash != new_fingerprint.data_hash:
            return [{"OLD_DATA_HASH": self.data_hash, "NEW_DATA_HASH": new_fingerprint.data_hash}]
        return None

class OutputFingerprint(CollectionFingerprint):
    field_fingerprint_dict: 'dict[str, DataFingerprint | NodeFingerprint | list[DataFingerprint | NodeFingerprint]]'  
class InputFingerprint(CollectionFingerprint):
    field_fingerprint_dict: 'dict[str,  NodeFingerprint | list[  NodeFingerprint]]' 

class NodeFingerprint(GraphElementFingerprint):
    identity_key: str
    input_fingerprint: InputFingerprint | None = None
    output_fingerprint: OutputFingerprint | None = None
    external_data_last_modified: int | None = None

    def _inner_update(self, new_fingerprint: 'NodeFingerprint') -> None:
        if self.input_fingerprint is None:
            self.input_fingerprint = new_fingerprint.input_fingerprint
        elif new_fingerprint.input_fingerprint is not None:
            self.input_fingerprint.update(new_fingerprint.input_fingerprint)
        if self.output_fingerprint is None:
            self.output_fingerprint = new_fingerprint.output_fingerprint
        elif new_fingerprint.output_fingerprint is not None:
            self.output_fingerprint.update(new_fingerprint.output_fingerprint)
        if self.external_data_last_modified != new_fingerprint.external_data_last_modified:
            self.external_data_last_modified = new_fingerprint.external_data_last_modified
    
    def _inner_compare(self, new_fingerprint: 'NodeFingerprint', ignore_external_data_last_modified: bool) -> dict[str, list[str]] | None:
        input_diffs = self.input_fingerprint._inner_compare(new_fingerprint.input_fingerprint, ignore_external_data_last_modified=ignore_external_data_last_modified) if self.input_fingerprint is not None else None
        output_diffs = self.output_fingerprint._inner_compare(new_fingerprint.output_fingerprint, ignore_external_data_last_modified=ignore_external_data_last_modified) if self.output_fingerprint is not None else None
        if not ignore_external_data_last_modified:
            external_data_last_modified_diffs = (self.external_data_last_modified, new_fingerprint.external_data_last_modified) if self.external_data_last_modified != new_fingerprint.external_data_last_modified else None
        else:
            external_data_last_modified_diffs = None
        if input_diffs or external_data_last_modified_diffs:
            return {
                "identity_key": self.identity_key,
                "input_diffs": input_diffs,
                "external_data_last_modified_diffs": external_data_last_modified_diffs
            }
        elif output_diffs:
            return {
                "identity_key": self.identity_key,
                "output_diffs": output_diffs,
            }
        return None

    def upstream_data_modified(self, other: 'NodeFingerprint') -> bool:
        """
        Check if any external_data_last_modified has changed anywhere in the upstream input chain
        """
        if self.input_fingerprint is not None:
            if self.input_fingerprint._inner_compare(other.input_fingerprint, ignore_external_data_last_modified=False):
                return True
        if self.external_data_last_modified != other.external_data_last_modified:
                return True
        return False
    
    def underlying_upstream_data_diffs(self, other: 'NodeFingerprint') -> dict[str, list[str]] | None:
        """
        Get diffs between the current _output's 
            (1) input fingerprint, IGNORING temporary data changes/oscillations, i.e. is the output valid for the CURRENT UNDERLYING input data
            (2) external data last_modified
        
        Diffs will be present and should recompute output if 
           (1) input data no longer matches underlying data portion of _output fingerprint 
             OR
           (2) external data has been modified since _output was last set 
        """
        diffs = []
        if self.input_fingerprint is not None:
            input_diffs = self.input_fingerprint._inner_compare(other.input_fingerprint, ignore_external_data_last_modified=True)
            if input_diffs:
                diffs.append(input_diffs)
        if self.external_data_last_modified != other.external_data_last_modified:
            diffs.append(({"last_modified": {"OLD": self.external_data_last_modified, "NEW": other.external_data_last_modified}}))
        
        if len(diffs) > 0:
            return diffs
        else:
            return None


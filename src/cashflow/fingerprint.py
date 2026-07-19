"""
fingerprint for graph elements
by Dana K
NOT by ai
"""
from pydantic import PrivateAttr
from pydantic import BaseModel
from datetime import datetime

class Version(BaseModel):
    _version_number: int = PrivateAttr(default=0)
    _timestamp: datetime = PrivateAttr(default=datetime.now())

    @property
    def version_number(self) -> int:
        return self._version_number + 1

    @property
    def timestamp(self) -> datetime:
        return self._timestamp

    def bump_version(self) -> None:
        self._version_number += 1
        self._timestamp = datetime.now()

class GraphElementFingerprint(BaseModel):
    identity_key: str
    _version: Version = PrivateAttr(default=Version())

    def _bump_version(self) -> None:
        self._version.bump_version()

    @property
    def version(self) -> int:
        return self._version

    def update(self, new_fingerprint: 'GraphElementFingerprint') -> None:
        self._inner_update(new_fingerprint)
        self._bump_version()

    def _inner_update(self, new_fingerprint: 'GraphElementFingerprint') -> None:
        raise NotImplementedError("Subclasses must implement this method")

    def underlying_data_match( self, other: 'GraphElementFingerprint') -> bool:
        """
        Returns True if the underlying data of the two fingerprints match, potential temporary data changes
        """
        return self.identity_key == other.identity_key and not self._inner_compare(other, ignore_external_data_last_modified=True) 
        


class CollectionFingerprint(GraphElementFingerprint):
    def _inner_update(self, new_fingerprint: 'OutputFingerprint') -> None:
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
                        continue
            else:
                old_value = self.field_fingerprint_dict.get(field_name)
                new_value = new_fingerprint.field_fingerprint_dict.get(field_name)
                if old_value.identity_key != new_value.identity_key:
                    field_diffs.append({"REFERENCED_CHANGED: FROM": old_value.identity_key, "TO": new_value.identity_key})
                else:
                    new_diffs = old_value._inner_compare(new_value, ignore_external_data_last_modified=ignore_external_data_last_modified)
                    if new_diffs:
                        field_diffs.append(new_diffs)
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
        return []

class OutputFingerprint(CollectionFingerprint):
    field_fingerprint_dict: 'dict[str, DataFingerprint | NodeFingerprint | list[DataFingerprint | NodeFingerprint]]'  
class InputFingerprint(CollectionFingerprint):
    field_fingerprint_dict: 'dict[str,  NodeFingerprint | list[  NodeFingerprint]]' 

class NodeFingerprint(GraphElementFingerprint):
    identity_key: str
    input_fingerprint: InputFingerprint | None = None
    output_fingerprint: OutputFingerprint | None = None
    external_data_last_modified: int | None = None
    created_by_fingerprint: 'NodeFingerprint | None' = None

    def _inner_update(self, new_fingerprint: 'NodeFingerprint') -> None:
        if not self.input_fingerprint.underlying_data_match(new_fingerprint.input_fingerprint):
            self.input_fingerprint.update(new_fingerprint.input_fingerprint)
        if not self.output_fingerprint.underlying_data_match(new_fingerprint.output_fingerprint):
            self.output_fingerprint.update(new_fingerprint.output_fingerprint)
        if not self.created_by_fingerprint.underlying_data_match(new_fingerprint.created_by_fingerprint):
            self.created_by_fingerprint.update(new_fingerprint.created_by_fingerprint)
        if self.external_data_last_modified != new_fingerprint.external_data_last_modified:
            self.external_data_last_modified = new_fingerprint.external_data_last_modified
    def _inner_compare(self, new_fingerprint: 'NodeFingerprint', ignore_external_data_last_modified: bool) -> dict[str, list[str]] | None:
        input_diffs = self.input_fingerprint._inner_compare(new_fingerprint.input_fingerprint, ignore_external_data_last_modified=ignore_external_data_last_modified) if self.input_fingerprint is not None else None
        output_diffs = self.output_fingerprint._inner_compare(new_fingerprint.output_fingerprint, ignore_external_data_last_modified=ignore_external_data_last_modified) if self.output_fingerprint is not None else None
        created_by_diffs = self.created_by_fingerprint._inner_compare(new_fingerprint.created_by_fingerprint, ignore_external_data_last_modified=ignore_external_data_last_modified) if self.created_by_fingerprint is not None else None
        if not ignore_external_data_last_modified:
            external_data_last_modified_diffs = (self.external_data_last_modified, new_fingerprint.external_data_last_modified) if self.external_data_last_modified != new_fingerprint.external_data_last_modified else None
        else:
            external_data_last_modified_diffs = None
        if input_diffs or created_by_diffs or external_data_last_modified_diffs:
            return {
                "identity_key": self.identity_key,
                "input_diffs": input_diffs,
                "created_by_diffs": created_by_diffs,
                "external_data_last_modified_diffs": external_data_last_modified_diffs
            }
        elif output_diffs:
            return {
                "identity_key": self.identity_key,
                "output_diffs": output_diffs,
            }
        return None


class FullUpstreamFingerprint(BaseModel):
        input_fingerprint: InputFingerprint | None = None
        external_data_last_modified: int | None = None
    
        def has_been_modified(self, other: 'FullUpstreamFingerprint') -> bool:
            if self.input_fingerprint is not None:
                if self.input_fingerprint._inner_compare(other.input_fingerprint, ignore_external_data_last_modified=False):
                    return True
            if self.external_data_last_modified != other.external_data_last_modified:
                    return True
            return False
      
        def get_diffs(self, other: 'FullUpstreamFingerprint') -> dict[str, list[str]] | None:
            diffs = []
            if self.input_fingerprint is not None:
                diffs.append(self.input_fingerprint._inner_compare(other.input_fingerprint, ignore_external_data_last_modified=True))
            if self.external_data_last_modified != other.external_data_last_modified:
                diffs.append((self.external_data_last_modified, other.external_data_last_modified))
            return diffs

        def underlying_data_match(self, other: 'FullUpstreamFingerprint') -> bool:
            """
            Ignores external data last modified changes
            """
            if self.input_fingerprint is not None:
                if not self.input_fingerprint.underlying_data_match(other.input_fingerprint):
                    return False
            elif self.external_data_last_modified != other.external_data_last_modified:
                """
                If the node itself uses external data that has since been modified, then the underlying data could possibly not match
                """
                return False
            return True
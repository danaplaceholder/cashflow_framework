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

    def __eq__( self, other: 'GraphElementFingerprint') -> bool:
        return self.identity_key == other.identity_key and not self._inner_compare(other) 
        

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
    def _inner_compare(self,  new_fingerprint: 'GraphElementFingerprint') -> None:
        diffs = []
        for field_name in self.field_fingerprint_dict.keys():
            old_value = self.field_fingerprint_dict.get(field_name)
            new_value = new_fingerprint.field_fingerprint_dict.get(field_name)
            if old_value == new_value:
                continue
            elif old_value is None or new_value is None:
                diffs.append((field_name, old_value, new_value))
            elif isinstance(old_value, list):
                old_identity_key_dict = { node_fingerprint.identity_key: node_fingerprint for node_fingerprint in old_value }
                new_identity_key_dict = { node_fingerprint.identity_key: node_fingerprint for node_fingerprint in new_value }
                for identity_key, old_node_fingerprint in old_identity_key_dict.items():
                    if identity_key not in new_identity_key_dict:
                        diffs.append((f"{self.identity_key}:{field_name} - {identity_key}:Node deleted"))
                    elif new_identity_key_dict[identity_key] != old_node_fingerprint:
                        diffs.append(old_node_fingerprint._inner_compare(new_identity_key_dict[identity_key]))
                    else:
                        continue
                for identity_key, new_node_fingerprint in new_identity_key_dict.items():
                    if identity_key not in old_identity_key_dict:
                        diffs.append((f"{self.identity_key}:{field_name} - {identity_key}:Node added"))
                    else:
                        continue
            elif old_value != new_value:
                diffs.append(old_value._inner_compare(new_value))
        return diffs


            

class DataFingerprint(GraphElementFingerprint):
    data_hash: str

    def _inner_update(self, new_fingerprint: 'DataFingerprint') -> None:
        if self.data_hash != new_fingerprint.data_hash:
            self.data_hash = new_fingerprint.data_hash
    def _inner_compare(self, new_fingerprint: 'DataFingerprint') -> None:
        if self.data_hash != new_fingerprint.data_hash:
            return [(self.data_hash, new_fingerprint.data_hash)]
        return []

class OutputFingerprint(CollectionFingerprint):
    field_fingerprint_dict: 'dict[str, DataFingerprint | NodeFingerprint | list[DataFingerprint | NodeFingerprint]]'  
class InputFingerprint(CollectionFingerprint):
    field_fingerprint_dict: 'dict[str,  NodeFingerprint | list[  NodeFingerprint]]' 

class NodeFingerprint(GraphElementFingerprint):
    identity_key: str
    input_fingerprint: InputFingerprint | None = None
    output_fingerprint: OutputFingerprint | None = None
    created_by_fingerprint: 'NodeFingerprint | None' = None

    def _inner_update(self, new_fingerprint: 'NodeFingerprint') -> None:
        if self.input_fingerprint != new_fingerprint.input_fingerprint:
            self.input_fingerprint.update(new_fingerprint.input_fingerprint)
        if self.output_fingerprint != new_fingerprint.output_fingerprint:
            self.output_fingerprint.update(new_fingerprint.output_fingerprint)
        if self.created_by_fingerprint != new_fingerprint.created_by_fingerprint:
            self.created_by_fingerprint.update(new_fingerprint.created_by_fingerprint)

    def _inner_compare(self, new_fingerprint: 'NodeFingerprint') -> dict[str, list[str]] | None:
        input_diffs = self.input_fingerprint._inner_compare(new_fingerprint.input_fingerprint) if self.input_fingerprint is not None else None
        output_diffs = self.output_fingerprint._inner_compare(new_fingerprint.output_fingerprint) if self.output_fingerprint is not None else None
        created_by_diffs = self.created_by_fingerprint._inner_compare(new_fingerprint.created_by_fingerprint) if self.created_by_fingerprint is not None else None
        if input_diffs or output_diffs or created_by_diffs:
            return {
                "identity_key": self.identity_key,
                "input_diffs": input_diffs,
                "output_diffs": output_diffs,
                "created_by_diffs": created_by_diffs
            }
        return None


class FullUpstreamFingerprint(BaseModel):
        input_fingerprint: InputFingerprint | None = None
        external_data_last_modified: int | None = None
        created_by_fingerprint: NodeFingerprint | None = None

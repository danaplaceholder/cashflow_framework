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

    def bump_version(self) -> None:
        self._version.bump_version()

    @property
    def version(self) -> int:
        return self._version

    def update(self, new_fingerprint: 'GraphElementFingerprint') -> None:
        self._inner_update(new_fingerprint)
        self.bump_version()

    def _inner_update(self, new_fingerprint: 'GraphElementFingerprint') -> None:
        raise NotImplementedError("Subclasses must implement this method")
        

class CollectionFingerprint(GraphElementFingerprint):
    def _inner_update(self, new_fingerprint: 'OutputFingerprint') -> None:
        for field_name in self.__class__.field_names:
            old_value = self.field_fingerprint_dict.get(field_name)
            new_value = new_fingerprint.field_fingerprint_dict.get(field_name)
            if old_value == new_value:
                continue
            elif old_value is None or new_value is None:
                self.field_fingerprint_dict[field_name] = new_value
            elif isinstance(old_value, list):  # handles both DataFingerprint and NodeFingerprint
                old_identity_key_dict = { node_fingerprint.identity_key: node_fingerprint for node_fingerprint in old_value }
                new_identity_key_dict = { node_fingerprint.identity_key: node_fingerprint for node_fingerprint in new_value }
                for identity_key, old_node_fingerprint in old_identity_key_dict.items():
                    if identity_key not in new_identity_key_dict:
                        del self.field_fingerprint_dict[field_name][old_node_fingerprint]
                    elif new_identity_key_dict[identity_key] != old_node_fingerprint:
                        old_node_fingerprint.update(new_identity_key_dict[identity_key])
                    else:
                        continue
                for identity_key, new_node_fingerprint in new_identity_key_dict.items():
                    if identity_key not in old_identity_key_dict:
                        self.field_fingerprint_dict[field_name].append(new_node_fingerprint)
                    else:
                        continue
            elif old_value != new_value:
                old_value.update(new_value)
    def _inner_compare(self,  new_fingerprint: 'GraphElementFingerprint') -> None:
        diffs = []
        for field_name in self.__class__.field_names:
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
                        diffs.append((f"{self.identity_key}:{field_name} - {identity_key}:Node updated"))
                    else:
                        continue
                for identity_key, new_node_fingerprint in new_identity_key_dict.items():
                    if identity_key not in old_identity_key_dict:
                        diffs.append((f"{self.identity_key}:{field_name} - {identity_key}:Node added"))
                    else:
                        continue
            elif old_value != new_value:
                diffs.append((f"{self.identity_key}:{field_name} - {old_value.identity_key}: updated to {new_value.identity_key}"))
        return diffs
            

class DataFingerprint(GraphElementFingerprint):
    data_hash: str

    def _inner_update(self, new_fingerprint: 'DataFingerprint') -> None:
        if self.data_hash != new_fingerprint.data_hash:
            self.data_hash = new_fingerprint.data_hash
    def _inner_compare(self, old_fingerprint: 'DataFingerprint', new_fingerprint: 'DataFingerprint') -> None:
        if old_fingerprint.data_hash != new_fingerprint.data_hash:
            return [(self.data_hash, old_fingerprint.data_hash, new_fingerprint.data_hash)]
        return []

class OutputFingerprint(CollectionFingerprint):
    field_fingerprint_dict: dict[str, DataFingerprint | NodeFingerprint | list[DataFingerprint | NodeFingerprint]]
  
class InputFingerprint(CollectionFingerprint):
    field_fingerprint_dict: dict[str,  NodeFingerprint | list[  NodeFingerprint]]

class NodeFingerprint(GraphElementFingerprint):
    identity_key: str
    input_fingerprint: InputFingerprint | None = None
    output_fingerprint: OutputFingerprint  
    created_by_fingerprint: NodeFingerprint | None = None

    def _inner_update(self, new_fingerprint: 'NodeFingerprint') -> None:
        if self.input_fingerprint != new_fingerprint.input_fingerprint:
            self.input_fingerprint.update(new_fingerprint.input_fingerprint)
        if self.output_fingerprint != new_fingerprint.output_fingerprint:
            self.output_fingerprint.update(new_fingerprint.output_fingerprint)
        if self.created_by_fingerprint != new_fingerprint.created_by_fingerprint:
            self.created_by_fingerprint.update(new_fingerprint.created_by_fingerprint)

    def _inner_compare(self, new_fingerprint: 'NodeFingerprint') -> dict[str, list[str]] | None:
        input_diffs = self.input_fingerprint._inner_compare(new_fingerprint.input_fingerprint)
        output_diffs = self.output_fingerprint._inner_compare(new_fingerprint.output_fingerprint)
        created_by_diffs = self.created_by_fingerprint._inner_compare(new_fingerprint.created_by_fingerprint)
        if input_diffs or output_diffs or created_by_diffs:
            return {
                "identity_key": self.identity_key,
                "input_diffs": input_diffs,
                "output_diffs": output_diffs,
                "created_by_diffs": created_by_diffs
            }
        return None
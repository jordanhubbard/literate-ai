"""Observe the operator's current revocation set for each SDK authorization check."""

import json
from pathlib import Path
from threading import Lock

from literate_ai.projects import PinnedInputClosure
from literate_ai.security import AuthorizationRevocationSet


def _unique_fields(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate SDK revocation field")
        result[key] = value
    return result


class SdkRevocationFile:
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.is_absolute() or ".." in self.path.parts:
            raise ValueError("SDK revocation authority requires an absolute path")
        self._seen = {}
        self._lock = Lock()
        self._last_observation = None

    def __call__(self):
        with self._lock:
            pins = PinnedInputClosure(
                maximum_files=1,
                maximum_file_bytes=4 * 1024**2,
                maximum_total_bytes=4 * 1024**2,
            )
            content = pins.pin(
                self.path, boundary=self.path.parent, label="SDK revocations"
            )
            state = AuthorizationRevocationSet.from_dict(
                json.loads(content, object_pairs_hook=_unique_fields)
            )
            current = {entry.authorization_id: entry for entry in state.entries}
            if any(current.get(key) != value for key, value in self._seen.items()):
                raise ValueError(
                    "Previously observed SDK revocation disappeared or changed"
                )
            pins.require_unchanged()
            self._seen = current
            self._last_observation = pins
            return state

    def original_observation(self):
        with self._lock:
            if self._last_observation is None:
                raise ValueError("SDK revocation file has not been observed")
            return self._last_observation

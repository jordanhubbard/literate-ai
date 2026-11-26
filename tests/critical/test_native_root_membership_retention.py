"""Historical typed membership retention, no accepted native-run claim."""

import os
import unittest
from dataclasses import replace

from literate_ai.adapters.qualification_capture import (
    QualificationEvidenceReader,
    reopen_qualification_node,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from tests.critical import test_native_root_preparation_retention as fixture


@unittest.skipUnless(os.name == "posix", "original binding/physical CAS fixture")
class NativeRootMembershipRetentionTests(unittest.TestCase):
    setUp = fixture.NativeRootPreparationRetentionTests.setUp
    observe = fixture.NativeRootPreparationRetentionTests.observe
    metadata = fixture.NativeRootPreparationRetentionTests.metadata
    library_current = fixture.NativeRootPreparationRetentionTests.library_current
    native_protocol = fixture.NativeRootPreparationRetentionTests.native_protocol
    opened = fixture.NativeRootPreparationRetentionTests.opened
    controller = fixture.NativeRootPreparationRetentionTests.controller
    modeled_registered_candidate = (
        fixture.NativeRootPreparationRetentionTests.modeled_registered_candidate
    )

    def test_prepublication_membership_stays_readable_after_distinct_later_member(self):
        with self.modeled_registered_candidate():
            node = self.modeled_node
            original = node.identity_document()
            membership = node.source_cache_membership
            # A different later standalone member is data only. No final
            # acceptance/root/run is fabricated by this retention control.
            later = replace(
                membership,
                acceptance_identity=canonical_identity({"modeled-later-acceptance": 1}),
            )
            self.assertNotEqual(later.identity, membership.identity)
            with self.controller() as (scope, _sequence, controller):
                controller._retain_node(node)
                scope.retain_record(later)
                content = canonical_json_bytes(membership.to_dict())
                self.assertEqual(
                    scope._evidence.get_bytes(
                        BlobRef(membership.identity.digest, len(content))
                    ),
                    content,
                )
                reader = QualificationEvidenceReader(
                    self.recorder.entries, max_bytes=16 * 1024**2, max_records=2000
                )
                reopened = reopen_qualification_node(reader, node.identity)
                self.assertEqual(reopened.source_cache_membership, membership)
                self.assertEqual(reader.read_json(later.identity), later.to_dict())
                self.assertEqual(node.identity_document(), original)

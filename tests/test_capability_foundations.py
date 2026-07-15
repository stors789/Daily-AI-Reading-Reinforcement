from __future__ import annotations

import sys
import unittest
from pathlib import Path


CORE_SRC = Path(__file__).resolve().parent.parent / "packages" / "dairr_core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from dairr_core.capabilities import (
    Capability,
    CapabilityId,
    CapabilityReason,
    CapabilitySet,
    CapabilityStatus,
    Provenance,
)


class CapabilityFoundationTests(unittest.TestCase):
    def test_available_capability_round_trips(self) -> None:
        capabilities = CapabilitySet([
            Capability(
                CapabilityId.PASTED_TEXT_PRACTICE,
                CapabilityStatus.AVAILABLE,
                provenance=Provenance.SHARED_CORE,
            ),
            Capability(
                CapabilityId.FSRS_VALUES,
                CapabilityStatus.DATA_ABSENT,
                CapabilityReason.FSRS_NOT_AVAILABLE,
                Provenance.ANKICONNECT_STANDARD,
                "The selected cards did not expose FSRS fields.",
            ),
        ])
        restored = CapabilitySet.from_dict(capabilities.to_dict())
        self.assertTrue(restored.is_available(CapabilityId.PASTED_TEXT_PRACTICE))
        fsrs = restored.get(CapabilityId.FSRS_VALUES)
        self.assertFalse(fsrs.available)
        self.assertEqual(fsrs.reason, CapabilityReason.FSRS_NOT_AVAILABLE)
        self.assertEqual(fsrs.provenance, Provenance.ANKICONNECT_STANDARD)

    def test_status_and_reason_must_be_consistent(self) -> None:
        with self.assertRaises(ValueError):
            Capability(
                CapabilityId.CANCELLATION,
                CapabilityStatus.AVAILABLE,
                CapabilityReason.PROVIDER_LIMITATION,
            )
        with self.assertRaises(ValueError):
            Capability(
                CapabilityId.CANCELLATION,
                CapabilityStatus.PROVIDER_UNSUPPORTED,
            )

    def test_duplicate_and_undeclared_capabilities_are_not_silent(self) -> None:
        row = Capability(
            CapabilityId.ARTICLE_HISTORY,
            CapabilityStatus.AVAILABLE,
        )
        with self.assertRaises(ValueError):
            CapabilitySet([row, row])
        with self.assertRaises(KeyError):
            CapabilitySet().get(CapabilityId.ARTICLE_HISTORY)


if __name__ == "__main__":
    unittest.main()

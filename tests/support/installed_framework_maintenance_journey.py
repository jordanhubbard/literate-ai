"""Installed maintenance planning after real framework producer transitions.

Exercise the public root and descendant commands before the inherited journey
restores its original native/Git state. Preserve a failed finalized fixture for
inspection; historical initialization records are never rewritten by this test.
"""

from __future__ import annotations

from tests.support import installed_framework_producer_journey as producer
from tests.support import installed_native_adoption_journey as adoption


class InstalledFrameworkMaintenanceJourney(producer.InstalledFrameworkProducerJourney):
    def after_framework_apply(self, project, launcher, plan):
        super().after_framework_apply(project, launcher, plan)
        source = project / "components/legacy-project-wrapper/implementation"
        snapshot = adoption.InstalledNativeAdoptionJourney.snapshot
        before = snapshot(source)
        index = (project / ".git/index").read_bytes()
        failures = []
        reparent_identity = None
        for coordinate, selected in (
            ("root", project),
            ("descendant", project / "litai/components"),
        ):
            for operation in ("reparent", "update"):
                label = f"framework-maintenance-{operation}-{coordinate}"
                arguments = (
                    ("reparent", "none", "--project", str(selected))
                    if operation == "reparent"
                    else ("update", str(selected))
                )
                try:
                    result = self.cli(label, launcher, *arguments, cwd=self.root)[
                        "result"
                    ]
                    self.assertEqual(result["mode"], "read-only-plan", result)
                    if operation == "reparent":
                        if reparent_identity is None:
                            reparent_identity = result["identity"]
                        else:
                            self.assertEqual(result["identity"], reparent_identity)
                except AssertionError as error:
                    # Collect independent read-only command outcomes once, then
                    # retain this exact finalized fixture if any command fails.
                    failures.append(f"{label}: {error}")
                self.assertEqual(snapshot(source), before)
                self.assertEqual((project / ".git/index").read_bytes(), index)
        self.assertFalse(failures, "\n".join(failures))

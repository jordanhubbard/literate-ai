"""Installed original Component renewal, finalization and exact recovery.

The immutable installed wheel owns every public CLI operation. The inherited
journey retains the real initialization, framework placement and source/Git
preservation assertions. This does not qualify full project containment.
"""

from __future__ import annotations

import json

from tests.support import installed_framework_layout_journey as placement


class InstalledFrameworkProducerJourney(placement.InstalledFrameworkLayoutJourney):
    def after_framework_apply(self, project, launcher, plan):
        component = "litai/components/legacy-project-wrapper"
        lock = json.loads((project / component / "component.lock.json").read_bytes())
        common = (
            "--project",
            str(project / "litai/components"),
            "--place-framework-authority",
            "--plan-identity",
            plan["plan_identity"],
            "--acknowledge",
        )
        renewed = self.cli(
            "framework-producer-renew",
            launcher,
            "project",
            "layout",
            "renew",
            *common,
            "--component",
            component,
            "--target",
            lock["target_name"],
            cwd=self.root,
        )["result"]
        self.assertTrue(renewed["current"], renewed)
        self.assertFalse(renewed["full_containment"])
        for repeat in range(2):
            finalized = self.cli(
                f"framework-producer-finalize-{repeat}",
                launcher,
                "project",
                "layout",
                "finalize",
                *common,
                cwd=self.root,
            )["result"]
            self.assertTrue(finalized["components_finalized"], finalized)
            self.assertFalse(finalized["full_containment"])
        self.assertFalse(
            (project / "components/legacy-project-wrapper/component.md").exists()
        )
        self.assertTrue(
            (
                project / "components/legacy-project-wrapper/implementation/app.py"
            ).is_file()
        )

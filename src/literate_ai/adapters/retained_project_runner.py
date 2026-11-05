"""Pure noncircular retained runner projection; no runtime/provider imports."""

from literate_ai.contracts.identity import ContentIdentity, canonical_identity

RETAINED_PROJECT_RUNNER_SCHEMA = "literate-ai/retained-project-test-runner@2"


def retained_project_runner_identity(plan, manifest, test_policy) -> ContentIdentity:
    """Bind complete typed semantics; omit only the single circular policy ref."""
    from literate_ai.contracts.retained_project_tests import RetainedProjectTestPolicy

    if not isinstance(test_policy, RetainedProjectTestPolicy):
        raise TypeError("retained.promotion.typed-test-policy-required")
    actions = [action for action in plan.profile.actions if action.stage == "test"]
    tools = {name: identity for name, _path, identity in plan.profile.tools}
    if not actions or set(dict(test_policy.reports)) != {a.action_id for a in actions}:
        raise ValueError("retained.promotion.complete-runner-inventory-required")
    semantic_policy = test_policy.to_dict()
    del semantic_policy["project_policy_identity"]
    return canonical_identity(
        {
            "schema": RETAINED_PROJECT_RUNNER_SCHEMA,
            "actions": [
                {"action": action.to_dict(), "tool_identity": tools[action.tool].uri}
                for action in actions
            ],
            "definitions": [
                member.to_dict()
                for member in manifest.members
                if member.role == "test-definition"
            ],
            "test_policy": semantic_policy,
        }
    )

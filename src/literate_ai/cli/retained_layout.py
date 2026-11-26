"""Fresh retained-layout intent through canonical project/state/service owners.

The dispatcher registers this boundary only with the complete renewal/recovery
integration. No saved JSON plan or operator-selected state path can issue an
owner. Default planning invokes no host build/test/acceptance commands.
"""

from __future__ import annotations

from pathlib import Path

from literate_ai._cache_lock import CacheLockError
from literate_ai._filesystem import UnsafeFilesystemPathError, require_safe_directory
from literate_ai.adapters.lifecycle_lock import ProjectLifecycleLockError
from literate_ai.adapters.retained_layout import (
    RetainedLayoutError,
    resolve_retained_layout,
)
from literate_ai.adapters.retained_layout_service import (
    apply_retained_layout_relocation,
    plan_retained_layout_relocation,
)
from literate_ai.adapters.standard_lifecycle_binding import (
    StandardLifecycleBindingError,
)
from literate_ai.adapters.user_paths import UserPathError, resolve_user_paths
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.retained_layout import RetainedLayoutDeclaration
from literate_ai.contracts.retained_project import RetainedProjectLimits
from literate_ai.projects import ProjectError, load_project


def relocate_implementation_from_args(args):
    """Plan from original source, or apply the full fresh acknowledgement."""
    apply = bool(getattr(args, "apply", False))
    schema = (
        "literate-ai/retained-layout-apply-result@1"
        if apply
        else "literate-ai/retained-layout-plan-result@1"
    )
    try:
        acknowledgement = getattr(args, "ack_plan", None)
        host_authorized = bool(getattr(args, "authorize_relocation", False))
        if apply and acknowledgement is None:
            raise RetainedLayoutError(
                "retained.layout.plan_acknowledgement_required",
                "application requires the full reviewed fresh plan identity",
            )
        if not apply and (acknowledgement is not None or host_authorized):
            raise RetainedLayoutError(
                "retained.layout.apply_required",
                "acknowledgement and host authorization belong to application only",
            )
        root = Path(args.project).absolute()
        require_safe_directory(root)
        if root.resolve(strict=True) != root:
            raise RetainedLayoutError(
                "retained.layout.project_redirected",
                "actual direct project root required",
            )
        project = load_project(root)
        if project.root != root:
            raise RetainedLayoutError(
                "retained.layout.project_root_required", "select the exact project root"
            )
        layout = resolve_retained_layout(project)
        declaration = RetainedLayoutDeclaration(
            getattr(args, "wrapper_component", None)
            or layout.declaration.wrapper_component,
            args.implementation_directory,
        )
        limits = RetainedProjectLimits(
            args.maximum_entries,
            args.maximum_file_bytes,
            args.maximum_total_bytes,
        )
        options = dict(
            limits=limits,
            case_sensitive=bool(args.case_sensitive),
            maximum_metadata_bytes=args.maximum_metadata_bytes,
        )
        if apply:
            result = apply_retained_layout_relocation(
                root,
                declaration,
                **options,
                acknowledged_plan_identity=ContentIdentity.parse_uri(acknowledgement),
                authorize_relocation=host_authorized,
                state_root=Path(resolve_user_paths().state_root),
            )
            return {"schema": schema, "status": "relocated", "relocation": result}, 0
        result = plan_retained_layout_relocation(root, declaration, **options)
        if (
            result["plan"]["source_plan"]["current_layout_identity"]
            != layout.identity.uri
        ):
            raise RetainedLayoutError(
                "retained.layout.layout_changed",
                "current layout changed while selecting intent",
            )
        return {"schema": schema, "status": "planned", **result}, 0
    except RetainedLayoutError as exc:
        code, message = exc.code, exc.message
    except ProjectLifecycleLockError:
        code = "retained.layout.lifecycle_lock_unavailable"
        message = "The actual project lifecycle could not be locked safely."
    except CacheLockError:
        code = "retained.layout.native_lock_unavailable"
        message = "The original native transaction lock could not be acquired safely."
    except StandardLifecycleBindingError as exc:
        code = exc.code
        message = "The actual installed noneditable framework could not be verified."
    except (ProjectError, UserPathError) as exc:
        code = exc.code
        message = (
            "The actual project or canonical operator state could not be verified."
        )
    except (OSError, ValueError, TypeError, RecursionError, UnsafeFilesystemPathError):
        code = (
            "retained.layout.apply_unavailable"
            if apply
            else "retained.layout.plan_unavailable"
        )
        message = (
            "The selected intent, original source or metadata could not be verified."
        )
    return {
        "schema": schema,
        "status": "refused",
        "refusal": {
            "code": code,
            "message": message,
        },
    }, 1

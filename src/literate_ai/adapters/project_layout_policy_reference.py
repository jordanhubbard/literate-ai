"""Finite resident-policy ledger projection, never source or movement authority.

The original observer owns the policy's exact bytes/native witness and the same
proved ledger placement. Unknown consumers and optional external policy parsers
remain blocked; no policy lookup, file read, release operation or foreign callback runs.
"""

from __future__ import annotations


def _bind_projection():
    import json

    from literate_ai import project_releases as release
    from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError

    def fail():
        raise ProjectLayoutPlanError(
            "framework_policy_reference_changed",
            "original finite policy reference producer changed",
        )

    def namespace(cls):
        values = dict(vars(cls))
        cache = values.pop("__slotnames__", None)
        if cache is not None and (
            type(cache) is not list
            or tuple(cache)
            != tuple(
                n
                for n in getattr(cls, "__slots__", ())
                if n not in {"__dict__", "__weakref__"}
            )
        ):
            fail()
        return values

    classes = tuple(
        (cls, namespace(cls), cls.__bases__, cls.__mro__)
        for cls in (
            release.ReleasePolicy,
            release.VersionBinding,
            release.ReleaseContributionsPolicy,
            release.ReleaseCollateralPolicy,
            release.ProjectReleaseError,
            json.JSONDecoder,
            json.JSONEncoder,
            json.JSONDecodeError,
        )
    )
    bindings = tuple(
        (release, name, getattr(release, name))
        for name in (
            "ReleasePolicy",
            "VersionBinding",
            "ReleaseContributionsPolicy",
            "ReleaseCollateralPolicy",
            "ProjectReleaseError",
            "re",
            "RELEASE_POLICY_SCHEMA",
            "LEGACY_RELEASE_POLICY_SCHEMA",
            "_RELATIVE_PATH",
            "_PYTHON_NAME",
            "_QUOTED_NAME",
            "_CARGO_NAME",
            "_REMOTE",
            "_REPOSITORY",
            "_TAG_PREFIX",
            "_COLLATERAL_RESOURCE_ID",
            "_BRANCH_NAME",
            "_mapping",
            "_keys",
            "_string",
            "_strings",
            "_relative_path",
            "_fail",
        )
    ) + tuple(
        (module, name, getattr(module, name))
        for module, names in (
            (
                json,
                (
                    "loads",
                    "dumps",
                    "JSONDecoder",
                    "JSONEncoder",
                    "JSONDecodeError",
                    "decoder",
                    "encoder",
                ),
            ),
            (
                json.decoder,
                (
                    "JSONDecoder",
                    "JSONDecodeError",
                    "JSONObject",
                    "JSONArray",
                    "scanstring",
                    "scanner",
                    "WHITESPACE",
                    "WHITESPACE_STR",
                    "_CONSTANTS",
                ),
            ),
            (
                json.scanner,
                ("make_scanner", "c_make_scanner", "py_make_scanner", "NUMBER_RE"),
            ),
            (
                json.encoder,
                (
                    "JSONEncoder",
                    "c_make_encoder",
                    "_make_iterencode",
                    "encode_basestring",
                    "encode_basestring_ascii",
                    "py_encode_basestring",
                    "py_encode_basestring_ascii",
                    "ESCAPE",
                    "ESCAPE_ASCII",
                    "ESCAPE_DCT",
                    "INFINITY",
                ),
            ),
        )
        for name in names
    )
    tables = tuple(
        (value, dict(value)) for _, _, value in bindings if type(value) is dict
    )
    functions = [value for _, _, value in bindings if hasattr(value, "__code__")]
    for _cls, values, _bases, _mro in classes:
        for value in values.values():
            if type(value) in (classmethod, staticmethod):
                value = value.__func__
            if hasattr(value, "__code__"):
                functions.append(value)
    parse = release.ReleasePolicy.from_dict
    release_error = release.ProjectReleaseError
    loads, dumps = json.loads, json.dumps
    external_parsers = (
        "qualification",
        "readme_latest_release",
        "authenticated_receipt",
    )

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate resident release-policy key")
            result[key] = value
        return result

    def decode(content):
        value = loads(content.decode("utf-8"), object_pairs_hook=pairs)
        if type(value) is not dict:
            raise ValueError("resident release policy must be an object")
        return value

    def project(content, moved):
        """Return only a supported one-leaf change and its explicit typed facts."""
        current()
        if type(content) is not bytes or len(content) > 16 * 1024**2:
            return None
        if type(moved) is not dict or any(
            type(k) is not str or type(v) is not str for k, v in moved.items()
        ):
            return None
        try:
            document = decode(content)
            # These branches delegate to distinct producers. They need their own
            # admitted closure before this owner can consume them; never execute
            # an unguarded optional parser or infer that its policy is invalid.
            if any(document.get(name) is not None for name in external_parsers):
                return None
            before = parse(document)
            if before.contributions is None:
                return None
            old = before.contributions.roadmap_goal_manifest
            destination = moved.get(old)
            if old is None or destination != "litai/" + old:
                return None
            rest = decode(content)
            rest["contributions"].pop("roadmap_goal_manifest")
            # Every remaining moved-path consumer still requires another owner.
            if any(path in dumps(rest, ensure_ascii=False) for path in moved):
                return None
            document["contributions"]["roadmap_goal_manifest"] = destination
            encoded = (dumps(document, ensure_ascii=False, indent=2) + "\n").encode()
            after = parse(decode(encoded))
            if after.contributions.roadmap_goal_manifest != destination:
                fail()
            return encoded, {
                "pointer": "/contributions/roadmap_goal_manifest",
                "from": old,
                "to": destination,
            }
        except (ValueError, TypeError, RecursionError, release_error):
            return None
        finally:
            current()

    def consumes(content, moved):
        """Discover decoded consumers independently of permission to rewrite."""
        current()
        try:
            if type(content) is not bytes or len(content) > 16 * 1024**2:
                return None
            if type(moved) is not dict or any(
                type(k) is not str or type(v) is not str for k, v in moved.items()
            ):
                return None
            normalized = dumps(decode(content), ensure_ascii=False)
            return any(path in normalized for path in moved)
        except (ValueError, TypeError, RecursionError):
            return None
        finally:
            current()

    functions.extend((fail, namespace, pairs, decode, project, consumes))
    states = tuple(
        (
            fn,
            fn.__code__,
            fn.__defaults__,
            fn.__kwdefaults__,
            None if fn.__kwdefaults__ is None else dict(fn.__kwdefaults__),
        )
        for fn in functions
    )

    def current():
        for module, name, original in bindings:
            if vars(module).get(name) is not original:
                fail()
        for table, values in tables:
            if set(table) != set(values) or any(
                table[k] is not v for k, v in values.items()
            ):
                fail()
        for cls, values, bases, mro in classes:
            actual = namespace(cls)
            if (
                cls.__bases__ is not bases
                or cls.__mro__ is not mro
                or set(actual) != set(values)
                or any(actual[name] is not value for name, value in values.items())
            ):
                fail()
        for fn, code, defaults, kwdefaults, kwvalues in states:
            if (
                fn.__code__ is not code
                or fn.__defaults__ is not defaults
                or fn.__kwdefaults__ is not kwdefaults
                or (
                    kwdefaults is not None
                    and (
                        set(kwdefaults) != set(kwvalues)
                        or any(kwdefaults[k] is not v for k, v in kwvalues.items())
                    )
                )
            ):
                fail()

    return project, consumes, current


(
    project_release_policy_ledger_reference,
    release_policy_consumes_moved_references,
    require_original_policy_reference_projector,
) = _bind_projection()
del _bind_projection

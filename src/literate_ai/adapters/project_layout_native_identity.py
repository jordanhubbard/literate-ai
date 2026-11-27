"""Explicit native-ID wire projections; these data functions issue no live owner.

Private native views keep integers for native equality and moves. Persisted
records use the existing canonical stat-ID encoding at these named fields only.
Nested public plans retain their own wire data and identity without rewriting.
"""

from literate_ai._filesystem import is_stat_identity_value, stat_identity_value


def _make_native_identity_calls(namespace, names):
    """Bind declared code paths once at their original owner's import boundary."""
    import builtins
    import types

    functions, slots, pending = {}, {}, []
    roots = {name: namespace[name] for name in names}
    for function in roots.values():
        scope, name = function.__globals__, function.__name__
        if scope.get(name) is function:
            slots[id(scope), name] = (scope, name, True, function)
    pending.extend(roots.values())
    while pending:
        function = pending.pop()
        if function in functions:
            continue
        if type(function) is not types.FunctionType:
            raise ValueError("original Python native identity projection required")
        functions[function] = (
            function.__code__,
            function.__defaults__,
            function.__kwdefaults__,
            tuple((function.__kwdefaults__ or {}).items()),
        )
        scope = function.__globals__
        for name in function.__code__.co_names:
            value = scope.get(name)
            if type(value) is types.FunctionType or hasattr(builtins, name):
                slots[id(scope), name] = (scope, name, name in scope, value)
                if name not in scope and name in function.__builtins__:
                    builtin_scope = function.__builtins__
                    slots[id(builtin_scope), name] = (
                        builtin_scope,
                        name,
                        True,
                        builtin_scope[name],
                    )
                if type(value) is types.FunctionType:
                    pending.append(value)
    function_rows = tuple((fn, *row) for fn, row in functions.items())
    slot_rows = tuple(slots.values())
    ports = {}
    size, exact_type, error, some, text_type = len, type, ValueError, any, str

    def check():
        for scope, name, present, original in slot_rows:
            if (name in scope) is not present or scope.get(name) is not original:
                raise error("original native identity dependency changed")
        for fn, code, defaults, keywords, items in function_rows:
            actual = fn.__kwdefaults__
            if (
                fn.__code__ is not code
                or fn.__defaults__ is not defaults
                or actual is not keywords
                or size(actual or {}) != size(items)
                or some(exact_type(key) is not text_type for key in (actual or {}))
                or some((actual or {}).get(key) is not value for key, value in items)
            ):
                raise error("original native identity producer changed")
        for name, (port, code) in ports.items():
            if (
                namespace.get(name) is not port
                or port.__code__ is not code
                or port.__defaults__ is not None
                or port.__kwdefaults__ is not None
            ):
                raise error("original native identity call boundary changed")

    check_code = check.__code__

    def bind(function):
        def call(*args, **kwargs):
            if (
                check.__code__ is not check_code
                or check.__defaults__ is not None
                or check.__kwdefaults__ is not None
            ):
                raise error("original native identity checker changed")
            check()
            result = function(*args, **kwargs)
            if (
                check.__code__ is not check_code
                or check.__defaults__ is not None
                or check.__kwdefaults__ is not None
            ):
                raise error("original native identity checker changed")
            check()
            return result

        return call

    for name, function in roots.items():
        port = bind(function)
        ports[name] = (port, port.__code__)
    ports["_native_identity_guard"] = (check, check.__code__)
    return {name: port for name, (port, _code) in ports.items()}


def _make_native_identity_boundaries(namespace, names):
    """Check captured projections before original owner callbacks and I/O."""
    from contextlib import contextmanager
    from functools import wraps
    from inspect import isgeneratorfunction
    from types import FunctionType

    from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError

    guard = namespace["_native_identity_guard"]
    guard_code = guard.__code__
    error_type = ProjectLayoutPlanError
    bound = {}

    def current():
        if (
            guard.__code__ is not guard_code
            or guard.__defaults__ is not None
            or guard.__kwdefaults__ is not None
        ):
            raise error_type(
                "native_identity_changed", "original native identity checker changed"
            )
        try:
            guard()
        except ValueError as error:
            raise error_type("native_identity_changed", str(error)) from error
        for name, (function, code) in bound.items():
            if (
                namespace.get(name) is not function
                or function.__code__ is not code
                or function.__defaults__ is not None
                or function.__kwdefaults__ is not None
            ):
                raise error_type(
                    "native_identity_changed",
                    "original native identity owner boundary changed",
                )

    current_code = current.__code__
    some, size, exact_type, text_type = any, len, type, str

    def checked():
        if (
            current.__code__ is not current_code
            or current.__defaults__ is not None
            or current.__kwdefaults__ is not None
        ):
            raise error_type(
                "native_identity_changed",
                "original native identity owner checker changed",
            )
        current()

    def bind(function):
        chain, subject = [], function
        while exact_type(subject) is FunctionType:
            wrapped = vars(subject).get("__wrapped__")
            chain.append(
                (
                    subject,
                    subject.__code__,
                    subject.__defaults__,
                    subject.__kwdefaults__,
                    tuple((subject.__kwdefaults__ or {}).items()),
                    wrapped,
                )
            )
            subject = wrapped
        originals = tuple(chain)

        def entry():
            checked()
            for fn, code, defaults, keywords, items, wrapped in originals:
                actual = fn.__kwdefaults__
                if (
                    fn.__code__ is not code
                    or fn.__defaults__ is not defaults
                    or actual is not keywords
                    or size(actual or {}) != size(items)
                    or some(exact_type(key) is not text_type for key in (actual or {}))
                    or some(
                        (actual or {}).get(key) is not value for key, value in items
                    )
                    or vars(fn).get("__wrapped__") is not wrapped
                ):
                    raise error_type(
                        "native_identity_changed",
                        "original native identity owner code changed",
                    )

        if isgeneratorfunction(getattr(function, "__wrapped__", None)):

            @contextmanager
            @wraps(function)
            def scope(*args, **kwargs):
                entry()
                with function(*args, **kwargs) as value:
                    checked()
                    yield value
                    checked()
                checked()

            return scope

        @wraps(function)
        def call(*args, **kwargs):
            entry()
            result = function(*args, **kwargs)
            checked()
            return result

        return call

    for name in names:
        function = bind(namespace[name])
        bound[name] = (function, function.__code__)
    return {name: function for name, (function, _code) in bound.items()}


def _identity(value, decode):
    if decode:
        if not is_stat_identity_value(value) or int(value) < 0:
            raise ValueError("noncanonical catalog native identity")
        return int(value)
    if type(value) is not int or value < 0:
        raise ValueError("nonnegative native integer identity required")
    return stat_identity_value(value)


def _vector(value, decode, *, native_key=False):
    if decode and type(value) is not list:
        raise ValueError("native wire vector must be an array")
    if type(value) not in (list, tuple) or len(value) not in (
        (2, 3) if native_key else (3,)
    ):
        raise ValueError("exact catalog native vector required")
    if native_key:
        return [_identity(part, decode) for part in value]
    mode = value[2]
    if type(mode) is not int or not 0 <= mode < (1 << 63):
        raise ValueError("catalog native mode must remain an integer")
    return [_identity(value[0], decode), _identity(value[1], decode), mode]


def wire_node(value):
    return _vector(value, False)


def native_node(value):
    return _vector(value, True)


def _mapping(value):
    if type(value) is not dict or len(value) > 8192:
        raise ValueError("bounded native record mapping required")
    return value


def _rows(value, names, decode, *, keys=False):
    result = {}
    for name, original in _mapping(value).items():
        row = dict(_mapping(original))
        for field in names:
            row[field] = _vector(row[field], decode)
        if keys:
            row["native_node"] = _vector(row["native_node"], decode, native_key=True)
        result[name] = row
    return result


def _directories(value, decode):
    return {name: _vector(node, decode) for name, node in _mapping(value).items()}


def _intent(value, decode):
    result = dict(_mapping(value))
    if result.get("schema") not in (
        "literate-ai/project-layout-catalog-continuation-journal@1",
        "literate-ai/project-layout-catalog-continuation-journal@2",
    ):
        raise ValueError("original catalog intent schema required")
    result["entries"] = _rows(result["entries"], ("node", "after_node"), decode)
    for name in ("coordination", "source_coordination"):
        result[name] = _rows(result[name], ("node",), decode, keys=True)
    result["history"] = _rows(result["history"], ("node",), decode)
    result["new_directories"] = _rows(result["new_directories"], ("node",), decode)
    for name in ("original_directories", "journal_directories"):
        result[name] = _directories(result[name], decode)
    result["journal_node"] = _vector(result["journal_node"], decode)
    return result


def catalog_intent_wire(value):
    return _intent(value, False)


def catalog_intent_native(value):
    return _intent(value, True)


def _renewal(value, decode):
    result = dict(_mapping(value))
    if result.get("schema") not in (
        "literate-ai/catalog-producer-renewal@1",
        "literate-ai/catalog-producer-renewal@2",
    ):
        raise ValueError("original catalog renewal schema required")
    result["entries"] = _rows(result["entries"], ("node", "after_node"), decode)
    for name in ("original_directories", "journal_directories"):
        result[name] = _directories(result[name], decode)
    result["journal_node"] = _vector(result["journal_node"], decode)
    return result


def catalog_renewal_wire(value):
    return _renewal(value, False)


def catalog_renewal_native(value):
    return _renewal(value, True)


def publication_record_wire(value):
    """Select the original pair owner's finite record format, never a callback."""
    if type(value) is dict and value.get("schema") == (
        "literate-ai/project-layout-framework-producer-renewal@1"
    ):
        return value
    return catalog_renewal_wire(value)


def _closure(value, decode):
    result = dict(_mapping(value))
    if result.get("schema") != "literate-ai/component-source-namespace-closure@1":
        raise ValueError("original source closure schema required")
    for name in ("source_node", "source_parent_node", "archive_parent_node"):
        result[name] = _vector(result[name], decode)
    result["coordination"] = _rows(result["coordination"], ("node",), decode, keys=True)
    result["payloads"] = _rows(result["payloads"], ("node",), decode)
    result["empty_directories"] = _directories(result["empty_directories"], decode)
    return result


def source_closure_wire(value):
    return _closure(value, False)


def source_closure_native(value):
    return _closure(value, True)


def _bind_original_codec():
    """One import-time provider baseline; later callers cannot refresh it."""
    import builtins
    from types import FunctionType

    namespace = globals()
    originals = {
        name: value
        for name, value in namespace.items()
        if type(value) is FunctionType and name != "_bind_original_codec"
    }
    rows = tuple(
        (
            name,
            function,
            function.__code__,
            function.__defaults__,
            function.__kwdefaults__,
            tuple((function.__kwdefaults__ or {}).items()),
        )
        for name, function in originals.items()
    )
    slots = {}
    for function in originals.values():
        scope = function.__globals__
        for name in function.__code__.co_names:
            value = scope.get(name)
            if type(value) is FunctionType or hasattr(builtins, name):
                slots[id(scope), name] = (scope, name, name in scope, value)
                if name not in scope and name in function.__builtins__:
                    builtin_scope = function.__builtins__
                    slots[id(builtin_scope), name] = (
                        builtin_scope,
                        name,
                        True,
                        builtin_scope[name],
                    )
    original_slots = tuple(slots.values())
    scalar_scope = is_stat_identity_value.__globals__
    scalar = stat_identity_value
    make_calls = originals["_make_native_identity_calls"]
    make_boundaries = originals["_make_native_identity_boundaries"]
    exports = {}
    exact_type, text_type, size, some, failure = type, str, len, any, ValueError

    def check():
        for scope, name, present, value in original_slots:
            if (name in scope) is not present or scope.get(name) is not value:
                raise failure("original native identity provider dependency changed")
        if scalar_scope.get("stat_identity_value") is not scalar:
            raise failure("original native identity scalar export changed")
        for name, function, code, defaults, keywords, items in rows:
            actual = function.__kwdefaults__
            if (
                namespace.get(name) is not function
                or function.__code__ is not code
                or function.__defaults__ is not defaults
                or actual is not keywords
                or size(actual or {}) != size(items)
                or some(exact_type(key) is not text_type for key in (actual or {}))
                or some((actual or {}).get(key) is not value for key, value in items)
            ):
                raise failure("original native identity provider changed")
        for name, (function, code) in exports.items():
            if (
                namespace.get(name) is not function
                or function.__code__ is not code
                or function.__defaults__ is not None
                or function.__kwdefaults__ is not None
            ):
                raise failure("original native identity binder changed")

    check_code = check.__code__

    def current():
        if (
            check.__code__ is not check_code
            or check.__defaults__ is not None
            or check.__kwdefaults__ is not None
        ):
            raise failure("original native identity provider checker changed")
        check()

    def calls(owner_namespace, names):
        current()
        if (
            exact_type(owner_namespace) is not dict
            or exact_type(names) is not tuple
            or size(names) > 32
            or some(exact_type(name) is not text_type for name in names)
            or some(
                name not in originals
                or owner_namespace.get(name) is not originals[name]
                for name in names
            )
        ):
            raise failure("original declared native identity roots required")
        result = make_calls(owner_namespace, names)
        current()
        return result

    def boundaries(owner_namespace, names):
        current()
        result = make_boundaries(owner_namespace, names)
        current()
        return result

    exports.update(
        {
            "bind_native_identity_calls": (calls, calls.__code__),
            "bind_native_identity_boundaries": (boundaries, boundaries.__code__),
        }
    )
    return {name: function for name, (function, _code) in exports.items()}


globals().update(_bind_original_codec())
del _bind_original_codec

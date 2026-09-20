"""Register independent signal policies with @register('name')."""

REGISTRY = {}


def register(name):
    def decorator(cls):
        if name in REGISTRY:
            raise ValueError(f"Duplicate strategy {name}")
        REGISTRY[name] = cls
        return cls

    return decorator


def load_builtins():
    # Explicit imports are intentional: frozen desktop builds cannot reliably
    # discover modules through pkgutil at runtime.
    from . import fixed as _fixed  # noqa: F401
    from . import green_wave as _green_wave  # noqa: F401
    from . import pressure as _pressure  # noqa: F401
    from . import webster as _webster  # noqa: F401


def available():
    """Return every built-in policy, including inside a frozen desktop app."""
    load_builtins()
    return tuple(sorted(REGISTRY))


def create(name, connection, bundle):
    load_builtins()
    if name not in REGISTRY:
        raise ValueError(f"Unknown strategy {name!r}; available: {', '.join(sorted(REGISTRY))}")
    return REGISTRY[name](connection, bundle)

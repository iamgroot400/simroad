"""Register independent signal policies with @register('name')."""

REGISTRY = {}


def register(name):
    def decorator(cls):
        if name in REGISTRY:
            raise ValueError(f"Duplicate strategy {name}")
        REGISTRY[name] = cls
        return cls

    return decorator


def create(name, connection, bundle):
    # Import modules in this package so adding one self-contained file is sufficient.
    import importlib
    import pkgutil

    for module in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{__name__}.{module.name}")
    if name not in REGISTRY:
        raise ValueError(f"Unknown strategy {name!r}; available: {', '.join(REGISTRY)}")
    return REGISTRY[name](connection, bundle)

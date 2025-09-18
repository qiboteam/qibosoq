"""qibosoq module."""

try:
    import importlib.metadata as im

    __version__ = im.version(__package__)
except im.PackageNotFoundError:
    __version__ = "0.0.0-dev"

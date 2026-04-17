"""DDS — Daedalus Deployment System."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("dds-deploy")
except PackageNotFoundError:
    __version__ = "0.3.0"  # fallback for editable/dev installs

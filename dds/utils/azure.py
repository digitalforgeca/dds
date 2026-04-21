"""Azure CLI wrapper utilities — re-exports from providers.azure.utils.

This module is kept for backward compatibility. New code should import from
dds.providers.azure.utils (for Azure-specific) or dds.utils.shell (for generic).
"""

from __future__ import annotations

# Re-export Azure wrappers
from dds.providers.azure.utils import az, az_json  # noqa: F401

# Re-export generic shell runner
from dds.utils.shell import run_cmd  # noqa: F401

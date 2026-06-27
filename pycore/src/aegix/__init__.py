"""Aegix — AI-Supervised Cybersecurity Tool Orchestration Platform (Python core).

The core is Python. It is supported by:
  * TypeScript adapters (MCP / IDE clients),
  * C and hand-tuned Assembly accelerators for hot paths (see ``aegix.accel``),
  * a Java performance layer for high-throughput, cross-platform fan-out.

The security layer (scope, risk gating, audit) is intentionally NOT part of this
package. It is owned and implemented separately by the security team according to
their own policies and the laws of the relevant jurisdictions.
"""

from .platform import Aegix, AegixOptions
from .core.config import AegixConfig, load_config, DEFAULT_CONFIG
from .core.types import (
    Artifact,
    Phase,
    ResultObject,
    SourceClient,
    TaskObject,
    ToolCall,
    ToolResult,
)

__version__ = "2.0.0"

__all__ = [
    "Aegix",
    "AegixOptions",
    "AegixConfig",
    "load_config",
    "DEFAULT_CONFIG",
    "Artifact",
    "Phase",
    "ResultObject",
    "SourceClient",
    "TaskObject",
    "ToolCall",
    "ToolResult",
    "__version__",
]

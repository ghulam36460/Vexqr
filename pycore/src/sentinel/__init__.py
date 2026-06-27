"""Sentinel — AI-Supervised Cybersecurity Tool Orchestration Platform (Python core).

The core is Python. It is supported by:
  * TypeScript adapters (MCP / IDE clients),
  * C and hand-tuned Assembly accelerators for hot paths (see ``sentinel.accel``),
  * a Java 26 performance layer for high-throughput, cross-platform fan-out.

The security layer (scope, risk gating, audit) is intentionally NOT part of this
package. It is owned and implemented separately by the security team according to
their own policies and the laws of the relevant jurisdictions.
"""

from .platform import Sentinel, SentinelOptions
from .core.config import SentinelConfig, load_config, DEFAULT_CONFIG
from .core.types import (
    Artifact,
    Phase,
    ResultObject,
    SourceClient,
    TaskObject,
    ToolCall,
    ToolResult,
)

__version__ = "0.2.0"

__all__ = [
    "Sentinel",
    "SentinelOptions",
    "SentinelConfig",
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

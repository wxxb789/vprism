"""vprism: Modern Financial Data Infrastructure Platform.

A next-generation personal finance/investment data platform that redefines
financial data access through modern architecture and tools.
"""

__version__ = "0.1.0"
__author__ = "vprism Team"
__email__ = "team@vprism.dev"

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .core.service import DataService
    from .models.query import DataQuery
    from .models.response import DataResponse

__all__ = [
    "__version__",
    "DataService",
    "DataQuery", 
    "DataResponse",
]
"""Conector Ruvic de mensajería empresarial en Azure Service Bus."""

from .client import ServiceBusClient
from .config import ENV_PREFIX, ServiceBusConfig
from .exceptions import (
    ServiceBusAuthError,
    ServiceBusConnectorError,
    ServiceBusDataError,
    ServiceBusNetworkError,
)
from .logging_utils import setup_logging

__all__ = [
    "ENV_PREFIX",
    "ServiceBusAuthError",
    "ServiceBusClient",
    "ServiceBusConfig",
    "ServiceBusConnectorError",
    "ServiceBusDataError",
    "ServiceBusNetworkError",
    "setup_logging",
]

__version__ = "1.0.0"

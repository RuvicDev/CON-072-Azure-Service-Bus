"""Excepciones propias del conector Azure Service Bus.

Separan los tres tipos de fallo que el usuario debe distinguir:
autenticación, red/servidor y datos. Nunca exponemos excepciones
crípticas del SDK subyacente.
"""


class ServiceBusConnectorError(Exception):
    """Error base del conector."""


class ServiceBusAuthError(ServiceBusConnectorError):
    """Credenciales inválidas o permisos insuficientes."""


class ServiceBusNetworkError(ServiceBusConnectorError):
    """No se pudo alcanzar el namespace de Service Bus (red/timeout)."""


class ServiceBusDataError(ServiceBusConnectorError):
    """La operación es válida pero la cola/topic/mensaje es inválido."""

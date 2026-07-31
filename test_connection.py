"""Prueba de conexión estándar del conector service_bus.

Firma estándar Ruvic: def test_connection() -> tuple[bool, str]
- Lee la configuración EXCLUSIVAMENTE de las env vars RUVIC_SERVICE_BUS_*.
- Nunca lanza excepciones; retorna (ok, mensaje).

Ejecutable también como script para pruebas locales:
    python test_connection.py
"""

from __future__ import annotations


def test_connection() -> tuple[bool, str]:
    """Conecta a Azure Service Bus y consulta métricas de la cola usando
    las env vars RUVIC_SERVICE_BUS_*."""
    try:
        from ruvic_service_bus_connector import (
            ServiceBusAuthError,
            ServiceBusClient,
            ServiceBusDataError,
            ServiceBusNetworkError,
        )
    except ImportError:
        return (
            False,
            "La librería ruvic-service-bus-connector no está instalada. "
            "Instala con: pip install git+https://github.com/Dgirto/"
            "Azure-Service-Bus.git#subdirectory=lib",
        )

    try:
        client = ServiceBusClient()  # valida que existan las env vars
    except ValueError as exc:
        return False, str(exc)

    try:
        client.ping()
    except ServiceBusAuthError as exc:
        return False, f"Autenticación fallida: {exc}"
    except ServiceBusNetworkError as exc:
        return False, f"Error de red: {exc}"
    except ServiceBusDataError as exc:
        return False, f"Error de datos: {exc}"
    except Exception as exc:  # red de seguridad: jamás propagar
        return False, f"Error inesperado: {exc}"

    return (
        True,
        f"Conexión exitosa a Service Bus ({client.config.fully_qualified_namespace}, cola={client.config.queue_name!r})",
    )


if __name__ == "__main__":
    ok, message = test_connection()
    print(f"{'OK' if ok else 'FALLO'}: {message}")
    raise SystemExit(0 if ok else 1)

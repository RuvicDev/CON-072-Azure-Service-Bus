"""Configuración del conector leída desde variables de entorno.

Convención de la plataforma: cada campo del formulario de configuración
llega como variable de entorno {ENV_PREFIX}{CAMPO} en mayúsculas.
Para este conector el prefijo es RUVIC_SERVICE_BUS_.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

ENV_PREFIX = "RUVIC_SERVICE_BUS_"


@dataclass(frozen=True)
class ServiceBusConfig:
    """Parámetros de conexión a Azure Service Bus vía Service Principal."""

    tenant_id: str
    client_id: str
    client_secret: str
    fully_qualified_namespace: str
    queue_name: str
    connect_timeout: int = 10

    @classmethod
    def from_env(cls) -> "ServiceBusConfig":
        """Construye la configuración desde las variables RUVIC_SERVICE_BUS_*.

        Raises:
            ValueError: si falta alguna variable obligatoria.

        Ejemplo:
            >>> config = ServiceBusConfig.from_env()
            >>> config.fully_qualified_namespace
            'mi-namespace.servicebus.windows.net'
        """
        missing = [
            f"{ENV_PREFIX}{name}"
            for name in (
                "TENANT_ID",
                "CLIENT_ID",
                "CLIENT_SECRET",
                "FULLY_QUALIFIED_NAMESPACE",
                "QUEUE_NAME",
            )
            if not os.environ.get(f"{ENV_PREFIX}{name}")
        ]
        if missing:
            raise ValueError(
                "Faltan variables de entorno del conector service_bus: "
                + ", ".join(missing)
                + ". Configura el conector en Settings → Conectores."
            )
        return cls(
            tenant_id=os.environ[f"{ENV_PREFIX}TENANT_ID"],
            client_id=os.environ[f"{ENV_PREFIX}CLIENT_ID"],
            client_secret=os.environ[f"{ENV_PREFIX}CLIENT_SECRET"],
            fully_qualified_namespace=os.environ[f"{ENV_PREFIX}FULLY_QUALIFIED_NAMESPACE"],
            queue_name=os.environ[f"{ENV_PREFIX}QUEUE_NAME"],
            connect_timeout=int(os.environ.get(f"{ENV_PREFIX}CONNECT_TIMEOUT", "10")),
        )

"""Cliente de mensajería empresarial para Azure Service Bus.

Capacidades:
- send_message():      envía un mensaje a la cola configurada.
- receive_message():    recibe (y confirma) un mensaje de la cola configurada.
- get_queue_metrics():  consulta métricas de la cola (cantidad de
                        mensajes activos, muertos, programados).

Las credenciales SIEMPRE provienen de variables de entorno
RUVIC_SERVICE_BUS_* (ver config.ServiceBusConfig.from_env). Prohibido
hardcodearlas.

Nota: `receive_message` usa modo peek-lock y confirma (completa) el
mensaje automáticamente al recibirlo — el mensaje se elimina de la cola
tras leerse, como es habitual en un consumidor de Service Bus.
"""

from __future__ import annotations

from typing import Any

from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ResourceNotFoundError,
    ServiceRequestError,
)
from azure.identity import ClientSecretCredential
from azure.servicebus import ServiceBusClient as _AzureServiceBusClient
from azure.servicebus import ServiceBusMessage
from azure.servicebus.exceptions import ServiceBusError
from azure.servicebus.management import ServiceBusAdministrationClient

from .config import ServiceBusConfig
from .exceptions import (
    ServiceBusAuthError,
    ServiceBusDataError,
    ServiceBusNetworkError,
)
from .logging_utils import get_logger


class ServiceBusClient:
    """Cliente de mensajería de Azure Service Bus sobre la cola configurada.

    Args:
        config: configuración de conexión. Si se omite, se lee de las
            variables de entorno RUVIC_SERVICE_BUS_* (comportamiento
            estándar en el runtime de la plataforma).

    Ejemplo:
        >>> client = ServiceBusClient()  # lee RUVIC_SERVICE_BUS_* del entorno
        >>> client.send_message("hola mundo")
    """

    def __init__(self, config: ServiceBusConfig | None = None) -> None:
        self.config = config or ServiceBusConfig.from_env()
        self._logger = get_logger()
        self._credential: ClientSecretCredential | None = None

    # ------------------------------------------------------------------ #
    # Conexión
    # ------------------------------------------------------------------ #

    def _get_credential(self) -> ClientSecretCredential:
        if self._credential is None:
            self._credential = ClientSecretCredential(
                tenant_id=self.config.tenant_id,
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
            )
        return self._credential

    def ping(self) -> bool:
        """Verifica la conexión consultando las métricas de la cola.

        Returns:
            True si la conexión funciona.

        Raises:
            ServiceBusAuthError / ServiceBusNetworkError / ServiceBusDataError.
        """
        self.get_queue_metrics()
        self._logger.info(
            "Ping exitoso a Service Bus %s", self.config.fully_qualified_namespace
        )
        return True

    # ------------------------------------------------------------------ #
    # Capacidad 1: enviar un mensaje
    # ------------------------------------------------------------------ #

    def send_message(self, body: str) -> None:
        """Envía un mensaje a la cola configurada.

        Args:
            body: contenido del mensaje (texto).

        Ejemplo:
            >>> client.send_message("hola mundo")
        """
        if not body:
            raise ServiceBusDataError("body no puede estar vacío.")
        try:
            with _AzureServiceBusClient(
                fully_qualified_namespace=self.config.fully_qualified_namespace,
                credential=self._get_credential(),
            ) as sb_client:
                with sb_client.get_queue_sender(self.config.queue_name) as sender:
                    sender.send_messages(ServiceBusMessage(body))
        except ClientAuthenticationError as exc:
            raise ServiceBusAuthError(
                f"Credenciales inválidas o sin permiso suficiente para enviar: {exc}"
            ) from exc
        except ServiceBusError as exc:
            raise ServiceBusDataError(f"No se pudo enviar el mensaje: {exc}") from exc
        self._logger.info("Mensaje enviado a %s", self.config.queue_name)

    # ------------------------------------------------------------------ #
    # Capacidad 2: recibir un mensaje
    # ------------------------------------------------------------------ #

    def receive_message(self, max_wait_seconds: int = 5) -> str | None:
        """Recibe y confirma (completa) un mensaje de la cola configurada.

        El mensaje se elimina de la cola al confirmarse, como es
        habitual en un consumidor de Service Bus.

        Args:
            max_wait_seconds: tiempo máximo de espera si no hay mensajes
                disponibles (default 5).

        Returns:
            El contenido del mensaje recibido, o None si no había
            ningún mensaje disponible en ese tiempo.

        Ejemplo:
            >>> client.receive_message()
            'hola mundo'
        """
        try:
            with _AzureServiceBusClient(
                fully_qualified_namespace=self.config.fully_qualified_namespace,
                credential=self._get_credential(),
            ) as sb_client:
                with sb_client.get_queue_receiver(self.config.queue_name) as receiver:
                    messages = receiver.receive_messages(
                        max_message_count=1, max_wait_time=max_wait_seconds
                    )
                    if not messages:
                        self._logger.info(
                            "No había mensajes disponibles en %s", self.config.queue_name
                        )
                        return None
                    message = messages[0]
                    body = b"".join(message.body).decode("utf-8")
                    receiver.complete_message(message)
        except ClientAuthenticationError as exc:
            raise ServiceBusAuthError(
                f"Credenciales inválidas o sin permiso suficiente para recibir: {exc}"
            ) from exc
        except ServiceBusError as exc:
            raise ServiceBusDataError(f"No se pudo recibir el mensaje: {exc}") from exc
        self._logger.info("Mensaje recibido y confirmado de %s", self.config.queue_name)
        return body

    # ------------------------------------------------------------------ #
    # Capacidad 3: consultar métricas
    # ------------------------------------------------------------------ #

    def get_queue_metrics(self) -> dict[str, Any]:
        """Consulta métricas de la cola configurada.

        Returns:
            Dict con: active_message_count, dead_letter_message_count,
            scheduled_message_count, size_in_bytes.

        Ejemplo:
            >>> client.get_queue_metrics()
            {'active_message_count': 3, 'dead_letter_message_count': 0, ...}
        """
        try:
            with ServiceBusAdministrationClient(
                fully_qualified_namespace=self.config.fully_qualified_namespace,
                credential=self._get_credential(),
            ) as admin_client:
                props = admin_client.get_queue_runtime_properties(self.config.queue_name)
        except ClientAuthenticationError as exc:
            raise ServiceBusAuthError(
                f"Credenciales inválidas o sin permiso suficiente para consultar métricas: {exc}"
            ) from exc
        except ResourceNotFoundError as exc:
            raise ServiceBusDataError(
                f"La cola {self.config.queue_name!r} no existe."
            ) from exc
        except ServiceRequestError as exc:
            raise ServiceBusNetworkError(f"No se pudo conectar a Service Bus: {exc}") from exc
        except HttpResponseError as exc:
            raise ServiceBusDataError(f"Error de Service Bus: {exc}") from exc

        result = {
            "active_message_count": props.active_message_count,
            "dead_letter_message_count": props.dead_letter_message_count,
            "scheduled_message_count": props.scheduled_message_count,
            "size_in_bytes": props.size_in_bytes,
        }
        self._logger.info(
            "Métricas de %s: %d mensajes activos", self.config.queue_name,
            result["active_message_count"],
        )
        return result

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

Permisos: enviar requiere "Azure Service Bus Data Sender"; recibir y la
prueba de conexión (ping, que solo hace peek) requieren "Azure Service Bus
Data Receiver". get_queue_metrics() lee la descripción de la cola, que
Service Bus exige con el derecho Manage: solo funciona con "Azure Service
Bus Data Owner".
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
from azure.servicebus.exceptions import (
    MessageLockLostError,
    MessagingEntityNotFoundError,
    ServiceBusAuthenticationError,
    ServiceBusAuthorizationError,
    ServiceBusError,
)
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
        """Verifica la conexión espiando (peek) la cola, sin consumir ni
        bloquear mensajes. Solo requiere el rol "Azure Service Bus Data
        Receiver".

        Returns:
            True si la conexión funciona.

        Raises:
            ServiceBusAuthError / ServiceBusNetworkError / ServiceBusDataError.
        """
        try:
            with _AzureServiceBusClient(
                fully_qualified_namespace=self.config.fully_qualified_namespace,
                credential=self._get_credential(),
            ) as sb_client:
                with sb_client.get_queue_receiver(self.config.queue_name) as receiver:
                    receiver.peek_messages(max_message_count=1)
        except (ClientAuthenticationError, ServiceBusAuthenticationError, ServiceBusAuthorizationError) as exc:
            raise ServiceBusAuthError(
                f"No se pudo acceder a la cola {self.config.queue_name!r}. Con Microsoft Entra ID, "
                "Service Bus responde igual en dos casos: la cola no existe en el namespace, o la "
                "aplicación no tiene el rol 'Azure Service Bus Data Receiver' sobre ella. Verifica "
                f"el nombre de la cola y la asignación del rol. Detalle: {exc}"
            ) from exc
        except MessagingEntityNotFoundError as exc:
            raise ServiceBusDataError(f"La cola {self.config.queue_name!r} no existe.") from exc
        except ServiceBusError as exc:
            raise ServiceBusNetworkError(f"No se pudo conectar a Service Bus: {exc}") from exc
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
        if body is not None and not isinstance(body, str):
            raise ServiceBusDataError(f"body debe ser un string, no {type(body).__name__}.")
        if not body or not body.strip():
            raise ServiceBusDataError("body no puede estar vacío ni contener solo espacios.")
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
            max_wait_seconds = int(max_wait_seconds)
        except (TypeError, ValueError) as exc:
            raise ServiceBusDataError(
                f"max_wait_seconds inválido: {max_wait_seconds!r}. Debe ser un número entero."
            ) from exc
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
        except MessageLockLostError as exc:
            raise ServiceBusDataError(
                "El mensaje se recibió pero no se pudo confirmar porque su bloqueo venció "
                "(sigue en la cola y se volverá a entregar). Suele ocurrir si el reloj del "
                "equipo que ejecuta el conector está desfasado más que la 'duración del "
                f"bloqueo' de la cola. Detalle: {exc}"
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

        Requiere el rol "Azure Service Bus Data Owner": Service Bus exige el
        derecho Manage para leer la descripción de la cola.

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
                "Sin permiso para consultar métricas: Service Bus exige el derecho Manage "
                "(rol 'Azure Service Bus Data Owner'); los roles Data Sender/Receiver no "
                f"alcanzan. Detalle: {exc}"
            ) from exc
        except ResourceNotFoundError as exc:
            raise ServiceBusDataError(
                f"La cola {self.config.queue_name!r} no existe."
            ) from exc
        except ServiceRequestError as exc:
            raise ServiceBusNetworkError(f"No se pudo conectar a Service Bus: {exc}") from exc
        except HttpResponseError as exc:
            if exc.status_code in (401, 403):
                raise ServiceBusAuthError(
                    "Sin permiso para consultar métricas: Service Bus exige el derecho Manage "
                    "(rol 'Azure Service Bus Data Owner'); los roles Data Sender/Receiver no "
                    "alcanzan."
                ) from exc
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

---
name: service-bus
description: Enviar y recibir mensajes en una cola de Azure Service Bus, y consultar métricas de la cola
---

# Azure Service Bus

Conector para mensajería empresarial en Azure Service Bus. Opera
sobre una única cola (queue) configurada — no soporta topics ni
subscriptions, que tienen un modelo de consumo distinto.

## Credenciales

Usa un Service Principal de Azure AD (`tenant_id`, `client_id`,
`client_secret`) autenticado vía `azure-identity.ClientSecretCredential`.
Nunca hardcodees ni loguees el `client_secret`. El Service Principal
debe tener asignados, limitados al namespace o a la cola:

- **"Azure Service Bus Data Sender"** — requerido para `send_message`.
- **"Azure Service Bus Data Receiver"** — requerido para
  `receive_message` y `get_queue_metrics`.

No uses el rol "Azure Service Bus Data Owner" ni permisos de
administración del namespace.

## Capacidades

### `send_message(body: str) -> None`

Envía un mensaje de texto a la cola configurada. Escribe un mensaje
real; no hay modo dry-run.

```python
client.send_message("pedido #1234 procesado")
```

### `receive_message(max_wait_seconds: int = 10) -> str | None`

Recibe (peek-lock) y confirma (`complete_message`) el siguiente
mensaje disponible en la cola, eliminándolo. Retorna `None` si no
hay mensajes dentro del tiempo de espera — esto no es un error.

```python
mensaje = client.receive_message(max_wait_seconds=10)
```

### `get_queue_metrics() -> dict`

Consulta metadatos de solo lectura de la cola (mensajes activos, en
dead-letter, tamaño, etc.) vía `ServiceBusAdministrationClient`.

```python
metricas = client.get_queue_metrics()
```

## Manejo de errores

Todas las excepciones heredan de `ServiceBusConnectorError`:

- `ServiceBusAuthError`: credenciales inválidas o permisos RBAC
  insuficientes.
- `ServiceBusNetworkError`: namespace inalcanzable, timeout de red.
- `ServiceBusDataError`: cola inexistente u otro error de datos.

Nunca dejes propagar excepciones crudas del SDK de Azure
(`azure.core.exceptions.*`) — siempre se traducen a estas.

## Buenas prácticas

- Tratá `send_message` y `receive_message` como operaciones con
  efectos secundarios reales (escritura y eliminación
  respectivamente); no las ejecutes contra una cola de producción
  sin confirmar con el usuario.
- `get_queue_metrics` es segura de ejecutar libremente (solo
  lectura).
- Si `receive_message` retorna `None` repetidamente, verificá que
  otro consumidor no esté vaciando la cola antes de asumir un fallo
  de conexión.

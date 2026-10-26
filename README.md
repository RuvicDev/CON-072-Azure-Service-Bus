# Conector Azure Service Bus (CON-072)

Conector Ruvic de mensajería empresarial en Azure Service Bus. Permite
enviar un mensaje a una cola, recibir (y confirmar) un mensaje, y
consultar métricas de la cola.

**Este conector opera sobre colas (queues), no sobre topics/subscriptions**
— ambos tienen modelos de API y de consumo distintos en Service Bus; si
necesitás topics, se requeriría un conector separado.

## Instalación

```bash
pip install git+https://github.com/Dgirto/Azure-Service-Bus.git#subdirectory=lib
```

Python 3.10+. Dependencias: `azure-identity`, `azure-servicebus`.

## Permisos requeridos en Azure

Crea un **Service Principal dedicado** y otorgale, limitado al
namespace o a la cola específica:

- **"Azure Service Bus Data Sender"**: necesario para `send_message`.
- **"Azure Service Bus Data Receiver"**: necesario para
  `receive_message` y para la prueba de conexión (`ping` hace un *peek*
  que no consume ni bloquea mensajes).
- **"Azure Service Bus Data Owner"**: solo si vas a usar
  `get_queue_metrics`. Service Bus exige el derecho *Manage* para leer
  la descripción de la cola ("Get the queue description" en la tabla de
  derechos de Microsoft), así que con Sender + Receiver esa operación
  falla con un error de permisos. Data Owner también permite administrar
  entidades: asígnalo limitado a la cola, nunca al namespace completo, y
  solo si necesitas las métricas.

## Variables de entorno (`RUVIC_SERVICE_BUS_*`)

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `RUVIC_SERVICE_BUS_TENANT_ID` | Sí | Tenant ID de Azure AD |
| `RUVIC_SERVICE_BUS_CLIENT_ID` | Sí | Client ID del Service Principal |
| `RUVIC_SERVICE_BUS_CLIENT_SECRET` | Sí | Client Secret del Service Principal |
| `RUVIC_SERVICE_BUS_FULLY_QUALIFIED_NAMESPACE` | Sí | Namespace (ej. `mi-namespace.servicebus.windows.net`) |
| `RUVIC_SERVICE_BUS_QUEUE_NAME` | Sí | Nombre de la cola |
| `RUVIC_SERVICE_BUS_CONNECT_TIMEOUT` | No (default `10`) | Timeout de conexión en segundos |

## Pruebas locales

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ./lib

export RUVIC_SERVICE_BUS_TENANT_ID=tu-tenant-id
export RUVIC_SERVICE_BUS_CLIENT_ID=tu-client-id
export RUVIC_SERVICE_BUS_CLIENT_SECRET=tu-client-secret
export RUVIC_SERVICE_BUS_FULLY_QUALIFIED_NAMESPACE=tu-namespace.servicebus.windows.net
export RUVIC_SERVICE_BUS_QUEUE_NAME=tu-cola-de-prueba

python test_connection.py
python validate_local.py
```

## Notas de integración

- `get_queue_metrics` es de **solo lectura**. `send_message` **SÍ
  escribe** un mensaje real en la cola. `receive_message` **SÍ
  elimina** el mensaje recibido de la cola al confirmarlo
  (comportamiento estándar de un consumidor peek-lock).
- `receive_message` retorna `None` si no hay ningún mensaje disponible
  dentro del tiempo de espera configurado — no es un error.
- Los mensajes se envían y reciben como texto plano (UTF-8); si
  necesitás enviar JSON estructurado, serializalo vos antes de llamar
  a `send_message`.
- `get_queue_metrics` usa `ServiceBusAdministrationClient`, que es
  parte del mismo paquete `azure-servicebus` (no requiere
  `azure-mgmt-servicebus` por separado).
- `send_message` rechaza mensajes vacíos o de solo espacios.
- **Reloj del equipo:** el SDK decide si el bloqueo de un mensaje recibido
  sigue vigente comparando la hora del servidor con la hora local. Si el
  reloj de la máquina que ejecuta el conector está desfasado más que la
  "duración del bloqueo" de la cola (1 minuto por defecto), recibir falla
  con un error de bloqueo vencido: el mensaje no se pierde, sigue en la
  cola. Sincroniza la hora (NTP) o aumenta la duración del bloqueo.

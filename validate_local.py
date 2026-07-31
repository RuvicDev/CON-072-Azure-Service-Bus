"""Validación local del conector service_bus: ejercita las 3 capacidades.

Uso:
    python validate_local.py

Requiere las variables RUVIC_SERVICE_BUS_* exportadas en el entorno,
apuntando a una cola de prueba.

ADVERTENCIA: este script envía y recibe un mensaje REAL en la cola
configurada (el mensaje recibido se elimina de la cola al confirmarse).
Ejecútalo solo contra una cola de pruebas.
"""

from ruvic_service_bus_connector import ServiceBusClient, setup_logging

setup_logging("INFO")
client = ServiceBusClient()

print("== 1. Consultar métricas de la cola ==")
metricas = client.get_queue_metrics()
print(f"  {metricas}")

print("== 2. Enviar mensaje de prueba ==")
client.send_message("prueba de validación local Ruvic")
print("  enviado")

print("== 3. Recibir mensaje ==")
mensaje = client.receive_message(max_wait_seconds=10)
print(f"  recibido: {mensaje!r}")

print("\nTodo OK: get_queue_metrics, send_message y receive_message funcionan.")

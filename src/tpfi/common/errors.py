"""Excepciones propias del sistema.

Tener una jerarquía propia permite capturar los errores esperados con un solo
`except TpfiError` y traducirlos a una respuesta JSON, sin ocultar errores de
programación, que siguen siendo excepciones comunes de Python.
"""


class TpfiError(Exception):
    """Error esperado del sistema; su mensaje puede mostrarse al usuario."""

    #: Código de estado que recibe el cliente, con el mismo significado que en HTTP.
    status = 500


class ValidationError(TpfiError):
    """El pedido no tiene los datos mínimos o sus datos son inválidos."""

    status = 400


class RecordNotFoundError(TpfiError):
    """El registro pedido no existe en CorporateData."""

    status = 404


class StorageError(TpfiError):
    """No se pudo completar una operación contra DynamoDB."""

    status = 502


class ProtocolError(TpfiError):
    """El mensaje recibido por el socket no respeta el formato acordado."""

    status = 400

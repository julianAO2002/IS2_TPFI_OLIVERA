"""Utilidades compartidas por las interfaces de línea de comandos."""

import argparse
import io
import logging
import sys
from typing import NoReturn

_LOG_FORMAT = "%(asctime)s %(levelname)s %(threadName)s %(name)s: %(message)s"


class ArgumentParser(argparse.ArgumentParser):
    """Parser que informa los errores de uso en español."""

    def __init__(self, description: str) -> None:
        """Crea el parser sin abreviaturas, para aceptar solo opciones exactas."""
        super().__init__(description=description, allow_abbrev=False)

    def error(self, message: str) -> NoReturn:
        """Muestra el error y termina con el código 2, habitual en errores de uso."""
        self.print_usage(sys.stderr)
        self.exit(2, f"Error en los argumentos: {message}\n")


def port_number(text: str) -> int:
    """Convierte un argumento de línea de comandos a un puerto válido."""
    try:
        port = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{text}' no es un número de puerto") from None
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"el puerto {port} no está entre 1 y 65535")
    return port


def positive_seconds(text: str) -> float:
    """Convierte un argumento a una cantidad positiva de segundos."""
    try:
        seconds = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{text}' no es una cantidad de segundos") from None
    if not 0 < seconds < float("inf"):
        raise argparse.ArgumentTypeError("los segundos deben ser un número positivo")
    return seconds


def configure_logging(verbose: bool) -> None:
    """Configura el log por salida estándar.

    Con `-v` se ven los mensajes de debug. Sin `-v` solo aparecen las advertencias, de
    modo que los mensajes de diagnóstico quedan apagados en el uso normal.
    """
    # En Windows la consola puede no usar UTF-8 y fallar al imprimir ciertos caracteres.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")

    logging.basicConfig(
        stream=sys.stdout,
        level=logging.DEBUG if verbose else logging.WARNING,
        format=_LOG_FORMAT,
        force=True,
    )
    # El debug de estas librerías es muy extenso y puede incluir firmas de pedidos.
    for noisy in ("boto3", "botocore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

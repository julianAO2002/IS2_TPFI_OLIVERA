"""Infraestructura de las pruebas de aceptación.

Las pruebas ejecutan los tres programas reales como procesos separados, igual que un
usuario. Pueden correr contra dos destinos:

- Por defecto, contra `moto`, un DynamoDB simulado. No necesita credenciales y es lo
  que usa el CI.
- Con `TPFI_ACCEPTANCE_AWS=1`, contra las tablas reales. Son tablas compartidas con
  otros alumnos: solo se escriben claves con el prefijo `OLIVERA-TEST-`, y al terminar
  solo se borran esas claves.

La tabla CorporateLog es grande y su capacidad de lectura es limitada, así que las
pruebas nunca la recorren con un scan: toman la clave de cada fila del log de debug del
servidor y la leen con `get_item`. Un scan por prueba agotó la capacidad compartida en
la primera corrida real.

Con `TPFI_EVIDENCE_DIR=carpeta` se guarda ahí el log de debug del servidor.
"""

import json
import os
import re
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any

import boto3
import pytest

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table

ROOT = Path(__file__).resolve().parents[2]
TEST_PREFIX = "OLIVERA-TEST-"
START_TIMEOUT_SECONDS = 20.0
AUDIT_LINE = re.compile(r"Auditoría registrada: clave=(\S+) cliente=(\S+)")


def free_port() -> int:
    """Pide al sistema un puerto libre."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def wait_for_port(port: int, process: subprocess.Popen[bytes] | None = None) -> None:
    """Espera a que un programa empiece a escuchar en el puerto."""
    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise AssertionError(f"El proceso terminó antes de tiempo: {process.returncode}")
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
            return
        except OSError:
            time.sleep(0.05)
    raise AssertionError(f"Nadie escucha en el puerto {port}")


@dataclass
class Backend:
    """Destino de las pruebas y acceso directo a sus tablas."""

    env: dict[str, str]
    data: "Table"
    log: "Table"
    created_keys: list[str] = field(default_factory=list)

    def new_key(self) -> str:
        """Genera una clave propia y recuerda borrarla al final."""
        key = f"{TEST_PREFIX}{uuid.uuid4().hex[:12]}"
        self.created_keys.append(key)
        return key

    def row(self, key: str) -> dict[str, Any] | None:
        """Lee una fila de CorporateData directamente, sin pasar por el sistema."""
        return self.data.get_item(Key={"id": key}, ConsistentRead=True).get("Item")

    def audit_row(self, key: str) -> dict[str, Any]:
        """Lee una fila de CorporateLog directamente de la tabla."""
        item = self.log.get_item(Key={"id": key}, ConsistentRead=True).get("Item")
        if item is None:
            raise AssertionError(f"El servidor informó la auditoría {key}, pero no está en la tabla.")
        return item


@pytest.fixture(scope="session")
def backend() -> Iterator[Backend]:
    """Prepara el destino elegido."""
    if os.environ.get("TPFI_ACCEPTANCE_AWS") == "1":
        # Con AWS real se usan las credenciales del perfil; el código no las conoce.
        dynamodb = boto3.resource("dynamodb")
        selected = Backend(dict(os.environ), dynamodb.Table("CorporateData"), dynamodb.Table("CorporateLog"))
        yield selected
        _delete_own_rows(selected)
        return

    port = free_port()
    command = [sys.executable, "-c", f"from moto.server import main; main(['-H', '127.0.0.1', '-p', '{port}'])"]
    moto_process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    env = {
        **os.environ,
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_ENDPOINT_URL": f"http://127.0.0.1:{port}",
    }
    env.pop("AWS_PROFILE", None)
    try:
        wait_for_port(port, moto_process)
        session = boto3.Session(aws_access_key_id="testing", aws_secret_access_key="testing", region_name="us-east-1")
        dynamodb = session.resource("dynamodb", endpoint_url=env["AWS_ENDPOINT_URL"])
        for name in ("CorporateData", "CorporateLog"):
            dynamodb.create_table(
                TableName=name,
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
        yield Backend(env, dynamodb.Table("CorporateData"), dynamodb.Table("CorporateLog"))
    finally:
        moto_process.terminate()
        moto_process.wait(timeout=10)


def _delete_own_rows(selected: Backend) -> None:
    """Borra solo las filas creadas por las pruebas."""
    for key in selected.created_keys:
        if not key.startswith(TEST_PREFIX):
            raise AssertionError(f"Clave ajena: {key}")
        selected.data.delete_item(Key={"id": key})


@dataclass
class Result:
    """Resultado de ejecutar un programa."""

    code: int
    stdout: str
    stderr: str

    @property
    def json(self) -> Any:
        """Interpreta la salida estándar como JSON."""
        return json.loads(self.stdout)


@dataclass
class Programs:
    """Ejecuta los tres programas del trabajo."""

    backend: Backend
    tmp_path: Path
    test_name: str
    processes: list[subprocess.Popen[bytes]] = field(default_factory=list)
    log_files: list[IO[bytes]] = field(default_factory=list)

    def run(self, script: str, *arguments: str, timeout: float = 40.0) -> Result:
        """Ejecuta un programa hasta que termine."""
        completed = subprocess.run(
            [sys.executable, str(ROOT / script), *arguments],
            env=self._env(),
            cwd=self.tmp_path,
            capture_output=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )
        return Result(completed.returncode, completed.stdout, completed.stderr)

    def request(self, port: int, payload: Any, *arguments: str) -> Result:
        """Escribe el pedido en input.json y ejecuta singletonclient."""
        input_path = self.tmp_path / "input.json"
        input_path.write_text(json.dumps(payload), encoding="utf-8")
        return self.run("singletonclient.py", f"-i={input_path}", f"-p={port}", *arguments)

    def start(self, script: str, *arguments: str, log_name: str) -> subprocess.Popen[bytes]:
        """Lanza un programa que queda corriendo, con su salida en un archivo."""
        log_file = self.log_path(log_name).open("wb")
        self.log_files.append(log_file)
        process = subprocess.Popen(
            [sys.executable, "-u", str(ROOT / script), *arguments],
            env=self._env(),
            cwd=self.tmp_path,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        self.processes.append(process)
        return process

    def start_server(self, port: int, log_name: str = "servidor.log") -> subprocess.Popen[bytes]:
        """Lanza el servidor con debug activado y espera a que atienda."""
        process = self.start("singletonproxyobserver.py", f"-p={port}", "-v", log_name=log_name)
        wait_for_port(port, process)
        return process

    def log_path(self, name: str) -> Path:
        """Devuelve dónde se guarda la salida de un proceso."""
        evidence = os.environ.get("TPFI_EVIDENCE_DIR")
        folder = Path(evidence) if evidence else self.tmp_path
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"{self.test_name}-{name}"

    def audit_rows(self, client_uuid: str) -> list[dict[str, Any]]:
        """Devuelve las filas de CorporateLog de un cliente en esta prueba."""
        rows: list[dict[str, Any]] = []
        for path in self.log_path("x").parent.glob(f"{self.test_name}-*.log"):
            for key, client in AUDIT_LINE.findall(path.read_text(encoding="utf-8", errors="replace")):
                if client == client_uuid:
                    rows.append(self.backend.audit_row(key))
        return rows

    def log_text(self, name: str) -> str:
        """Lee la salida acumulada de un proceso."""
        return self.log_path(name).read_text(encoding="utf-8", errors="replace")

    def _env(self) -> dict[str, str]:
        return {**self.backend.env, "PYTHONIOENCODING": "utf-8"}

    def stop_all(self) -> None:
        """Termina los procesos que sigan vivos."""
        for process in self.processes:
            process.kill()
            process.wait(timeout=10)
        for log_file in self.log_files:
            log_file.close()


@pytest.fixture
def programs(backend: Backend, tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[Programs]:
    """Entrega el ejecutor de programas y limpia los procesos al terminar."""
    test_name = re.sub(r"\W+", "_", request.node.name).strip("_")
    instance = Programs(backend, tmp_path, test_name)
    yield instance
    instance.stop_all()


@pytest.fixture
def client_uuid() -> str:
    """Identificador de cliente único: la CPU real más un sufijo de la prueba."""
    return f"{uuid.getnode()}-{uuid.uuid4().hex[:8]}"

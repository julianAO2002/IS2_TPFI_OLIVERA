"""Pruebas de la generación de documentación y de lo que exporta el paquete."""

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from scripts import build_docs


def _fake_pdoc(returncode: int = 0) -> subprocess.CompletedProcess[Any]:
    return subprocess.CompletedProcess(args=[], returncode=returncode)


def _create_pages(folder: Path, pages: list[str]) -> None:
    for page in pages:
        target = folder / page
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("<html></html>", encoding="utf-8")


def test_con_todas_las_paginas_termina_bien(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build_docs, "OUTPUT", tmp_path)
    _create_pages(tmp_path, build_docs.REQUIRED_PAGES)
    with patch("subprocess.run", return_value=_fake_pdoc()):
        assert build_docs.main() == 0


def test_si_falta_una_pagina_falla_y_la_nombra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(build_docs, "OUTPUT", tmp_path)
    _create_pages(tmp_path, [p for p in build_docs.REQUIRED_PAGES if p != "tpfi/server/proxy.html"])
    with patch("subprocess.run", return_value=_fake_pdoc()):
        assert build_docs.main() == 1
    assert "tpfi/server/proxy.html" in capsys.readouterr().err


def test_si_falla_pdoc_devuelve_su_codigo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build_docs, "OUTPUT", tmp_path)
    with patch("subprocess.run", return_value=_fake_pdoc(3)):
        assert build_docs.main() == 3


def test_el_paquete_exporta_version_y_subpaquetes() -> None:
    # Sin __all__, la importación con asterisco omite los nombres que empiezan con guion bajo.
    namespace: dict[str, Any] = {}
    exec("from tpfi import *", namespace)  # noqa: S102
    assert {"__version__", "__build__", "clients", "common", "persistence", "server"} <= set(namespace)

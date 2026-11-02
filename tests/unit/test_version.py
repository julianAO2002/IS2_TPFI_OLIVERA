"""Pruebas del registro de VERSION y BUILD."""

import re
import tomllib
from pathlib import Path

import tpfi

ROOT = Path(__file__).resolve().parents[2]


def test_version_y_build_se_leen_de_los_archivos_de_la_raiz() -> None:
    assert tpfi.__version__ == (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert tpfi.__build__ == (ROOT / "BUILD").read_text(encoding="utf-8").strip()


def test_version_tiene_formato_semantico() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", tpfi.__version__)


def test_build_es_un_numero() -> None:
    assert tpfi.__build__.isdigit()


def test_pyproject_declara_la_misma_version() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == tpfi.__version__

"""Ejecuta en orden todos los controles de calidad exigidos por el enunciado.

Sirve para repetir localmente lo mismo que hace el workflow de CI. Uso:

    python scripts/quality.py
"""

# Solo se ejecutan herramientas fijas del proyecto.
import subprocess  # nosec B404
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROGRAMS = ["singletonclient.py", "observerclient.py", "singletonproxyobserver.py"]

# Cada control es un nombre y el módulo de Python que lo ejecuta con sus argumentos.
CHECKS: list[tuple[str, list[str]]] = [
    ("ruff", ["ruff", "check", "."]),
    ("black", ["black", "--check", "."]),
    (
        "pycodestyle",
        ["pycodestyle", "--max-line-length=120", "--ignore=E203,W503", "src", "tests", "scripts", *PROGRAMS],
    ),
    ("pydocstyle", ["pydocstyle", "--convention=pep257", "src", "scripts", *PROGRAMS]),
    ("mypy", ["mypy"]),
    ("pyright", ["pyright"]),
    ("bandit", ["bandit", "-q", "-c", "pyproject.toml", "-r", "src", "scripts", *PROGRAMS]),
    ("pytest", ["pytest", "--cov", "--cov-report=term-missing", "--cov-fail-under=85", "-q"]),
]


def main() -> int:
    """Corre todos los controles y devuelve 0 solo si todos pasan."""
    failed: list[str] = []
    for name, arguments in CHECKS:
        print(f"\n=== {name} ===", flush=True)
        command = [sys.executable, "-m", *arguments]
        if subprocess.run(command, cwd=ROOT, check=False).returncode != 0:  # nosec B603
            failed.append(name)
    print("\n=== Resumen ===")
    print("Fallaron: " + ", ".join(failed) if failed else "Todos los controles pasaron.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

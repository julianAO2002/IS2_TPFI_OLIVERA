"""Resume la salida de la acción "list": cantidad de registros y los propios del alumno."""

import json
import sys
from pathlib import Path

records = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(f"Tipo: {type(records).__name__}; registros: {len(records)}")
print("Registros de este trabajo:", [r["id"] for r in records if r["id"] in ("OLIVERA-TPFI-DEMO", "UADER-FCyT-IS2")])

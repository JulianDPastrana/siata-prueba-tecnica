"""El dashboard abre sin errores con enlaces normales y raros (necesita las salidas del pipeline; en CI se salta)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from siata.datos import DIR_SALIDAS

DASHBOARD = Path(__file__).resolve().parents[1] / "dashboard.py"


@pytest.mark.skipif(not (DIR_SALIDAS / "minutal_367.parquet").exists(), reason="sin salidas del pipeline")
@pytest.mark.parametrize("enlace", [
    {},
    {"estacion": "803", "desde": "2025-12-02", "hasta": "2025-12-09"},
    {"desde": "x", "hasta": "2025-12-09"},  # fecha ilegible
    {"desde": "", "hasta": "2025-12-09"},  # vacía (NaT)
    {"estacion": "367", "desde": "2025-11-30", "hasta": "2026-05-01"},  # fuera del periodo de la 367
])
def test_dashboard_abre_con_cualquier_enlace(enlace):
    at = AppTest.from_file(str(DASHBOARD), default_timeout=120)
    for k, v in enlace.items():
        at.query_params[k] = v
    at.run()
    assert not at.exception

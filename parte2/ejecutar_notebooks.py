"""Ejecuta los notebooks de parte2/notebooks en orden y guarda sus salidas.

    python parte2/ejecutar_notebooks.py            (todos)
    python parte2/ejecutar_notebooks.py 06 07      (solo los que empiezan así)
"""
import asyncio
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

if sys.platform == "win32":  # zmq necesita este bucle de eventos en Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

CARPETA = Path(__file__).resolve().parent / "notebooks"

if __name__ == "__main__":
    filtros = sys.argv[1:]
    for ruta in sorted(CARPETA.glob("*.ipynb")):
        if filtros and not any(ruta.name.startswith(f) for f in filtros):
            continue
        print(f"ejecutando {ruta.name} ...", flush=True)
        nb = nbformat.read(ruta, as_version=4)
        NotebookClient(nb, timeout=1800, kernel_name="python3", resources={"metadata": {"path": str(CARPETA)}}).execute()
        nbformat.write(nb, ruta)

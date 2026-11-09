"""
empaquetar_contexto.py
Arma un .zip liviano del proyecto para compartirlo con el chat de Claude que asesora el
proyecto: código, documentos, figuras y tablas resumen. No incluye datos/crudos (~400 MB)
ni las tablas procesadas grandes (se regeneran con los scripts 01 a 07).

El .zip queda en la carpeta que contiene a seguro_parametrico, con la fecha en el nombre.
Uso:  python scripts/empaquetar_contexto.py
"""
import datetime as dt
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
MAX_MB_PROCESADO = 1.0  # tablas procesadas más grandes que esto quedan por fuera

# Archivos y carpetas que siempre van (rutas relativas a seguro_parametrico)
SIEMPRE = ["README.md", "requirements.txt", "app.py", "scripts", "docs", "notebooks",
           "datos/crudos/registro_descargas.csv"]


def archivos_a_incluir():
    incluidos = []
    for ruta in SIEMPRE:
        p = RAIZ / ruta
        incluidos += [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file())
    excluidos = []
    for p in sorted((RAIZ / "datos" / "procesados").glob("*")):
        (incluidos if p.stat().st_size / 1e6 <= MAX_MB_PROCESADO else excluidos).append(p)
    # Sin cachés de Python
    incluidos = [p for p in incluidos if "__pycache__" not in p.parts]
    return incluidos, excluidos


def leeme(incluidos, excluidos, hoy):
    """Nota corta para quien recibe el .zip."""
    lineas = [
        f"# Contexto del proyecto seguro_parametrico ({hoy})",
        "",
        "Paquete liviano para revisar el proyecto. Empieza por `README.md` y `docs/bitacora.md`:",
        "la bitácora tiene, por sesión, lo que se hizo, los resultados, lo que falló y lo pendiente.",
        "",
        f"## Incluido ({len(incluidos)} archivos)",
        "",
        *[f"- `{p.relative_to(RAIZ).as_posix()}`" for p in incluidos],
        "",
        "## No incluido",
        "",
        "- `datos/crudos/`: descargas originales (~400 MB). Las fuentes, URLs y fechas están en"
        " `README.md` y `datos/crudos/registro_descargas.csv`.",
        *[f"- `{p.relative_to(RAIZ).as_posix()}` ({p.stat().st_size / 1e6:.1f} MB): se regenera con los scripts"
          for p in excluidos],
    ]
    return "\n".join(lineas) + "\n"


def main():
    hoy = dt.date.today().isoformat()
    destino = RAIZ.parent / f"contexto_seguro_parametrico_{hoy}.zip"
    incluidos, excluidos = archivos_a_incluir()
    print(f"📥 Empaquetando {len(incluidos)} archivos ({len(excluidos)} tablas grandes quedan por fuera)...")
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("seguro_parametrico/LEEME_CONTEXTO.md", leeme(incluidos, excluidos, hoy))
        for p in incluidos:
            z.write(p, "seguro_parametrico/" + p.relative_to(RAIZ).as_posix())
    print(f"✅ Listo: {destino} ({destino.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()

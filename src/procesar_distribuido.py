import os
import time
from multiprocessing import Pool
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def _procesar_chunk(chunk: pd.DataFrame) -> dict:
    """Fase Map (Worker): procesa un bloque independiente del CSV y retorna agregaciones parciales."""
    chunk = chunk.copy()
    chunk["ingreso"] = chunk["cantidad"] * chunk["precio_unitario"]
    chunk["mes"] = pd.to_datetime(chunk["fecha"]).dt.to_period("M").astype(str)

    # Agregaciones locales del bloque asignado al worker
    ciudad_parcial = chunk.groupby("ciudad")["ingreso"].sum().to_dict()
    producto_parcial = chunk.groupby("producto")["cantidad"].sum().to_dict()

    mes_df = chunk.groupby("mes").agg(
        ingreso_total=("ingreso", "sum"),
        cantidad_total=("cantidad", "sum"),
        transacciones=("id_venta", "count"),
    )
    mes_parcial = mes_df.to_dict(orient="index")

    return {
        "ciudad": ciudad_parcial,
        "producto": producto_parcial,
        "mes": mes_parcial,
        "filas": len(chunk),
        "ingreso_parcial": float(chunk["ingreso"].sum()),
    }


def _consolidar_resultados(resultados_parciales: list[dict]) -> dict:
    """Fase Reduce (Coordinador): unifica los diccionarios parciales de todos los workers."""
    acum_ciudad: dict[str, float] = {}
    acum_producto: dict[str, int] = {}
    acum_mes: dict[str, dict[str, float | int]] = {}
    total_registros = 0
    ingreso_global = 0.0

    # Acumulación de métricas parciales por clave (ciudad, producto y mes)
    for parcial in resultados_parciales:
        total_registros += parcial["filas"]
        ingreso_global += parcial["ingreso_parcial"]

        for ciudad, val in parcial["ciudad"].items():
            acum_ciudad[ciudad] = acum_ciudad.get(ciudad, 0.0) + float(val)

        for prod, cant in parcial["producto"].items():
            acum_producto[prod] = acum_producto.get(prod, 0) + int(cant)

        for mes, metrics in parcial["mes"].items():
            if mes not in acum_mes:
                acum_mes[mes] = {
                    "ingreso_total": 0.0,
                    "cantidad_total": 0,
                    "transacciones": 0,
                }
            acum_mes[mes]["ingreso_total"] += float(metrics["ingreso_total"])
            acum_mes[mes]["cantidad_total"] += int(metrics["cantidad_total"])
            acum_mes[mes]["transacciones"] += int(metrics["transacciones"])

    # Conversión de resultados consolidados a DataFrames ordenados
    ingresos_por_ciudad = (
        pd.DataFrame([{"ciudad": k, "ingreso": v} for k, v in acum_ciudad.items()])
        .sort_values("ingreso", ascending=False)
        .reset_index(drop=True)
    )

    top_5_productos = (
        pd.DataFrame([{"producto": k, "cantidad": v} for k, v in acum_producto.items()])
        .sort_values("cantidad", ascending=False)
        .head(5)
        .reset_index(drop=True)
    )

    ventas_por_mes = (
        pd.DataFrame(
            [
                {
                    "mes": mes,
                    "ingreso_total": vals["ingreso_total"],
                    "cantidad_total": vals["cantidad_total"],
                    "transacciones": vals["transacciones"],
                }
                for mes, vals in acum_mes.items()
            ]
        )
        .sort_values("mes", ascending=True)
        .reset_index(drop=True)
    )

    return {
        "ingresos_por_ciudad": ingresos_por_ciudad,
        "top_5_productos": top_5_productos,
        "ventas_por_mes": ventas_por_mes,
        "total_registros": total_registros,
        "ingreso_global": ingreso_global,
    }


def ejecutar_distribuido(
    ruta_csv: Path,
    num_workers: int | None = None,
    chunksize: int = 25_000,
    mostrar_detalle: bool = True,
) -> dict:
    """Particiona el CSV en chunks, los distribuye en un Pool de procesos y consolida salidas."""
    if num_workers is None:
        num_workers = max(2, min(os.cpu_count() or 2, 8))

    inicio = time.perf_counter()
    # Lectura particionada en bloques de tamaño fijo
    chunks = list(pd.read_csv(ruta_csv, chunksize=chunksize))

    # Ejecución paralela de los bloques en procesos independientes
    with Pool(processes=num_workers) as pool:
        parciales = pool.map(_procesar_chunk, chunks)

    resultados = _consolidar_resultados(parciales)
    fin = time.perf_counter()

    tiempo_seg = fin - inicio
    resultados["tiempo_seg"] = tiempo_seg
    resultados["archivo"] = ruta_csv.name
    resultados["num_workers"] = num_workers
    resultados["num_chunks"] = len(chunks)

    if mostrar_detalle:
        print(
            f"\n=== DISTRIBUIDO ({num_workers} procesos, {len(chunks)} chunks) | "
            f"{ruta_csv.name} ({resultados['total_registros']:,} filas) ==="
        )
        print(f"Tiempo total: {tiempo_seg:.4f} s | Ingreso global: ${resultados['ingreso_global']:,.2f}")
        print("\n-- Ingresos por ciudad --")
        print(resultados["ingresos_por_ciudad"].to_string(index=False))
        print("\n-- Top 5 productos por cantidad --")
        print(resultados["top_5_productos"].to_string(index=False))
        print("\n-- Ventas por mes --")
        print(resultados["ventas_por_mes"].to_string(index=False))

    return resultados


if __name__ == "__main__":
    ejecutar_distribuido(DATA_DIR / "ventas_10k.csv", mostrar_detalle=True)
import time
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def analizar_df(df: pd.DataFrame) -> dict:
    """Calcula las métricas de negocio (ciudad, top productos y mes) sobre un DataFrame completo."""
    df = df.copy()
    # Cálculo de ingreso por línea de venta y extracción del periodo mensual (YYYY-MM)
    df["ingreso"] = df["cantidad"] * df["precio_unitario"]
    df["mes"] = pd.to_datetime(df["fecha"]).dt.to_period("M").astype(str)

    # 1. Ingresos totales agrupados por ciudad
    ingresos_por_ciudad = (
        df.groupby("ciudad", as_index=False)["ingreso"]
        .sum()
        .sort_values("ingreso", ascending=False)
    )

    # 2. Top 5 productos más vendidos según cantidad de unidades
    top_5_productos = (
        df.groupby("producto", as_index=False)["cantidad"]
        .sum()
        .sort_values("cantidad", ascending=False)
        .head(5)
    )

    # 3. Resumen mensual de ingresos, unidades y número de transacciones
    ventas_por_mes = (
        df.groupby("mes", as_index=False)
        .agg(
            ingreso_total=("ingreso", "sum"),
            cantidad_total=("cantidad", "sum"),
            transacciones=("id_venta", "count"),
        )
        .sort_values("mes", ascending=True)
    )

    return {
        "ingresos_por_ciudad": ingresos_por_ciudad,
        "top_5_productos": top_5_productos,
        "ventas_por_mes": ventas_por_mes,
        "total_registros": len(df),
        "ingreso_global": float(df["ingreso"].sum()),
    }


def ejecutar_secuencial(ruta_csv: Path, mostrar_detalle: bool = True) -> dict:
    """Lee el CSV completo en un único proceso y mide el tiempo total de ejecución secuencial."""
    inicio = time.perf_counter()
    df = pd.read_csv(ruta_csv)
    resultados = analizar_df(df)
    fin = time.perf_counter()

    tiempo_seg = fin - inicio
    resultados["tiempo_seg"] = tiempo_seg
    resultados["archivo"] = ruta_csv.name

    if mostrar_detalle:
        print(f"\n=== SECUENCIAL | {ruta_csv.name} ({resultados['total_registros']:,} filas) ===")
        print(f"Tiempo total: {tiempo_seg:.4f} s | Ingreso global: ${resultados['ingreso_global']:,.2f}")
        print("\n-- Ingresos por ciudad --")
        print(resultados["ingresos_por_ciudad"].to_string(index=False))
        print("\n-- Top 5 productos por cantidad --")
        print(resultados["top_5_productos"].to_string(index=False))
        print("\n-- Ventas por mes --")
        print(resultados["ventas_por_mes"].to_string(index=False))

    return resultados


if __name__ == "__main__":
    ejecutar_secuencial(DATA_DIR / "ventas_10k.csv", mostrar_detalle=True)
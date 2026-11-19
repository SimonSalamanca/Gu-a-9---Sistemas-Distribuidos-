import os
import platform
import subprocess
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

from procesar_secuencial import ejecutar_secuencial
from procesar_distribuido import ejecutar_distribuido

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

DATASETS = [
    ("10,000", "ventas_10k.csv", 10_000),
    ("100,000", "ventas_100k.csv", 100_000),
    ("500,000", "ventas_500k.csv", 500_000),
]


def obtener_specs_equipo() -> dict:
    """Consulta las características de hardware y software del entorno de ejecución."""
    cpu_nombre = platform.processor() or "Desconocido"
    ram_gb = "Desconocida"
    try:
        out_cpu = subprocess.check_output(
            ["powershell", "-Command", "(Get-CimInstance Win32_Processor).Name"],
            text=True,
        ).strip()
        if out_cpu:
            cpu_nombre = out_cpu
        out_ram = subprocess.check_output(
            [
                "powershell",
                "-Command",
                "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)",
            ],
            text=True,
        ).strip()
        if out_ram:
            ram_gb = f"{out_ram} GB"
    except Exception:
        pass

    return {
        "Sistema Operativo": f"{platform.system()} {platform.release()} ({platform.version()})",
        "Arquitectura": platform.machine(),
        "Procesador": cpu_nombre,
        "Núcleos lógicos": os.cpu_count(),
        "Memoria RAM": ram_gb,
        "Versión Python": platform.python_version(),
    }


def generar_graficas(df_bench: pd.DataFrame) -> None:
    """Genera y guarda las gráficas comparativas de tiempos y speedup en output/."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Gráfica 1: Comparación de tiempos de ejecución (Secuencial vs. Distribuido)
    fig, ax = plt.subplots(figsize=(9, 5))
    x = range(len(df_bench))
    ancho = 0.35

    b1 = ax.bar(
        [i - ancho / 2 for i in x],
        df_bench["tiempo_secuencial_s"],
        width=ancho,
        label="Secuencial (1 proceso)",
        color="#2b5c8f",
    )
    b2 = ax.bar(
        [i + ancho / 2 for i in x],
        df_bench["tiempo_distribuido_s"],
        width=ancho,
        label=f"Distribuido ({df_bench['workers'].iloc[0]} procesos)",
        color="#2ca02c",
    )

    ax.set_title("Tiempo de Ejecución: Secuencial vs. Distribuido Simulado", fontsize=12, fontweight="bold")
    ax.set_xlabel("Cantidad de registros")
    ax.set_ylabel("Tiempo (segundos)")
    ax.set_xticks(list(x))
    ax.set_xticklabels(df_bench["registros_label"])
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    for bar in list(b1) + list(b2):
        h = bar.get_height()
        ax.annotate(
            f"{h:.3f}s",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "comparacion_tiempos.png", dpi=150)
    plt.close(fig)

    # Gráfica 2: Curva de factor de aceleración (Speedup = Ts / Tp)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(
        df_bench["registros_label"],
        df_bench["aceleracion_speedup"],
        marker="o",
        linewidth=2.5,
        color="#d95f02",
        label="Speedup medido (Ts / Tp)",
    )
    ax.axhline(1.0, color="gray", linestyle="--", linewidth=1, label="Umbral equilibrio (Speedup = 1.0x)")
    ax.set_title("Factor de Aceleración (Speedup) por Volumen de Datos", fontsize=12, fontweight="bold")
    ax.set_xlabel("Cantidad de registros")
    ax.set_ylabel("Aceleración (Ts / Tp)")
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.5)

    for i, row in df_bench.iterrows():
        ax.annotate(
            f"{row['aceleracion_speedup']:.2f}x",
            (row["registros_label"], row["aceleracion_speedup"]),
            textcoords="offset points",
            xytext=(0, 8),
            ha="center",
            fontsize=9,
            fontweight="bold",
        )

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "aceleracion_speedup.png", dpi=150)
    plt.close(fig)


def main() -> None:
    """Orquesta las pruebas comparativas, valida consistencia y exporta resultados y gráficas."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    num_workers = max(2, min(os.cpu_count() or 2, 8))

    specs = obtener_specs_equipo()
    print("=== ESPECIFICACIONES DEL EQUIPO DE PRUEBA ===")
    for k, v in specs.items():
        print(f"- {k}: {v}")

    filas_resultados = []
    ultimo_dist = None

    # Ejecución secuencial y distribuida sobre cada volumen de datos
    for label, archivo, num_filas in DATASETS:
        ruta = DATA_DIR / archivo
        chunksize = max(2_500, num_filas // (num_workers * 2))

        print(f"\nEjecutando pruebas para {label} registros ({archivo})...")
        res_sec = ejecutar_secuencial(ruta, mostrar_detalle=False)
        res_dist = ejecutar_distribuido(
            ruta,
            num_workers=num_workers,
            chunksize=chunksize,
            mostrar_detalle=False,
        )

        # Verificación de igualdad numérica entre ambos métodos
        diff_ingreso = abs(res_sec["ingreso_global"] - res_dist["ingreso_global"])
        assert diff_ingreso < 1e-2, f"Discrepancia en ingreso global: {diff_ingreso}"

        ts = res_sec["tiempo_seg"]
        tp = res_dist["tiempo_seg"]
        speedup = ts / tp if tp > 0 else 0.0
        eficiencia = (speedup / num_workers) * 100

        filas_resultados.append(
            {
                "registros_label": label,
                "num_registros": num_filas,
                "archivo": archivo,
                "workers": num_workers,
                "chunks": res_dist["num_chunks"],
                "tiempo_secuencial_s": round(ts, 4),
                "tiempo_distribuido_s": round(tp, 4),
                "aceleracion_speedup": round(speedup, 4),
                "eficiencia_pct": round(eficiencia, 2),
                "ingreso_global": round(res_dist["ingreso_global"], 2),
            }
        )
        ultimo_dist = res_dist

    # Exportación de la tabla comparativa a CSV
    df_bench = pd.DataFrame(filas_resultados)
    df_bench.to_csv(OUTPUT_DIR / "resultados_benchmark.csv", index=False)

    print("\n=== TABLA COMPARATIVA DE RENDIMIENTO ===")
    print(
        df_bench[
            [
                "registros_label",
                "workers",
                "chunks",
                "tiempo_secuencial_s",
                "tiempo_distribuido_s",
                "aceleracion_speedup",
                "eficiencia_pct",
            ]
        ].to_string(index=False)
    )

    # Exportación del reporte consolidado de negocio (500k registros)
    if ultimo_dist is not None:
        reporte_txt = OUTPUT_DIR / "reporte_consolidado_500k.txt"
        with open(reporte_txt, "w", encoding="utf-8") as f:
            f.write("=== REPORTE CONSOLIDADO DE VENTAS (500,000 REGISTROS) ===\n")
            f.write(f"Ingreso Global: ${ultimo_dist['ingreso_global']:,.2f}\n\n")
            f.write("-- Ingresos por Ciudad --\n")
            f.write(ultimo_dist["ingresos_por_ciudad"].to_string(index=False) + "\n\n")
            f.write("-- Top 5 Productos por Cantidad --\n")
            f.write(ultimo_dist["top_5_productos"].to_string(index=False) + "\n\n")
            f.write("-- Ventas por Mes --\n")
            f.write(ultimo_dist["ventas_por_mes"].to_string(index=False) + "\n")

    generar_graficas(df_bench)
    print(f"\nArchivos guardados en: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
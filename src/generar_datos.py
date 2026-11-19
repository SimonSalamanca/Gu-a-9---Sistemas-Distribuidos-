import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

CIUDADES = [
    "Bogotá", "Medellín", "Cali", "Barranquilla", "Cartagena",
    "Bucaramanga", "Pereira", "Manizales", "Santa Marta", "Cúcuta"
]

PRODUCTOS = [
    ("Laptop Pro 14", 3800000),
    ("Monitor 27 FHD", 950000),
    ("Teclado Mecánico", 240000),
    ("Mouse Inalámbrico", 95000),
    ("Audífonos Studio", 320000),
    ("Silla Ergonómica", 780000),
    ("Disco SSD 1TB", 290000),
    ("Cámara Web HD", 180000),
    ("Hub USB-C 7 en 1", 130000),
    ("Base Refrigerante", 85000),
]


def generar_csv(num_registros: int, nombre_archivo: str, seed: int = 42) -> Path:
    """Genera un dataset CSV sintético de ventas con semilla fija para reproducibilidad."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ruta_salida = DATA_DIR / nombre_archivo
    rng = random.Random(seed)

    fecha_inicio = datetime(2025, 1, 1)
    rango_dias = 365

    # Escritura fila por fila del archivo CSV con los 6 campos requeridos
    with open(ruta_salida, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id_venta", "fecha", "ciudad", "producto", "cantidad", "precio_unitario"])

        for i in range(1, num_registros + 1):
            id_venta = f"VTA-{i:07d}"
            fecha = (fecha_inicio + timedelta(days=rng.randint(0, rango_dias - 1))).strftime("%Y-%m-%d")
            ciudad = rng.choice(CIUDADES)
            producto, precio_base = rng.choice(PRODUCTOS)
            cantidad = rng.randint(1, 8)
            # Variación aleatoria de ±5 % sobre el precio base del producto
            variacion = rng.uniform(0.95, 1.05)
            precio_unitario = round(precio_base * variacion, 2)

            writer.writerow([id_venta, fecha, ciudad, producto, cantidad, precio_unitario])

    print(f"Generado: {ruta_salida} ({num_registros:,} registros)")
    return ruta_salida


if __name__ == "__main__":
    # Generación de los tres volúmenes de prueba (10k, 100k y 500k registros)
    generar_csv(10_000, "ventas_10k.csv", seed=101)
    generar_csv(100_000, "ventas_100k.csv", seed=102)
    generar_csv(500_000, "ventas_500k.csv", seed=103)
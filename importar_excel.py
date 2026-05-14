import pandas as pd
import streamlit as st

DEFAULT_DATASET_PATH = "dataset_taller_2022_2026.csv"

# Columns expected in the monthly Excel export
EXCEL_COLUMNS = [
    "Orden", "Patente", "Modelo", "Año", "Vendido por", "Nro Motor",
    "Nro Chasis", "Tipo Servicio", "Fecha", "Nro Serv", "Km",
    "Observaciones", "Técnico", "Recepcionista", "T.doc", "Nro Doc",
    "Nombre", "Apellido", "Area", "Celular", "Email",
]

# Final column order matching dataset_taller_2022_2026.csv
CSV_COLUMNS = [
    "Orden", "Patente", "Modelo", "Año de compra", "Nro Motor", "Nro Chasis",
    "Tipo Servicio", "Fecha", "Nro Serv", "Km", "Observaciones", "Técnico",
    "Recepcionista", "T.doc", "Nro Doc", "Nombre", "Apellido", "Area",
    "Celular", "Email", "Cliente de AGM Motos SRL",
]


def _detectar_header(xl_file):
    """Find which row contains the real column headers (looks for 'Orden')."""
    for skip in range(6):
        try:
            df = pd.read_excel(xl_file, header=skip, nrows=1)
            if "Orden" in df.columns or any("Orden" in str(c) for c in df.columns):
                return skip
        except Exception:
            pass
    return 2  # fallback to row 2


def parsear_excel(archivo):
    """
    Parse a monthly taller Excel file and return a DataFrame
    with the same columns as the main CSV dataset.
    """
    skip = _detectar_header(archivo)
    df = pd.read_excel(archivo, header=skip)

    # Normalize column names (strip whitespace)
    df.columns = [str(c).strip() for c in df.columns]

    # Drop fully-empty rows
    df = df.dropna(how="all")

    # Validate required columns exist
    missing = [c for c in EXCEL_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"El Excel no tiene las columnas esperadas: {missing}")

    # Keep only the Excel columns we care about
    df = df[EXCEL_COLUMNS].copy()

    # --- Transformations ---

    # Año → Año de compra (convert float like 2026.0 → 2026)
    df["Año de compra"] = pd.to_numeric(df["Año"], errors="coerce").astype("Int64")
    df = df.drop(columns=["Año"])

    # Vendido por → Cliente de AGM Motos SRL (SI / NO)
    df["Cliente de AGM Motos SRL"] = df["Vendido por"].apply(
        lambda x: "SI" if pd.notna(x) and "AGM MOTOS SRL" in str(x).upper() else "NO"
    )
    df = df.drop(columns=["Vendido por"])

    # Orden: drop rows without a numeric Orden
    df["Orden"] = pd.to_numeric(df["Orden"], errors="coerce")
    df = df.dropna(subset=["Orden"])
    df["Orden"] = df["Orden"].astype(int)

    # Fecha: ensure DD/MM/YYYY string format
    if pd.api.types.is_datetime64_any_dtype(df["Fecha"]):
        df["Fecha"] = df["Fecha"].dt.strftime("%d/%m/%Y")
    else:
        df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce").dt.strftime("%d/%m/%Y")

    # Nro Serv: keep as integer where possible
    df["Nro Serv"] = pd.to_numeric(df["Nro Serv"], errors="coerce").astype("Int64")

    # Km: keep as integer where possible
    df["Km"] = pd.to_numeric(df["Km"], errors="coerce").astype("Int64")

    return df[CSV_COLUMNS]


def render_importar_excel(dataset_path=DEFAULT_DATASET_PATH):
    st.header("Importar Excel mensual")
    st.write(
        "Subí el archivo Excel del mes para incorporar los registros nuevos al dataset. "
        "El programa detecta automáticamente qué filas ya existen y agrega solo las nuevas."
    )

    archivo = st.file_uploader(
        "Seleccioná el Excel mensual (.xlsx)",
        type=["xlsx", "xls"],
        help="El archivo debe tener el formato estándar de exportación del sistema de taller.",
    )

    if archivo is None:
        return

    # --- Parse Excel ---
    try:
        df_nuevo = parsear_excel(archivo)
    except ValueError as e:
        st.error(str(e))
        return
    except Exception as e:
        st.error(f"No se pudo leer el archivo: {e}")
        return

    # --- Load existing dataset ---
    try:
        df_csv = pd.read_csv(dataset_path, encoding="utf-8-sig", sep=";", low_memory=False)
        ordenes_existentes = set(pd.to_numeric(df_csv["Orden"], errors="coerce").dropna().astype(int))
    except FileNotFoundError:
        st.error(f"No se encontró el dataset en: {dataset_path}")
        return

    # --- Split new vs duplicate ---
    es_duplicado = df_nuevo["Orden"].isin(ordenes_existentes)
    df_nuevos = df_nuevo[~es_duplicado].reset_index(drop=True)
    df_duplicados = df_nuevo[es_duplicado].reset_index(drop=True)

    # --- Summary metrics ---
    st.subheader("Resumen")
    col1, col2, col3 = st.columns(3)
    col1.metric("Filas en el Excel", len(df_nuevo))
    col2.metric("Ya existían", len(df_duplicados), delta=None)
    col3.metric("Nuevas a agregar", len(df_nuevos))

    if len(df_nuevos) == 0:
        st.warning("Todos los registros del Excel ya están en el dataset. No hay nada nuevo para agregar.")
        return

    # --- Preview ---
    st.subheader("Vista previa de los registros nuevos")
    st.dataframe(df_nuevos, use_container_width=True)

    if len(df_duplicados) > 0:
        with st.expander(f"Ver {len(df_duplicados)} registros ya existentes (no se agregarán)"):
            st.dataframe(df_duplicados, use_container_width=True)

    # --- Distribution info ---
    if "Cliente de AGM Motos SRL" in df_nuevos.columns:
        agm = (df_nuevos["Cliente de AGM Motos SRL"] == "SI").sum()
        otros = len(df_nuevos) - agm
        st.caption(f"De los {len(df_nuevos)} registros nuevos: {agm} clientes AGM Motos SRL, {otros} de otros concesionarios.")

    st.divider()

    # --- Confirm and append ---
    if st.button(f"Agregar {len(df_nuevos)} registros al dataset", type="primary"):
        try:
            df_nuevos.to_csv(
                dataset_path,
                mode="a",
                header=False,
                index=False,
                sep=";",
                encoding="utf-8",  # no BOM on append — BOM only at file start
            )
            st.success(f"Se agregaron {len(df_nuevos)} registros correctamente al dataset.")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Error al guardar: {e}")

import re

import pandas as pd
import plotly.express as px
import streamlit as st


DEFAULT_DATASET_PATH = "dataset_taller.csv"


def limpiar_telefono(x):
    if pd.isna(x):
        return None
    x = re.sub(r"[^0-9]", "", str(x))
    return x if len(x) >= 6 else None


def etiquetar_etapa_service(valor):
    numero = pd.to_numeric(valor, errors="coerce")
    if pd.isna(numero):
        return "Sin etapa informada"

    numero = int(numero)
    if numero == 1:
        return "1° service (<1.000 km)"
    return f"{numero}° service"


@st.cache_data
def leer_dataset(path=DEFAULT_DATASET_PATH):
    cols = [
        "orden",
        "patente",
        "modelo",
        "anio",
        "vendido_por",
        "nro_motor",
        "nro_chasis",
        "tipo_servicio",
        "fecha",
        "nro_serv",
        "km",
        "observaciones",
        "tecnico",
        "recepcionista",
        "t_doc",
        "nro_doc",
        "nombre",
        "apellido",
        "area",
        "celular",
        "email",
    ]

    df = pd.read_csv(
        path,
        delimiter=";",
        encoding="utf-8",
        skiprows=1,
        names=cols,
        na_values=["", "NA", "NULL"],
    )

    df["fecha"] = pd.to_datetime(df["fecha"], format="%d/%m/%Y", errors="coerce")
    df["km"] = pd.to_numeric(df["km"], errors="coerce")
    df["anio"] = pd.to_numeric(df["anio"], errors="coerce")
    df["nro_serv"] = pd.to_numeric(df["nro_serv"], errors="coerce")
    df["celular_limpio"] = df["celular"].apply(limpiar_telefono)
    df["cliente"] = (df["nombre"].fillna("") + " " + df["apellido"].fillna("")).str.strip()
    df["cliente"] = df["cliente"].replace("", None)
    df["email"] = df["email"].str.strip().str.lower()
    df["modelo"] = df["modelo"].str.strip()
    df["tecnico"] = df["tecnico"].str.strip()
    df["tipo_servicio"] = df["tipo_servicio"].str.strip()
    df["anio_mes"] = df["fecha"].dt.to_period("M").dt.to_timestamp()
    df["semana"] = df["fecha"].dt.to_period("W").dt.to_timestamp()
    df["dia_semana"] = df["fecha"].dt.day_name()
    df["etapa_service"] = df["nro_serv"].apply(etiquetar_etapa_service)

    df["identificador_cliente"] = df.apply(
        lambda row: row["celular_limpio"]
        if pd.notna(row["celular_limpio"])
        else (row["email"] if pd.notna(row["email"]) else None),
        axis=1,
    )

    return df


def calcular_servicios_por_dia(df):
    if df.empty or df["fecha"].dropna().empty:
        return 0.0
    rango_dias = (df["fecha"].max() - df["fecha"].min()).days + 1
    return len(df) / rango_dias if rango_dias > 0 else 0.0


def render_dashboard_dataset(path=DEFAULT_DATASET_PATH):
    df = leer_dataset(path)

    st.title("Dashboard Taller Avant - Analisis Operativo")
    st.markdown("Metricas de tecnicos, volumen de trabajo y etapas de service.")
    st.caption(
        "Referencia: `Nro Serv` indica la etapa o tipo de service realizado, no la cantidad de veces que el cliente regreso."
    )

    st.sidebar.header("Filtros")
    fecha_min = df["fecha"].min().date()
    fecha_max = df["fecha"].max().date()
    rango_fecha = st.sidebar.date_input(
        "Rango de fechas",
        [fecha_min, fecha_max],
        min_value=fecha_min,
        max_value=fecha_max,
        key="dataset_rango_fecha",
    )

    tipo_servicio = st.sidebar.selectbox(
        "Tipo de servicio",
        ["Todos"] + sorted(df["tipo_servicio"].dropna().unique().tolist()),
        key="dataset_tipo_servicio",
    )
    etapa_service = st.sidebar.selectbox(
        "Etapa de service",
        ["Todas"] + sorted(df["etapa_service"].dropna().unique().tolist()),
        key="dataset_etapa_service",
    )
    tecnico = st.sidebar.selectbox(
        "Tecnico",
        ["Todos"] + sorted(df["tecnico"].dropna().unique().tolist()),
        key="dataset_tecnico",
    )
    modelo = st.sidebar.selectbox(
        "Modelo",
        ["Todos"] + sorted(df["modelo"].dropna().unique().tolist()),
        key="dataset_modelo",
    )
    anio = st.sidebar.selectbox(
        "Anio",
        ["Todos"] + sorted(df["anio"].dropna().astype(int).tolist()),
        key="dataset_anio",
    )

    df_filtrado = df.copy()
    if rango_fecha:
        df_filtrado = df_filtrado[
            (df_filtrado["fecha"] >= pd.to_datetime(rango_fecha[0]))
            & (df_filtrado["fecha"] <= pd.to_datetime(rango_fecha[1]))
        ]
    if tipo_servicio != "Todos":
        df_filtrado = df_filtrado[df_filtrado["tipo_servicio"] == tipo_servicio]
    if etapa_service != "Todas":
        df_filtrado = df_filtrado[df_filtrado["etapa_service"] == etapa_service]
    if tecnico != "Todos":
        df_filtrado = df_filtrado[df_filtrado["tecnico"] == tecnico]
    if modelo != "Todos":
        df_filtrado = df_filtrado[df_filtrado["modelo"] == modelo]
    if anio != "Todos":
        df_filtrado = df_filtrado[df_filtrado["anio"] == anio]

    servicios_total = len(df_filtrado)
    clientes_ident = df_filtrado["identificador_cliente"].dropna().nunique()
    km_promedio = df_filtrado["km"].mean() if servicios_total else 0
    modelos_unicos = df_filtrado["modelo"].nunique()
    recurrentes = (
        df_filtrado.dropna(subset=["identificador_cliente"])
        .groupby("identificador_cliente")
        .size()
        .gt(1)
        .sum()
    )
    tecnicos_activos = df_filtrado["tecnico"].nunique()
    servicios_por_dia = calcular_servicios_por_dia(df_filtrado)
    pct_mantenimiento = (
        (df_filtrado["tipo_servicio"] == "Mantenimiento Obligatorio").mean() * 100
        if servicios_total
        else 0
    )

    etapa_top = (
        df_filtrado["etapa_service"].mode().iloc[0]
        if not df_filtrado["etapa_service"].dropna().empty
        else "Sin datos"
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Servicios totales", f"{servicios_total:,}".replace(",", "."))
    with col2:
        st.metric("Clientes identificados", f"{clientes_ident:,}".replace(",", "."))
    with col3:
        st.metric("Km promedio", f"{km_promedio:,.0f}".replace(",", "."))
    with col4:
        st.metric("Modelos atendidos", f"{modelos_unicos:,}".replace(",", "."))

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric("Clientes recurrentes", f"{recurrentes:,}".replace(",", "."))
    with col6:
        st.metric("Tecnicos activos", f"{tecnicos_activos:,}".replace(",", "."))
    with col7:
        st.metric("Servicios/dia promedio", f"{servicios_por_dia:.1f}")
    with col8:
        st.metric("Etapa mas frecuente", etapa_top)

    st.header("Evolucion y Analisis Operativo")

    col1, col2 = st.columns(2)
    with col1:
        servicios_mes = df_filtrado.groupby("anio_mes").agg({"orden": "count"}).reset_index()
        fig_serv = px.line(
            servicios_mes,
            x="anio_mes",
            y="orden",
            markers=True,
            title="Evolucion mensual de servicios",
            labels={"anio_mes": "Mes", "orden": "Servicios"},
        )
        st.plotly_chart(fig_serv, width="stretch")

    with col2:
        dias_semana = df_filtrado["dia_semana"].value_counts().reset_index()
        dias_semana.columns = ["dia", "servicios"]
        orden_dias = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        dias_semana["dia"] = pd.Categorical(dias_semana["dia"], categories=orden_dias, ordered=True)
        dias_semana = dias_semana.sort_values("dia")
        fig_dias = px.bar(
            dias_semana,
            x="dia",
            y="servicios",
            title="Servicios por dia de la semana",
            labels={"dia": "Dia", "servicios": "Cantidad"},
        )
        st.plotly_chart(fig_dias, width="stretch")

    st.subheader("Top modelos por cantidad de servicios")
    top_modelos = (
        df_filtrado.groupby("modelo")
        .agg({"orden": "count", "km": "mean"})
        .reset_index()
        .sort_values("orden", ascending=False)
        .head(10)
    )
    fig_top_mod = px.bar(
        top_modelos,
        x="orden",
        y="modelo",
        orientation="h",
        title="Top 10 modelos por servicios",
        labels={"orden": "Servicios", "modelo": "Modelo"},
        hover_data=["km"],
    )
    st.plotly_chart(fig_top_mod, width="stretch")

    st.header("Analisis por Etapa y Tecnico")
    col1, col2 = st.columns(2)

    with col1:
        etapas = (
            df_filtrado.groupby("etapa_service")
            .agg(servicios=("orden", "count"), km_promedio=("km", "mean"))
            .reset_index()
            .sort_values("servicios", ascending=False)
        )
        fig_etapas = px.bar(
            etapas,
            x="servicios",
            y="etapa_service",
            orientation="h",
            title="Distribucion por etapa de service",
            labels={"servicios": "Servicios", "etapa_service": "Etapa"},
            hover_data=["km_promedio"],
        )
        st.plotly_chart(fig_etapas, width="stretch")

    with col2:
        tecnicos = (
            df_filtrado.groupby("tecnico")
            .agg(servicios=("orden", "count"))
            .reset_index()
            .sort_values("servicios", ascending=False)
        )
        fig_tec = px.bar(
            tecnicos,
            x="servicios",
            y="tecnico",
            orientation="h",
            title="Servicios por tecnico",
            labels={"servicios": "Servicios", "tecnico": "Tecnico"},
        )
        st.plotly_chart(fig_tec, width="stretch")

    col1, col2 = st.columns(2)
    with col1:
        tecnicos_fecha = df_filtrado.groupby(["tecnico", "fecha"]).size().reset_index(name="servicios_dia")
        eficiencia_tec = (
            tecnicos_fecha.groupby("tecnico")["servicios_dia"]
            .mean()
            .reset_index()
            .sort_values("servicios_dia", ascending=False)
        )
        fig_ef = px.bar(
            eficiencia_tec,
            x="servicios_dia",
            y="tecnico",
            orientation="h",
            title="Eficiencia promedio por tecnico",
            labels={"servicios_dia": "Servicios/dia promedio", "tecnico": "Tecnico"},
        )
        st.plotly_chart(fig_ef, width="stretch")

    with col2:
        km_etapa = (
            df_filtrado.groupby("etapa_service")
            .agg(km_promedio=("km", "mean"), servicios=("orden", "count"))
            .reset_index()
            .sort_values("km_promedio", ascending=False)
        )
        fig_km_etapa = px.bar(
            km_etapa,
            x="km_promedio",
            y="etapa_service",
            orientation="h",
            title="Km promedio por etapa de service",
            labels={"km_promedio": "Km promedio", "etapa_service": "Etapa"},
            hover_data=["servicios"],
        )
        st.plotly_chart(fig_km_etapa, width="stretch")

    st.header("Fidelizacion de Clientes")
    col1, col2 = st.columns(2)

    visitas_cliente = (
        df_filtrado.dropna(subset=["identificador_cliente"])
        .groupby("identificador_cliente")
        .size()
        .reset_index(name="visitas")
    )

    with col1:
        nuevos = (visitas_cliente["visitas"] == 1).sum()
        recurrentes_count = (visitas_cliente["visitas"] > 1).sum()
        fig_clientes_tipo = px.pie(
            values=[nuevos, recurrentes_count],
            names=["Nuevos", "Recurrentes"],
            title="Clientes nuevos vs recurrentes",
        )
        st.plotly_chart(fig_clientes_tipo, width="stretch")

    with col2:
        freq_visitas = visitas_cliente["visitas"].value_counts().reset_index()
        freq_visitas.columns = ["visitas", "clientes"]
        fig_freq_vis = px.bar(
            freq_visitas,
            x="visitas",
            y="clientes",
            title="Frecuencia de visitas por cliente",
            labels={"visitas": "Numero de visitas", "clientes": "Cantidad de clientes"},
        )
        st.plotly_chart(fig_freq_vis, width="stretch")

    st.subheader("Clientes recurrentes")
    clientes_rec = (
        df_filtrado.dropna(subset=["identificador_cliente"])
        .groupby("identificador_cliente")
        .agg(
            cliente=("cliente", lambda x: x.dropna().iloc[0] if not x.dropna().empty else ""),
            email=("email", lambda x: x.dropna().iloc[0] if not x.dropna().empty else ""),
            modelo=("modelo", lambda x: x.mode().iloc[0] if not x.mode().empty else ""),
            etapa_service=("etapa_service", lambda x: x.dropna().iloc[-1] if not x.dropna().empty else ""),
            fecha=("fecha", "max"),
            orden=("orden", "count"),
        )
        .reset_index()
    )
    clientes_rec["visitas"] = clientes_rec["orden"]
    clientes_rec = clientes_rec[clientes_rec["visitas"] > 1].sort_values("visitas", ascending=False)
    clientes_rec["fecha"] = clientes_rec["fecha"].dt.strftime("%d/%m/%Y")
    clientes_rec = clientes_rec[
        ["cliente", "identificador_cliente", "email", "modelo", "etapa_service", "visitas", "fecha"]
    ]
    clientes_rec.columns = [
        "Cliente",
        "Contacto",
        "Email",
        "Modelo frecuente",
        "Ultima etapa de service",
        "Visitas",
        "Ultima visita",
    ]
    st.dataframe(clientes_rec.head(20), use_container_width=True)

    st.header("Hallazgos Estrategicos")
    pct_rec = recurrentes / clientes_ident if clientes_ident > 0 else 0
    top_modelo = df_filtrado["modelo"].value_counts().index[0] if servicios_total else "N/A"
    dias_mas_activos = (
        dias_semana.nlargest(2, "servicios")["dia"].astype(str).tolist()
        if not df_filtrado.empty
        else []
    )

    st.markdown("### Metricas clave")
    st.write(f"- Se realizaron **{servicios_total}** servicios en el periodo seleccionado.")
    st.write(f"- El **{pct_rec:.1%}** de los clientes identificados son recurrentes.")
    st.write(f"- Se atienden en promedio **{servicios_por_dia:.1f}** servicios por dia.")
    st.write(f"- La etapa mas frecuente fue **{etapa_top}**.")
    st.write(f"- El modelo mas atendido es **{top_modelo}**.")
    st.write(f"- Los dias mas activos son: **{', '.join(dias_mas_activos) if dias_mas_activos else 'Sin datos'}**.")

    st.markdown("### Oportunidades de mejora")
    st.write(
        "- Separar comunicacion por etapa de service: primer service, controles intermedios y servicios avanzados."
    )
    st.write(
        "- Reforzar agenda y repuestos para los modelos y etapas con mayor volumen."
    )
    st.write(
        "- Usar la recurrencia real del cliente para fidelizacion, sin confundirla con `Nro Serv`."
    )
    st.write(
        f"- Con **{servicios_por_dia:.1f}** servicios por dia, evaluar capacidad por tecnico en dias pico."
    )


def main():
    st.set_page_config(page_title="Dashboard Taller Avant - Dataset", page_icon="Taller", layout="wide")
    render_dashboard_dataset()


if __name__ == "__main__":
    main()

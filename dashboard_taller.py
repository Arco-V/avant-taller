import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import re

# Configuración de la página
st.set_page_config(page_title="Dashboard Taller Avant", page_icon="🏍️", layout="wide")

# Función para parsear montos
def parse_monto(x):
    if pd.isna(x):
        return 0.0
    x = str(x).replace('.', '').replace(',', '.')
    try:
        return float(x)
    except ValueError:
        return 0.0

# Función para limpiar teléfono
def limpiar_telefono(x):
    if pd.isna(x):
        return None
    x = re.sub(r'[^0-9]', '', str(x))
    return x if len(x) >= 6 else None

# Función para leer y limpiar datos
@st.cache_data
def leer_taller(path):
    cols = [
        "orden", "chasis", "moto", "fecha", "cliente", "mail", "telefono",
        "mo_fija", "mo_extra", "alarma", "repuestos", "total", "service", "mes"
    ]

    df = pd.read_csv(path, delimiter=';', encoding='utf-8', skiprows=1, names=cols, na_values=['', 'NA', 'NULL'])

    df['fecha'] = pd.to_datetime(df['fecha'], format='%d/%m/%Y', errors='coerce')
    df['mo_fija'] = df['mo_fija'].apply(parse_monto)
    df['mo_extra'] = df['mo_extra'].apply(parse_monto)
    df['alarma'] = df['alarma'].apply(parse_monto)
    df['repuestos'] = df['repuestos'].apply(parse_monto)
    df['total'] = df['total'].apply(parse_monto)
    df['telefono_limpio'] = df['telefono'].apply(limpiar_telefono)
    df['cliente'] = df['cliente'].str.strip() if 'cliente' in df else df['cliente']
    df['mail'] = df['mail'].str.strip() if 'mail' in df else df['mail']
    df['moto'] = df['moto'].str.strip() if 'moto' in df else df['moto']
    df['service'] = df['service'].str.strip() if 'service' in df else df['service']
    df['anio_mes'] = df['fecha'].dt.to_period('M').dt.to_timestamp()
    df['semana'] = df['fecha'].dt.to_period('W').dt.to_timestamp()
    df['tiene_repuestos'] = df['repuestos'] > 0
    df['tiene_mo_extra'] = df['mo_extra'] > 0
    df['ingreso_extra'] = df['mo_extra'].fillna(0) + df['repuestos'].fillna(0)
    df['tipo_trabajo'] = df['service'].str.lower().apply(
        lambda x: 'Reparación' if 'reparaci' in str(x) else ('Service' if 'service' in str(x) else 'Otro')
    )

    return df

# Cargar datos
archivo_csv = "taller 2026.csv"
df = leer_taller(archivo_csv)

# Título
st.title("🏍️ Dashboard Taller Avant")
st.markdown("Análisis estratégico de datos de taller de motocicletas")

# Sidebar para filtros
st.sidebar.header("Filtros")
fecha_min = df['fecha'].min().date()
fecha_max = df['fecha'].max().date()
rango_fecha = st.sidebar.date_input("Rango de fechas", [fecha_min, fecha_max], min_value=fecha_min, max_value=fecha_max)

tipo_trabajo = st.sidebar.selectbox("Tipo de trabajo", ["Todos"] + sorted(df['tipo_trabajo'].dropna().unique().tolist()))
service = st.sidebar.selectbox("Service/Reparación", ["Todos"] + sorted(df['service'].dropna().unique().tolist()))
moto = st.sidebar.selectbox("Modelo", ["Todos"] + sorted(df['moto'].dropna().unique().tolist()))

# Filtrar datos
df_filtrado = df.copy()
if rango_fecha:
    df_filtrado = df_filtrado[(df_filtrado['fecha'] >= pd.to_datetime(rango_fecha[0])) & (df_filtrado['fecha'] <= pd.to_datetime(rango_fecha[1]))]
if tipo_trabajo != "Todos":
    df_filtrado = df_filtrado[df_filtrado['tipo_trabajo'] == tipo_trabajo]
if service != "Todos":
    df_filtrado = df_filtrado[df_filtrado['service'] == service]
if moto != "Todos":
    df_filtrado = df_filtrado[df_filtrado['moto'] == moto]

# KPIs
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Facturación total", f"${df_filtrado['total'].sum():,.0f}".replace(",", "."))
with col2:
    st.metric("Órdenes", f"{len(df_filtrado):,}".replace(",", "."))
with col3:
    st.metric("Ticket promedio", f"${df_filtrado['total'].mean():,.0f}".replace(",", "."))
with col4:
    clientes_ident = df_filtrado['telefono_limpio'].dropna().nunique()
    st.metric("Clientes identificados", f"{clientes_ident:,}".replace(",", "."))

col5, col6, col7, col8 = st.columns(4)
with col5:
    recurrentes = df_filtrado.dropna(subset=['telefono_limpio']).groupby('telefono_limpio').size().gt(1).sum()
    st.metric("Clientes recurrentes", f"{recurrentes:,}".replace(",", "."))
with col6:
    pct_rep = df_filtrado['tiene_repuestos'].mean() * 100
    st.metric("% con repuestos", f"{pct_rep:.1f}%")
with col7:
    pct_mo = df_filtrado['tiene_mo_extra'].mean() * 100
    st.metric("% con M.O. extra", f"{pct_mo:.1f}%")
with col8:
    extra_prom = df_filtrado['ingreso_extra'].mean()
    st.metric("Ingreso extra / orden", f"${extra_prom:,.0f}".replace(",", "."))

# Gráficos
st.header("Evolución y Análisis")

col1, col2 = st.columns(2)

with col1:
    # Evolución de facturación
    fact_mes = df_filtrado.groupby('anio_mes').agg({'total': 'sum', 'orden': 'count'}).reset_index()
    fig_fact = px.line(fact_mes, x='anio_mes', y='total', markers=True,
                       title="Evolución de facturación mensual",
                       labels={'anio_mes': 'Mes', 'total': 'Facturación ($)'})
    fig_fact.update_traces(text=fact_mes.apply(lambda row: f"Mes: {row['anio_mes'].strftime('%m/%Y')}<br>Facturación: ${row['total']:,.0f}<br>Órdenes: {row['orden']}", axis=1))
    st.plotly_chart(fig_fact, width='stretch')

with col2:
    # Mix de ingresos
    mix = {
        'M.O. fija': df_filtrado['mo_fija'].sum(),
        'M.O. extra': df_filtrado['mo_extra'].sum(),
        'Alarma': df_filtrado['alarma'].sum(),
        'Repuestos': df_filtrado['repuestos'].sum()
    }
    fig_mix = px.pie(values=list(mix.values()), names=list(mix.keys()), title="Mix de ingresos")
    st.plotly_chart(fig_mix, width='stretch')

# Top modelos
st.subheader("Top modelos por facturación")
top_motos = df_filtrado.groupby('moto').agg({'total': 'sum', 'orden': 'count'}).reset_index().sort_values('total', ascending=False).head(10)
fig_top = px.bar(top_motos, x='total', y='moto', orientation='h',
                 title="Top 10 modelos por facturación",
                 labels={'total': 'Facturación ($)', 'moto': 'Modelo'})
st.plotly_chart(fig_top, width='stretch')

# Ventas
st.header("Análisis de Ventas")
col1, col2 = st.columns(2)

with col1:
    # Ticket por tipo
    ticket_tipo = df_filtrado.groupby('tipo_trabajo').agg({'total': 'mean', 'orden': 'count'}).reset_index()
    fig_ticket = px.bar(ticket_tipo, x='tipo_trabajo', y='total',
                        title="Ticket promedio por tipo de trabajo",
                        labels={'tipo_trabajo': 'Tipo', 'total': 'Ticket promedio ($)'})
    st.plotly_chart(fig_ticket, width='stretch')

with col2:
    # Uplift por service
    uplift = df_filtrado.groupby('service').agg({
        'orden': 'count',
        'total': 'mean',
        'repuestos': 'mean',
        'mo_extra': 'mean'
    }).reset_index()
    uplift = uplift[uplift['orden'] >= 5]
    uplift['ingreso_extra'] = uplift['repuestos'] + uplift['mo_extra']
    uplift = uplift.sort_values('ingreso_extra', ascending=False).head(10)
    fig_uplift = px.bar(uplift, x='ingreso_extra', y='service', orientation='h',
                        title="Ingreso extra promedio por service",
                        labels={'ingreso_extra': 'Ingreso extra ($)', 'service': 'Trabajo'})
    st.plotly_chart(fig_uplift, width='stretch')

# Oportunidad por modelo
st.subheader("Oportunidad de up-selling por modelo")
oportunidad = df_filtrado.groupby('moto').agg({
    'orden': 'count',
    'tiene_mo_extra': 'mean',
    'ingreso_extra': 'mean'
}).reset_index()
oportunidad = oportunidad[oportunidad['orden'] >= 8]
oportunidad['score'] = (1 - oportunidad['tiene_mo_extra']) * oportunidad['ingreso_extra']
oportunidad = oportunidad.sort_values('score', ascending=False).head(10)
fig_op = px.scatter(oportunidad, x='tiene_mo_extra', y='ingreso_extra', size='orden', text='moto',
                    title="Oportunidad de up-selling",
                    labels={'tiene_mo_extra': '% con M.O. extra', 'ingreso_extra': 'Ingreso extra promedio ($)'})
fig_op.update_traces(textposition='top center')
st.plotly_chart(fig_op, width='stretch')

# Tabla de ventas
st.subheader("Detalle comercial")
ventas_table = df_filtrado.groupby('service').agg(
    ordenes=('orden', 'count'),
    facturacion=('total', 'sum'),
    ticket_promedio=('total', 'mean'),
    repuestos_prom=('repuestos', 'mean'),
    mo_extra_prom=('mo_extra', 'mean'),
    pct_con_repuestos=('tiene_repuestos', 'mean'),
    pct_con_mo_extra=('tiene_mo_extra', 'mean')
).reset_index()
ventas_table.columns = ['Trabajo', 'Órdenes', 'Facturación', 'Ticket promedio', 'Repuestos prom.', 'M.O. extra prom.', '% con repuestos', '% con M.O. extra']
ventas_table['Facturación'] = ventas_table['Facturación'].apply(lambda x: f"${x:,.0f}".replace(",", "."))
ventas_table['Ticket promedio'] = ventas_table['Ticket promedio'].apply(lambda x: f"${x:,.0f}".replace(",", "."))
ventas_table['Repuestos prom.'] = ventas_table['Repuestos prom.'].apply(lambda x: f"${x:,.0f}".replace(",", "."))
ventas_table['M.O. extra prom.'] = ventas_table['M.O. extra prom.'].apply(lambda x: f"${x:,.0f}".replace(",", "."))
ventas_table['% con repuestos'] = ventas_table['% con repuestos'].apply(lambda x: f"{x:.1%}")
ventas_table['% con M.O. extra'] = ventas_table['% con M.O. extra'].apply(lambda x: f"{x:.1%}")
st.dataframe(ventas_table.sort_values('Facturación', ascending=False))

# Fidelización
st.header("Fidelización de Clientes")
col1, col2 = st.columns(2)

with col1:
    # Nuevos vs recurrentes
    clientes_visitas = df_filtrado.dropna(subset=['telefono_limpio']).groupby('telefono_limpio').size().reset_index(name='visitas')
    nuevos = (clientes_visitas['visitas'] == 1).sum()
    recurrentes = (clientes_visitas['visitas'] > 1).sum()
    fig_clientes = px.pie(values=[nuevos, recurrentes], names=['Nuevos', 'Recurrentes'], title="Clientes: nuevos vs recurrentes")
    st.plotly_chart(fig_clientes, width='stretch')

with col2:
    # Frecuencia de visitas
    freq = clientes_visitas['visitas'].value_counts().reset_index()
    freq.columns = ['visitas', 'clientes']
    fig_freq = px.bar(freq, x='visitas', y='clientes', title="Frecuencia de visitas por cliente",
                      labels={'visitas': 'Número de visitas', 'clientes': 'Cantidad de clientes'})
    st.plotly_chart(fig_freq, width='stretch')

# Tabla de clientes para accionar
st.subheader("Clientes para accionar")
clientes_hist = df_filtrado.dropna(subset=['telefono_limpio']).groupby('telefono_limpio').agg({
    'cliente': lambda x: x.dropna().iloc[0] if not x.dropna().empty else '',
    'mail': lambda x: x.dropna().iloc[0] if not x.dropna().empty else '',
    'moto': lambda x: x.mode().iloc[0] if not x.mode().empty else '',
    'fecha': 'max',
    'total': 'sum'
}).reset_index()
clientes_hist['visitas'] = df_filtrado.dropna(subset=['telefono_limpio']).groupby('telefono_limpio').size().values
clientes_hist['recurrente'] = clientes_hist['visitas'] > 1
clientes_hist['dias_desde_ultima'] = (datetime.now() - clientes_hist['fecha']).dt.days
clientes_hist['segmento'] = clientes_hist.apply(
    lambda row: 'Activar segunda visita' if row['visitas'] == 1 else (
        'Reactivar' if row['visitas'] >= 2 and row['dias_desde_ultima'] > 45 else (
            'Cliente fidelizado' if row['visitas'] >= 3 else 'Seguimiento'
        )
    ), axis=1
)
clientes_hist = clientes_hist.sort_values(['visitas', 'total'], ascending=[False, False])
clientes_hist['total'] = clientes_hist['total'].apply(lambda x: f"${x:,.0f}".replace(",", "."))
clientes_hist['fecha'] = clientes_hist['fecha'].dt.strftime('%d/%m/%Y')
clientes_hist = clientes_hist[['cliente', 'telefono_limpio', 'mail', 'moto', 'visitas', 'total', 'fecha', 'segmento']]
clientes_hist.columns = ['Cliente', 'Teléfono', 'Mail', 'Moto', 'Visitas', 'Facturación', 'Última visita', 'Acción sugerida']
st.dataframe(clientes_hist)

# Insights
st.header("Hallazgos Automáticos")
total_fact = df_filtrado['total'].sum()
share_rep = df_filtrado['repuestos'].sum() / total_fact if total_fact > 0 else 0
share_moextra = df_filtrado['mo_extra'].sum() / total_fact if total_fact > 0 else 0
pct_rep = df_filtrado['tiene_repuestos'].mean()
pct_moextra = df_filtrado['tiene_mo_extra'].mean()
pct_recurrentes = (clientes_visitas['visitas'] > 1).mean() if not clientes_visitas.empty else 0
top_gap = oportunidad.head(3)['moto'].tolist()

st.markdown("### Highlights")
st.write(f"- La facturación del período es **${total_fact:,.0f}**.".replace(",", "."))
st.write(f"- Los repuestos explican el **{share_rep:.1%}** de la facturación y la M.O. extra el **{share_moextra:.1%}**.")
st.write(f"- El **{pct_rep:.1%}** de las órdenes incluye repuestos, pero solo el **{pct_moextra:.1%}** incluye M.O. extra.")
st.write(f"- Entre clientes identificados, el **{pct_recurrentes:.1%}** volvió más de una vez.")
st.write(f"- Modelos con mejor oportunidad de venta adicional: **{', '.join(top_gap)}**.")

st.markdown("### Ideas accionables")
st.write("- Crear checklist comercial en recepción para elevar M.O. extra y venta de repuestos.")
st.write("- Automatizar recordatorios de service para clientes con una sola visita.")
st.write("- Lanzar campañas por modelo con accesorios/repuestos frecuentes.")
st.write("- Seguir de cerca modelos con mucha entrada al taller pero baja captura de M.O. extra.")

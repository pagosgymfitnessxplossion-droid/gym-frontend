import streamlit as st
import pandas as pd
from supabase import create_client
import time
import requests
import io
import plotly.express as px
from datetime import datetime, timedelta

# ================= CONFIGURACIÓN =================
st.set_page_config(
    page_title="GYM FITNESS XPLOSSION",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Variables de Sesión
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_role' not in st.session_state: st.session_state['user_role'] = ""
if 'user_name' not in st.session_state: st.session_state['user_name'] = ""

# ESTILOS DARK PRO
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: white; }
    .stButton>button { border-radius: 6px; font-weight: bold; }
    /* Métricas */
    [data-testid="stMetricValue"] { color: #fca311; font-size: 2.2rem; }
    h1, h2, h3 { color: #fca311; font-family: sans-serif; }
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #161a25; border-right: 1px solid #333; }
    /* Inputs */
    .stTextInput input, .stSelectbox, .stDateInput input, .stNumberInput input {
        background-color: #1c1c1c !important; 
        color: white !important;
    }
    #MainMenu {visibility: visible;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ================= CREDENCIALES =================
SUPABASE_URL = "https://cxmwymmgsggzilcwotjv.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN4bXd5bW1nc2dnemlsY3dvdGp2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzExNDAxMDEsImV4cCI6MjA4NjcxNjEwMX0.-3a_zppjlwprHG4qw-PQfdEPPPee2-iKdAlXLaQZeSM"

# ================= DATOS NEGOCIO =================
PLANES = ["PLAN COMÚN", "PLAN VIP", "VISITA DIARIA"] # Eliminada Inscripción
TIPOS_CLIENTE = ["Nuevo Ingreso", "Renovación", "Reingreso", "Empleado"]
METODOS_PAGO = ["EFECTIVO $", "EFECTIVO BS", "ZELLE", "PUNTO DE VENTA"]

USUARIOS = {
    "gymfitnessxplossion": {"pass": "gorrin.07*", "rol": "admin", "nombre": "Gerencia"},
    "recepcionxplossion": {"pass": "recepcion.07*", "rol": "empleado", "nombre": "Recepción"}
}

# ================= CONEXIONES =================
@st.cache_resource(ttl=0)
def init_supabase():
    try: return create_client(SUPABASE_URL, SUPABASE_KEY)
    except: return None

supabase = init_supabase()

@st.cache_data(ttl=300) # 5 min cache para tasa más fresca
def get_tasa_bcv():
    try:
        url = "https://ve.dolarapi.com/v1/dolares/oficial"
        req = requests.get(url, timeout=4)
        if req.status_code == 200: return float(req.json()['promedio'])
    except: pass
    try:
        url = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=bcv"
        req = requests.get(url, timeout=4)
        if req.status_code == 200: return float(req.json()['monitors']['usd']['price'])
    except: pass
    return None

def limpiar_monto_ve(monto_input):
    """Convierte cualquier formato de texto a float BS"""
    if pd.isna(monto_input): return 0.0
    texto = str(monto_input).upper().replace('BS', '').strip()
    # Caso 1200.50
    if '.' in texto and ',' not in texto:
        try: return float(texto)
        except: pass
    # Caso 1.200,50
    texto = texto.replace('.', '').replace(',', '.')
    try: return float(texto)
    except: return 0.0

# ================= FUNCIONES BASE DE DATOS =================
def get_pagos():
    if not supabase: return []
    try:
        res = supabase.table("pagos").select("*").order("id", desc=True).limit(2000).execute()
        return res.data
    except: return []

def actualizar_pago(id_pago, plan, tipo, nombre, cedula, metodo="Pago Móvil"):
    try:
        supabase.table("pagos").update({
            "servicio": plan, 
            "tipo_cliente": tipo,
            "nombre_cliente": nombre,
            "cedula_cliente": cedula,
            "metodo_pago": metodo
        }).eq("id", id_pago).execute()
        return True
    except: return False

def registrar_manual(monto_bs, ref, metodo, plan, tipo, nombre, cedula):
    try:
        data = {
            "referencia": ref,
            "monto": f"{monto_bs:.2f}", # Guardamos siempre en BS string para consistencia
            "servicio": plan,
            "tipo_cliente": tipo,
            "nombre_cliente": nombre,
            "cedula_cliente": cedula,
            "metodo_pago": metodo
        }
        supabase.table("pagos").insert(data).execute()
        return True
    except Exception as e:
        st.error(f"Error DB: {e}")
        return False

def eliminar_pago(id_pago):
    try:
        supabase.table("pagos").delete().eq("id", id_pago).execute()
        return True
    except: return False

# ================= EXCEL PRO =================
def generar_excel_pro(df, tasa, rango_texto):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        ws = workbook.add_worksheet("Reporte Gym")
        
        # Estilos
        st_title = workbook.add_format({'bold': True, 'font_size': 14, 'bg_color': '#161a25', 'font_color': '#fca311', 'border': 1, 'align': 'center'})
        st_head = workbook.add_format({'bold': True, 'bg_color': '#fca311', 'border': 1, 'align': 'center'})
        st_txt = workbook.add_format({'border': 1, 'align': 'center'})
        st_bs = workbook.add_format({'num_format': '#,##0.00 "Bs"', 'border': 1})
        st_usd = workbook.add_format({'num_format': '"$" #,##0.00', 'border': 1})
        st_tot = workbook.add_format({'bold': True, 'bg_color': '#DDD', 'border': 1})
        
        df_x = df.copy()
        df_x['monto_usd'] = df_x['monto_real'] / tasa if tasa > 0 else 0
        
        ws.merge_range('A1:I1', f'GYM FITNESS XPLOSSION - {rango_texto}', st_title)
        ws.write('A2', f'Tasa: {tasa:,.2f} Bs', st_txt)
        ws.write('I2', datetime.now().strftime("%d/%m/%Y"), st_txt)
        
        headers = ['FECHA/HORA', 'REFERENCIA', 'CÉDULA', 'CLIENTE', 'PLAN', 'TIPO', 'MÉTODO', 'MONTO (BS)', 'MONTO (USD)']
        for col, h in enumerate(headers): ws.write(3, col, h, st_head)
        
        row = 4
        for _, r in df_x.iterrows():
            ws.write(row, 0, r['fecha_fmt'], st_txt)
            ws.write(row, 1, r['referencia'], st_txt)
            ws.write(row, 2, r.get('cedula_cliente', '-') or '-', st_txt)
            ws.write(row, 3, r.get('nombre_cliente', '-') or '-', st_txt)
            ws.write(row, 4, r['servicio'] or '-', st_txt)
            ws.write(row, 5, r['tipo_cliente'] or '-', st_txt)
            ws.write(row, 6, r.get('metodo_pago', '-') or '-', st_txt)
            ws.write(row, 7, r['monto_real'], st_bs)
            ws.write(row, 8, r['monto_usd'], st_usd)
            row += 1
            
        ws.write(row, 0, "TOTAL GENERAL", st_tot)
        ws.write(row, 7, df_x['monto_real'].sum(), st_bs)
        ws.write(row, 8, df_x['monto_usd'].sum(), st_usd)
        
        ws.set_column('A:A', 22)
        ws.set_column('D:D', 25)
        ws.set_column('G:I', 18)
        
    return output.getvalue()

# ================= LOGIN =================
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.write("")
        st.markdown("<h1 style='text-align: center;'>🔐 GYM XPLOSSION</h1>", unsafe_allow_html=True)
        with st.form("login"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("ENTRAR", type="primary"):
                if u in USUARIOS and USUARIOS[u]["pass"] == p:
                    st.session_state['logged_in'] = True
                    st.session_state['user_role'] = USUARIOS[u]["rol"]
                    st.session_state['user_name'] = USUARIOS[u]["nombre"]
                    st.rerun()
                else: st.error("Datos incorrectos")
    st.stop()

# ================= DASHBOARD =================
with st.sidebar:
    st.title(f"👤 {st.session_state['user_name']}")
    st.caption("🔸 GERENCIA" if st.session_state['user_role'] == 'admin' else "🔸 RECEPCIÓN")
    st.write("---")
    
    # === TASA BCV PRIMERO ===
    tasa_api = get_tasa_bcv()
    tasa_calc = tasa_api if tasa_api else st.number_input("Tasa Manual", value=60.0)
    if tasa_api: 
        st.success(f"✅ BCV: {tasa_calc:,.2f} Bs")
    else: 
        st.warning("⚠️ Manual")
    st.write("---")

    # === REGISTRO MANUAL ===
    with st.expander("📝 REGISTRO MANUAL", expanded=False):
        with st.form("manual_pay"):
            st.caption("Datos del Cliente")
            m_ced = st.text_input("C.I.")
            m_nombre = st.text_input("Nombre")
            
            st.caption("Pago")
            col_m1, col_m2 = st.columns(2)
            moneda_pago = col_m1.selectbox("Moneda", ["BS", "USD"])
            m_monto_input = col_m2.number_input("Monto", min_value=0.0, step=1.0)
            
            m_ref = st.text_input("Referencia")
            m_metodo = st.selectbox("Método", METODOS_PAGO)
            m_plan = st.selectbox("Plan", PLANES)
            m_tipo = st.selectbox("Tipo", TIPOS_CLIENTE)
            
            if st.form_submit_button("💾 Guardar"):
                # Conversión automática para guardar todo unificado en BD
                monto_a_guardar_bs = m_monto_input
                if moneda_pago == "USD":
                    monto_a_guardar_bs = m_monto_input * tasa_calc
                
                if not m_ref: m_ref = f"MAN-{int(time.time())}"
                
                res = registrar_manual(monto_a_guardar_bs, m_ref, m_metodo, m_plan, m_tipo, m_nombre, m_ced)
                if res: 
                    st.success(f"Pago Registrado: {monto_a_guardar_bs:,.2f} Bs")
                    time.sleep(1.5)
                    st.rerun()

    st.write("---")
    st.header("Filtros")
    filtro_fecha = st.selectbox("Ver:", ["Hoy", "Ayer", "Semana Actual", "Mes Actual", "Rango"])
    
    hoy = datetime.now()
    ini, fin = hoy.date(), hoy.date()
    txt_rango = filtro_fecha
    
    if filtro_fecha == "Rango":
        d1 = st.date_input("Desde", hoy - timedelta(days=7))
        d2 = st.date_input("Hasta", hoy)
        ini, fin = d1, d2
        txt_rango = f"{d1} al {d2}"

    st.write("---")
    if st.button("Cerrar Sesión"):
        st.session_state['logged_in'] = False
        st.rerun()

# --- MAIN CONTENT ---
st.title("🏋️‍♂️ Control GYM XPLOSSION")

raw = get_pagos()
df = pd.DataFrame(raw) if raw else pd.DataFrame()

if df.empty:
    st.info("Sin registros.")
else:
    # 1. Procesar Fechas (CRÍTICO: Conversión UTC -> VZLA)
    df['monto_real'] = df['monto'].apply(limpiar_monto_ve)
    
    # Supabase devuelve string UTC, convertimos explícitamente
    df['fecha_dt'] = pd.to_datetime(df['created_at'])
    if df['fecha_dt'].dt.tz is None: 
        df['fecha_dt'] = df['fecha_dt'].dt.tz_localize('UTC')
    
    # Convertir a America/Caracas (-04:00)
    df['fecha_ve'] = df['fecha_dt'].dt.tz_convert('America/Caracas')
    df['fecha_fmt'] = df['fecha_ve'].dt.strftime('%d/%m %I:%M %p') # Formato 12h
    
    # Asegurar columnas
    if 'nombre_cliente' not in df.columns: df['nombre_cliente'] = ""
    if 'cedula_cliente' not in df.columns: df['cedula_cliente'] = ""
    if 'metodo_pago' not in df.columns: df['metodo_pago'] = "Pago Móvil"

    # 2. Filtrar Fecha
    mask = pd.Series([True]*len(df))
    # Importante: usar fecha_ve (hora venezuela) para filtrar
    fecha_ve_date = df['fecha_ve'].dt.date
    hoy_date = datetime.now(df['fecha_ve'].dt.tz).date() # Fecha actual Vzla

    if filtro_fecha == "Hoy": mask = fecha_ve_date == hoy_date
    elif filtro_fecha == "Ayer": mask = fecha_ve_date == (hoy_date - timedelta(days=1))
    elif filtro_fecha == "Semana Actual": mask = fecha_ve_date >= (hoy_date - timedelta(days=hoy_date.weekday()))
    elif filtro_fecha == "Mes Actual": mask = (df['fecha_ve'].dt.month == hoy_date.month) & (df['fecha_ve'].dt.year == hoy_date.year)
    elif filtro_fecha == "Rango": mask = (fecha_ve_date >= ini) & (fecha_ve_date <= fin)
    
    df_f = df[mask].copy()

    # BUSCADOR
    busqueda = st.text_input("🔍 Buscar Cliente, Cédula o Referencia", placeholder="Ej: Perez...")
    if busqueda:
        df_f = df_f[df_f['referencia'].astype(str).str.contains(busqueda, case=False) | 
                    df_f['nombre_cliente'].astype(str).str.contains(busqueda, case=False) |
                    df_f['cedula_cliente'].astype(str).str.contains(busqueda, case=False)]

    # 3. CALCULO DE TOTALES (SOLO PAGOS YA CLASIFICADOS)
    # Filtramos solo los que tienen Plan asignado para sumar
    df_calc = df_f[df_f['servicio'].notnull() & (df_f['servicio'] != "")]
    
    # --- VISTA GERENCIA ---
    if st.session_state['user_role'] == 'admin':
        tot_bs = df_calc['monto_real'].sum()
        tot_usd = tot_bs / tasa_calc if tasa_calc > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Ingresos (Bs)", f"{tot_bs:,.2f}")
        c2.metric("Total (USD)", f"{tot_usd:,.2f}")
        c3.download_button("📂 Descargar Reporte", data=generar_excel_pro(df_calc, tasa_calc, txt_rango), file_name="Cierre_Gym.xlsx", type="primary")
        
        # --- GRÁFICAS MEJORADAS (COLORES PERSONALIZADOS) ---
        if not df_calc.empty:
            st.write("")
            col_g1, col_g2 = st.columns(2)
            
            with col_g1:
                df_planes = df_calc['servicio'].value_counts().reset_index()
                df_planes.columns = ['Plan', 'Cantidad']
                
                # Mapa de colores específico
                colores_planes = {
                    "PLAN COMÚN": "#3498db",      # Azul
                    "PLAN VIP": "#f1c40f",        # Dorado/Amarillo
                    "VISITA DIARIA": "#2ecc71"    # Verde
                }
                
                fig_planes = px.bar(
                    df_planes, x='Plan', y='Cantidad', 
                    title="📊 Planes Más Vendidos",
                    text='Cantidad',
                    color='Plan',
                    color_discrete_map=colores_planes # Aplica colores
                )
                fig_planes.update_layout(
                    plot_bgcolor="#161a25", paper_bgcolor="#161a25",
                    font=dict(color="white"), showlegend=False,
                    xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#333')
                )
                st.plotly_chart(fig_planes, use_container_width=True)
            
            with col_g2:
                df_metodos = df_calc['metodo_pago'].value_counts().reset_index()
                df_metodos.columns = ['Método', 'Cantidad']
                fig_pie = px.pie(
                    df_metodos, names='Método', values='Cantidad',
                    title="💳 Métodos de Pago",
                    hole=0.4,
                    color_discrete_sequence=px.colors.sequential.RdBu
                )
                fig_pie.update_layout(
                    plot_bgcolor="#161a25", paper_bgcolor="#161a25",
                    font=dict(color="white")
                )
                st.plotly_chart(fig_pie, use_container_width=True)
        st.divider()

    # --- LISTA DE PAGOS ---
    if df_f.empty:
        st.warning("No se encontraron pagos.")
    else:
        st.subheader(f"Movimientos ({len(df_f)})")
        for i, row in df_f.iterrows():
            cedula_show = row.get('cedula_cliente', '') or 'Sin C.I'
            nombre_show = row['nombre_cliente'] if row['nombre_cliente'] else 'Sin Nombre'
            
            # Estado: Verde si tiene Plan, Rojo si no
            ready = row['servicio'] and row['tipo_cliente'] and row['nombre_cliente']
            color = "#2ecc71" if ready else "#e74c3c"
            
            with st.container():
                cols = st.columns([0.1, 0.5, 0.2, 0.2])
                cols[0].markdown(f"<div style='height:100%; width:5px; background-color:{color}; border-radius:5px;'></div>", unsafe_allow_html=True)
                
                with cols[1]:
                    st.markdown(f"**{nombre_show}**")
                    st.caption(f"C.I: {cedula_show} | Ref: {row['referencia']}")
                
                with cols[2]:
                    # Mostrar monto original
                    st.markdown(f"**Bs. {row['monto']}**")
                    # Mostrar equivalente USD si aplica
                    if tasa_calc > 0:
                        equiv_usd = row['monto_real'] / tasa_calc
                        st.caption(f"({equiv_usd:,.2f} $)")
                    st.caption(f"{row['fecha_fmt']}")
                
                with cols[3]:
                    with st.popover("Editar"):
                        st.write(f"Editar: {row['referencia']}")
                        
                        e_ced = st.text_input("Cédula", value=cedula_show if cedula_show != 'Sin C.I' else "", key=f"c_{row['id']}")
                        e_nom = st.text_input("Nombre", value=nombre_show if nombre_show != 'Sin Nombre' else "", key=f"n_{row['id']}")
                        
                        ix_p = PLANES.index(row['servicio']) if row['servicio'] in PLANES else 0
                        p_plan = st.selectbox("Plan", PLANES, index=ix_p, key=f"pl_{row['id']}")
                        
                        ix_t = TIPOS_CLIENTE.index(row['tipo_cliente']) if row['tipo_cliente'] in TIPOS_CLIENTE else 0
                        p_tipo = st.selectbox("Tipo", TIPOS_CLIENTE, index=ix_t, key=f"tp_{row['id']}")
                        
                        ix_m = METODOS_PAGO.index(row['metodo_pago']) if row['metodo_pago'] in METODOS_PAGO else 0
                        p_met = st.selectbox("Método", METODOS_PAGO, index=ix_m, key=f"mt_{row['id']}")
                        
                        if st.button("Guardar Cambios", key=f"sv_{row['id']}"):
                            res = actualizar_pago(row['id'], p_plan, p_tipo, e_nom, e_ced, p_met)
                            if res:
                                st.success("✅ Pago Registrado")
                                time.sleep(1)
                                st.rerun()
                        
                        if st.session_state['user_role'] == 'admin':
                            st.divider()
                            if st.button("Eliminar", key=f"dl_{row['id']}"):
                                eliminar_pago(row['id'])
                                st.rerun()
                st.divider()

    time.sleep(15)

import streamlit as st
import pandas as pd
from supabase import create_client
import time
import requests
import io
from datetime import datetime, timedelta

# ================= CONFIGURACIÓN INICIAL =================
st.set_page_config(
    page_title="GYM FITNESS XPLOSSION",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar variables de sesión
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_role' not in st.session_state: st.session_state['user_role'] = ""
if 'user_name' not in st.session_state: st.session_state['user_name'] = ""

# ESTILOS CSS PRO
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: white; }
    .stButton>button { width: 100%; border-radius: 6px; font-weight: bold; height: 3em; }
    /* Métricas */
    [data-testid="stMetricValue"] { color: #fca311; font-size: 2.5rem; }
    [data-testid="stMetricLabel"] { font-size: 1.1rem; color: #ddd; }
    h1, h2, h3 { color: #fca311; font-family: sans-serif; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #161a25; border-right: 1px solid #333; }
    
    /* Inputs */
    .stDateInput input { color: white; }
    
    #MainMenu {visibility: visible;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# ================= CREDENCIALES =================
SUPABASE_URL = "https://cxmwymmgsggzilcwotjv.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN4bXd5bW1nc2dnemlsY3dvdGp2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzExNDAxMDEsImV4cCI6MjA4NjcxNjEwMX0.-3a_zppjlwprHG4qw-PQfdEPPPee2-iKdAlXLaQZeSM"

# ================= CONFIGURACIÓN DEL NEGOCIO =================
PLANES = [
    "PLAN COMÚN",
    "PLAN VIP",
    "VISITA DIARIA"
]

TIPOS_CLIENTE = ["Nuevo Ingreso", "Renovación", "Reingreso", "Empleado"]

# USUARIOS ACTUALIZADOS
USUARIOS = {
    "gymfitnessxplossion": {
        "pass": "gorrin.07*", 
        "rol": "admin", 
        "nombre": "Gerencia"
    },
    "recepcionxplossion": {
        "pass": "recepcion.07*", 
        "rol": "empleado", 
        "nombre": "Recepción"
    }
}

# ================= CONEXIONES =================
@st.cache_resource(ttl=0)
def init_supabase():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except:
        return None

supabase = init_supabase()

# === LÓGICA DE TASA BCV ===
@st.cache_data(ttl=900)
def get_tasa_bcv():
    # 1. INTENTO PRIMARIO
    try:
        url = "https://ve.dolarapi.com/v1/dolares/oficial"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data['promedio'])
    except:
        pass
    # 2. INTENTO SECUNDARIO
    try:
        url = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=bcv"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return float(data['monitors']['usd']['price'])
    except:
        pass
    return None

def limpiar_monto_ve(monto_input):
    if pd.isna(monto_input): return 0.0
    texto = str(monto_input).upper().replace('BS', '').strip()
    if '.' in texto and ',' not in texto:
        try: return float(texto)
        except: pass
    texto = texto.replace('.', '').replace(',', '.')
    try: return float(texto)
    except: return 0.0

def get_pagos():
    if not supabase: return []
    try:
        # Traemos más registros para permitir reportes largos
        response = supabase.table("pagos").select("*").order("id", desc=True).limit(2000).execute()
        return response.data
    except:
        return []

def actualizar_pago(id_pago, plan, tipo):
    try:
        supabase.table("pagos").update({"servicio": plan, "tipo_cliente": tipo}).eq("id", id_pago).execute()
        return True
    except:
        return False

def eliminar_pago(id_pago):
    try:
        supabase.table("pagos").delete().eq("id", id_pago).execute()
        return True
    except:
        return False

# ================= EXCEL PROFESIONAL =================
def generar_excel_pro(df, tasa, rango_texto):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        worksheet = workbook.add_worksheet("Reporte Gym")
        
        # --- ESTILOS ---
        style_title = workbook.add_format({
            'bold': True, 'font_size': 16, 'align': 'center', 
            'bg_color': '#161a25', 'font_color': '#fca311', 'border': 1
        })
        style_header = workbook.add_format({
            'bold': True, 'bg_color': '#fca311', 'font_color': 'black', 
            'border': 1, 'align': 'center'
        })
        style_text = workbook.add_format({'border': 1, 'align': 'center'})
        style_bs = workbook.add_format({'num_format': '#,##0.00 "Bs"', 'border': 1})
        style_usd = workbook.add_format({'num_format': '"$" #,##0.00', 'border': 1})
        style_total = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
        style_total_bs = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'num_format': '#,##0.00 "Bs"', 'border': 1})
        style_total_usd = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'num_format': '"$" #,##0.00', 'border': 1})

        # --- PREPARAR DATA ---
        df_x = df.copy()
        # Calculamos columna USD para el excel
        df_x['monto_usd'] = df_x['monto_real'] / tasa if tasa > 0 else 0
        df_x['Fecha'] = df_x['fecha_ve'].dt.tz_localize(None) # Quitar zona horaria
        
        # --- ENCABEZADOS ---
        # Título Principal (Merge de celdas A1 a F1)
        worksheet.merge_range('A1:F1', f'GYM FITNESS XPLOSSION - REPORTE DE CAJA ({rango_texto})', style_title)
        worksheet.write('A2', f'Tasa BCV: {tasa:,.2f} Bs', style_text)
        worksheet.write('F2', f'Generado: {datetime.now().strftime("%d/%m/%Y")}', style_text)
        
        headers = ['FECHA', 'REFERENCIA', 'PLAN', 'TIPO CLIENTE', 'MONTO (BS)', 'MONTO (USD)']
        for col, h in enumerate(headers):
            worksheet.write(3, col, h, style_header)

        # --- ESCRIBIR DATA ---
        row = 4
        for _, r in df_x.iterrows():
            worksheet.write(row, 0, r['Fecha'].strftime("%d/%m/%Y %I:%M %p"), style_text)
            worksheet.write(row, 1, r['referencia'], style_text)
            worksheet.write(row, 2, r['servicio'] if r['servicio'] else "-", style_text)
            worksheet.write(row, 3, r['tipo_cliente'] if r['tipo_cliente'] else "-", style_text)
            worksheet.write(row, 4, r['monto_real'], style_bs)
            worksheet.write(row, 5, r['monto_usd'], style_usd)
            row += 1

        # --- FILA DE TOTALES ---
        worksheet.write(row, 0, "TOTALES", style_total)
        worksheet.write(row, 1, "", style_total)
        worksheet.write(row, 2, "", style_total)
        worksheet.write(row, 3, "", style_total)
        worksheet.write(row, 4, df_x['monto_real'].sum(), style_total_bs)
        worksheet.write(row, 5, df_x['monto_usd'].sum(), style_total_usd)

        # --- ANCHO DE COLUMNAS ---
        worksheet.set_column('A:A', 22) # Fecha
        worksheet.set_column('B:B', 15) # Ref
        worksheet.set_column('C:C', 20) # Plan
        worksheet.set_column('D:D', 20) # Tipo
        worksheet.set_column('E:F', 18) # Montos

    return output.getvalue()

# ================= LOGIN =================
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.write("")
        st.write("")
        st.markdown("<h1 style='text-align: center;'>🔐 GYM XPLOSSION</h1>", unsafe_allow_html=True)
        with st.form("login_fast"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            btn = st.form_submit_button("ENTRAR", type="primary")
            
            if btn:
                if u in USUARIOS and USUARIOS[u]["pass"] == p:
                    st.session_state['logged_in'] = True
                    st.session_state['user_role'] = USUARIOS[u]["rol"]
                    st.session_state['user_name'] = USUARIOS[u]["nombre"]
                    st.rerun()
                else:
                    st.error("Datos incorrectos")
    st.stop()

# ================= DASHBOARD PRINCIPAL =================

# --- BARRA LATERAL ---
with st.sidebar:
    st.title(f"👤 {st.session_state['user_name']}")
    if st.session_state['user_role'] == 'admin':
        st.caption("🔹 GERENCIA TOTAL")
    else:
        st.caption("🔸 RECEPCIÓN")
    st.write("---")
    
    st.header("📅 Filtros")
    # Filtro avanzado
    opcion_fecha = st.selectbox("Período:", ["Hoy", "Ayer", "Semana Actual", "Mes Actual", "Rango Personalizado"])
    
    # Variables de fecha iniciales
    hoy = datetime.now()
    fecha_inicio = hoy.date()
    fecha_fin = hoy.date()
    texto_rango = opcion_fecha

    if opcion_fecha == "Rango Personalizado":
        col_d1, col_d2 = st.columns(2)
        d1 = col_d1.date_input("Desde", hoy - timedelta(days=7))
        d2 = col_d2.date_input("Hasta", hoy)
        fecha_inicio = d1
        fecha_fin = d2
        texto_rango = f"{d1.strftime('%d/%m')} al {d2.strftime('%d/%m')}"
    
    st.write("---")
    st.header("💵 Tasa BCV")
    
    tasa_api = get_tasa_bcv()
    
    if tasa_api:
        tasa_calculo = tasa_api
        st.success(f"✅ Oficial: {tasa_calculo:,.2f} Bs")
    else:
        st.error("⚠️ Sin conexión BCV")
        tasa_calculo = st.number_input("Tasa Manual", value=60.00, step=0.1)

    st.write("---")
    if st.button("Cerrar Sesión"):
        st.session_state['logged_in'] = False
        st.rerun()

# --- CUERPO ---
st.title("🏋️‍♂️ Control GYM XPLOSSION")

raw = get_pagos()
df = pd.DataFrame(raw) if raw else pd.DataFrame()

if df.empty:
    st.info("No hay datos cargados.")
    time.sleep(5)
    st.rerun()
else:
    # Procesar datos
    df['monto_real'] = df['monto'].apply(limpiar_monto_ve)
    df['fecha_dt'] = pd.to_datetime(df['created_at'])
    if df['fecha_dt'].dt.tz is None: df['fecha_dt'] = df['fecha_dt'].dt.tz_localize('UTC')
    df['fecha_ve'] = df['fecha_dt'].dt.tz_convert('America/Caracas')
    df['fecha_fmt'] = df['fecha_ve'].dt.strftime('%d/%m %I:%M %p')

    # --- APLICAR FILTROS DE FECHA ---
    mask_fecha = pd.Series([True] * len(df))
    
    if opcion_fecha == "Hoy":
        mask_fecha = df['fecha_ve'].dt.date == hoy.date()
    elif opcion_fecha == "Ayer":
        mask_fecha = df['fecha_ve'].dt.date == (hoy - timedelta(days=1)).date()
    elif opcion_fecha == "Semana Actual":
        start = hoy.date() - timedelta(days=hoy.weekday())
        mask_fecha = df['fecha_ve'].dt.date >= start
    elif opcion_fecha == "Mes Actual":
        mask_fecha = (df['fecha_ve'].dt.month == hoy.month) & (df['fecha_ve'].dt.year == hoy.year)
    elif opcion_fecha == "Rango Personalizado":
        mask_fecha = (df['fecha_ve'].dt.date >= fecha_inicio) & (df['fecha_ve'].dt.date <= fecha_fin)

    df_filtered = df[mask_fecha]

    # --- MÉTRICAS (SOLO PARA GERENCIA) ---
    if st.session_state['user_role'] == 'admin':
        total_bs = df_filtered['monto_real'].sum()
        total_usd = total_bs / tasa_calculo if tasa_calculo > 0 else 0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Bolívares", f"Bs. {total_bs:,.2f}")
        m2.metric("Total Dólares", f"$ {total_usd:,.2f}")
        
        # Botón Excel PRO
        m3.write("") # Espacio para alinear
        m3.download_button(
            "📥 Descargar Reporte Excel", 
            data=generar_excel_pro(df_filtered, tasa_calculo, texto_rango), 
            file_name=f"Reporte_Gym_{datetime.now().strftime('%Y%m%d')}.xlsx",
            type="primary"
        )
        st.divider()
    else:
        st.info("👋 Hola Recepción. Clasifica los pagos pendientes a continuación.")
        # La recepción NO puede descargar el excel de contabilidad, solo ver lista
        st.divider()

    # --- TABLA DE PAGOS (PARA TODOS) ---
    if df_filtered.empty:
        st.warning("No hay transacciones en este período.")
    
    for i, row in df_filtered.iterrows():
        status = row['servicio'] and row['tipo_cliente']
        color = "#2ecc71" if status else "#e74c3c"
        bg_card = "#1c1c1c"
        
        with st.container():
            st.markdown(f"""
            <div style="background-color:{bg_card}; padding:15px; border-radius:10px; border-left: 5px solid {color}; margin-bottom:10px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <strong style="font-size:1.1em; color:white;">Ref: {row['referencia']}</strong><br>
                        <span style="color:#bbb; font-size:0.9em;">{row['fecha_fmt']}</span>
                    </div>
                    <div style="text-align:right;">
                        <strong style="font-size:1.3em; color:{color};">Bs. {row['monto']}</strong><br>
                        <span style="color:#bbb; font-size:0.8em;">{row['servicio'] if row['servicio'] else 'Sin Clasificar'}</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Solo permitir editar
            with st.expander("🛠️ Editar"):
                c_a, c_b, c_c = st.columns([2, 2, 1])
                
                ix_p = PLANES.index(row['servicio']) if row['servicio'] in PLANES else 0
                ix_t = TIPOS_CLIENTE.index(row['tipo_cliente']) if row['tipo_cliente'] in TIPOS_CLIENTE else 0
                
                np = c_a.selectbox("Plan", PLANES, index=ix_p, key=f"p_{row['id']}")
                nt = c_b.selectbox("Tipo", TIPOS_CLIENTE, index=ix_t, key=f"t_{row['id']}")
                
                if c_c.button("Guardar", key=f"s_{row['id']}"):
                    actualizar_pago(row['id'], np, nt)
                    st.rerun()
                
                # SOLO GERENCIA PUEDE ELIMINAR
                if st.session_state['user_role'] == 'admin':
                    if st.button("Eliminar (Gerencia)", key=f"d_{row['id']}"):
                        eliminar_pago(row['id'])
                        st.rerun()

    time.sleep(10)
    st.rerun()

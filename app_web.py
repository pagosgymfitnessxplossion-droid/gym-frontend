import streamlit as st
import pandas as pd
from supabase import create_client
import time
import requests
import base64
import os
from datetime import datetime, timedelta
import io

# ================= CONFIGURACIÓN INICIAL (CRÍTICO) =================
st.set_page_config(
    page_title="GYM FITNESS XPLOSSION",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Inicializar variables de sesión si no existen
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_role' not in st.session_state: st.session_state['user_role'] = ""
if 'user_name' not in st.session_state: st.session_state['user_name'] = ""

# ESTILOS CSS (Optimizados para carga rápida)
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: white; }
    .stButton>button { width: 100%; border-radius: 6px; font-weight: bold; height: 3em; }
    /* Métricas grandes y visibles */
    [data-testid="stMetricValue"] { color: #fca311; font-size: 2.8rem; }
    h1, h2, h3 { color: #fca311; font-family: sans-serif; }
    /* Ocultar elementos innecesarios */
    #MainMenu {visibility: visible;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
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

USUARIOS = {
    "admin": {"pass": "gym2024", "rol": "admin", "nombre": "Gerencia"},
    "recepcion": {"pass": "caja1", "rol": "empleado", "nombre": "Recepción"}
}

# ================= CONEXIONES =================
@st.cache_resource(ttl=0)
def init_supabase():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except:
        return None

supabase = init_supabase()

@st.cache_data(ttl=1800) # Se actualiza cada 30 min para no saturar
def get_tasa_bcv():
    """Obtiene la tasa BCV oficial sin fallos."""
    try:
        # API Principal (Más estable)
        url = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=bcv"
        response = requests.get(url, timeout=3) # Timeout rápido para no bloquear
        if response.status_code == 200:
            data = response.json()
            # Accedemos directo al precio
            price = data['monitors']['usd']['price']
            return float(price)
    except Exception as e:
        pass
    return None # Retorna None si falla para activar modo manual

def limpiar_monto_ve(monto_input):
    if pd.isna(monto_input): return 0.0
    texto = str(monto_input).upper().replace('BS', '').strip()
    # Detectar formato 1200.50
    if '.' in texto and ',' not in texto:
        try: return float(texto)
        except: pass
    # Detectar formato 1.200,50
    texto = texto.replace('.', '').replace(',', '.')
    try: return float(texto)
    except: return 0.0

def get_pagos():
    if not supabase: return []
    try:
        response = supabase.table("pagos").select("*").order("id", desc=True).limit(500).execute()
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

# ================= EXCEL =================
def generar_excel(df, tasa):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        fmt_head = workbook.add_format({'bold': True, 'bg_color': '#fca311', 'border': 1})
        fmt_num = workbook.add_format({'num_format': '#,##0.00 "Bs"', 'border': 1})
        
        df_x = df.copy()
        df_x = df_x[['fecha_ve', 'referencia', 'monto_real', 'servicio', 'tipo_cliente']]
        df_x.columns = ['Fecha', 'Referencia', 'Monto Bs', 'Plan', 'Tipo']
        df_x['Fecha'] = df_x['Fecha'].dt.tz_localize(None)
        
        df_x.to_excel(writer, sheet_name='Caja Gym', index=False)
    return output.getvalue()

# ================= LOGIN RÁPIDO =================
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
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
                    st.rerun() # Recarga INSTANTÁNEA
                else:
                    st.error("Datos incorrectos")
    st.stop() # Detiene la ejecución aquí si no entró

# ================= DASHBOARD PRINCIPAL =================

# --- BARRA LATERAL ---
with st.sidebar:
    st.markdown(f"### 👤 {st.session_state['user_name']}")
    filtro_fecha = st.selectbox("📅 Período", ["Hoy", "Ayer", "Semana Actual", "Todo"])
    
    st.divider()
    st.markdown("### 💵 Tasa BCV")
    
    # Lógica BCV Robusta
    tasa_api = get_tasa_bcv()
    
    if tasa_api:
        tasa_calculo = tasa_api
        st.success(f"✅ Oficial: {tasa_calculo:,.2f} Bs")
    else:
        st.warning("⚠️ API BCV Off - Modo Manual")
        tasa_calculo = st.number_input("Tasa Manual", value=60.00, step=0.1)

    st.divider()
    if st.button("Salir"):
        st.session_state['logged_in'] = False
        st.rerun()

# --- CUERPO ---
st.title("🏋️‍♂️ Control GYM XPLOSSION")

# Carga de datos
raw = get_pagos()
df = pd.DataFrame(raw) if raw else pd.DataFrame()

if df.empty:
    st.info("Esperando pagos...")
    time.sleep(5) # Auto-refresh suave si está vacío
    st.rerun()
else:
    # Procesamiento
    df['monto_real'] = df['monto'].apply(limpiar_monto_ve)
    df['fecha_dt'] = pd.to_datetime(df['created_at'])
    if df['fecha_dt'].dt.tz is None: df['fecha_dt'] = df['fecha_dt'].dt.tz_localize('UTC')
    df['fecha_ve'] = df['fecha_dt'].dt.tz_convert('America/Caracas')
    df['fecha_fmt'] = df['fecha_ve'].dt.strftime('%d/%m %I:%M %p')

    # Filtros Fecha
    hoy = datetime.now(df['fecha_ve'].dt.tz).date()
    if filtro_fecha == "Hoy": df = df[df['fecha_ve'].dt.date == hoy]
    elif filtro_fecha == "Ayer": df = df[df['fecha_ve'].dt.date == (hoy - timedelta(days=1))]
    elif filtro_fecha == "Semana Actual": 
        inicio = hoy - timedelta(days=hoy.weekday())
        df = df[df['fecha_ve'].dt.date >= inicio]

    # Métricas
    total_bs = df['monto_real'].sum()
    total_usd = total_bs / tasa_calculo if tasa_calculo > 0 else 0
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Bolívares", f"Bs. {total_bs:,.2f}")
    m2.metric("Total Dólares", f"$ {total_usd:,.2f}")
    m3.download_button("📥 Descargar Excel", data=generar_excel(df, tasa_calculo), file_name="Cierre.xlsx")
    
    st.divider()

    # Tabla de Pagos
    for i, row in df.iterrows():
        status = row['servicio'] and row['tipo_cliente']
        color = "#2ecc71" if status else "#e74c3c" # Verde/Rojo plano
        bg_card = "#1c1c1c" # Fondo tarjeta oscuro
        
        with st.container():
            # Diseño tarjeta personalizada
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
            
            # Botones de Acción (Solo mostrar expansor si se necesita editar)
            with st.expander("🛠️ Editar / Asignar Plan"):
                c_a, c_b, c_c = st.columns([2, 2, 1])
                
                ix_p = PLANES.index(row['servicio']) if row['servicio'] in PLANES else 0
                ix_t = TIPOS_CLIENTE.index(row['tipo_cliente']) if row['tipo_cliente'] in TIPOS_CLIENTE else 0
                
                np = c_a.selectbox("Plan", PLANES, index=ix_p, key=f"p_{row['id']}")
                nt = c_b.selectbox("Tipo", TIPOS_CLIENTE, index=ix_t, key=f"t_{row['id']}")
                
                if c_c.button("Guardar", key=f"s_{row['id']}"):
                    if actualizar_pago(row['id'], np, nt):
                        st.toast("Guardado")
                        time.sleep(0.5)
                        st.rerun()
                
                if st.session_state['user_role'] == 'admin':
                    if st.button("Eliminar Pago", key=f"d_{row['id']}"):
                        eliminar_pago(row['id'])
                        st.rerun()

    # Auto-refresco no bloqueante
    time.sleep(10)
    st.rerun()

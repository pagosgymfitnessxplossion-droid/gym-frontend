import streamlit as st
import pandas as pd
from supabase import create_client
import time
import requests
import base64
import os
from datetime import datetime, timedelta
import io

# ================= CONFIGURACIÓN =================
st.set_page_config(page_title="GYM FITNESS XPLOSSION", page_icon="🏋️‍♂️", layout="wide")

# ESTILOS (TEMA GYM: Negro y Amarillo/Naranja)
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: white; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    /* Métricas grandes */
    [data-testid="stMetricValue"] { color: #fca311; font-size: 2.5rem; }
    /* Encabezados */
    h1, h2, h3 { color: #fca311; }
    </style>
    """, unsafe_allow_html=True)

# ================= CREDENCIALES =================
# 1. TU NUEVA URL (Ya la puse yo)
SUPABASE_URL = "https://cxmwymmgsggzilcwotjv.supabase.co"

# 2. TU KEY (Pégala aquí abajo dentro de las comillas)
SUPABASE_KEY = "PEGA_AQUI_TU_ANON_PUBLIC_KEY"

# === CONFIGURACIÓN DEL GYM ===
PLANES = [
    "PLAN COMÚN",
    "PLAN VIP",
    "INSCRIPCIÓN",
    "VISITA DIARIA",
    "SEMANAL",
    "BEBIDA/SUPLEMENTO"
]

TIPOS_CLIENTE = ["Nuevo Ingreso", "Renovación", "Reingreso", "Empleado"]

USUARIOS = {
    "admin": {"pass": "gym2024", "rol": "admin", "nombre": "Gerencia"},
    "recepcion": {"pass": "caja1", "rol": "empleado", "nombre": "Recepción"}
}

# ================= CONEXIONES Y FUNCIONES =================
@st.cache_resource
def init_connection():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except:
        return None

supabase = init_connection()

@st.cache_data(ttl=3600)
def get_tasa_bcv():
    """Obtiene la tasa del BCV de una API pública o devuelve None"""
    try:
        # API PydolarVenezuela (Suele ser estable)
        url = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=bcv"
        req = requests.get(url, timeout=5)
        if req.status_code == 200:
            data = req.json()
            return float(data['monitors']['usd']['price'])
    except:
        pass
    return None

def limpiar_monto_ve(monto_input):
    """Convierte texto 1.200,00 a float 1200.00"""
    if pd.isna(monto_input): return 0.0
    texto = str(monto_input).upper().replace('BS', '').strip()
    # Caso 1200.50 (formato python)
    if '.' in texto and ',' not in texto:
        try: return float(texto)
        except: pass
    # Caso 1.200,50 (formato VE)
    texto = texto.replace('.', '').replace(',', '.')
    try: return float(texto)
    except: return 0.0

def get_pagos():
    if not supabase: return []
    response = supabase.table("pagos").select("*").order("id", desc=True).limit(1000).execute()
    return response.data

def actualizar_pago(id_pago, plan, tipo):
    supabase.table("pagos").update({"servicio": plan, "tipo_cliente": tipo}).eq("id", id_pago).execute()

def eliminar_pago(id_pago):
    supabase.table("pagos").delete().eq("id", id_pago).execute()

# ================= EXCEL REPORT =================
def generar_excel(df, tasa):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        # Formatos
        fmt_header = workbook.add_format({'bold': True, 'bg_color': '#fca311', 'border': 1})
        fmt_bs = workbook.add_format({'num_format': '#,##0.00 "Bs"', 'border': 1})
        fmt_usd = workbook.add_format({'num_format': '"$" #,##0.00', 'border': 1})
        
        # Hoja Data
        df_export = df.copy()
        df_export = df_export[['fecha_ve', 'referencia', 'monto_real', 'servicio', 'tipo_cliente']]
        df_export.columns = ['Fecha', 'Referencia', 'Bs', 'Plan', 'Tipo']
        df_export['Fecha'] = df_export['Fecha'].dt.tz_localize(None) # Quitar zona horaria para Excel
        
        df_export.to_excel(writer, sheet_name='Pagos Gym', index=False)
        ws = writer.sheets['Pagos Gym']
        ws.set_column('A:A', 20)
        ws.set_column('B:B', 15)
        ws.set_column('C:C', 15, fmt_bs)
        ws.set_column('D:E', 25)
        
    return output.getvalue()

# ================= LOGIN =================
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

params = st.query_params
if not st.session_state['logged_in'] and "auth" in params:
    try:
        creds = base64.b64decode(params["auth"]).decode().split(":")
        if creds[0] in USUARIOS and USUARIOS[creds[0]]["pass"] == creds[1]:
            st.session_state['logged_in'] = True
            st.session_state['user_role'] = USUARIOS[creds[0]]["rol"]
            st.session_state['user_name'] = USUARIOS[creds[0]]["nombre"]
    except: pass

def login_form():
    st.write("")
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<h1 style='text-align: center;'>🔐 GYM XPLOSSION</h1>", unsafe_allow_html=True)
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.button("INGRESAR", type="primary"):
            if u in USUARIOS and USUARIOS[u]["pass"] == p:
                st.session_state['logged_in'] = True
                st.session_state['user_role'] = USUARIOS[u]["rol"]
                st.session_state['user_name'] = USUARIOS[u]["nombre"]
                st.rerun()
            else:
                st.error("Acceso Incorrecto")

def logout():
    st.session_state['logged_in'] = False
    st.rerun()

# ================= APP PRINCIPAL =================
if not st.session_state['logged_in']:
    login_form()
else:
    # --- BARRA LATERAL ---
    with st.sidebar:
        st.title(f"Hola, {st.session_state['user_name']}")
        
        st.subheader("📅 Filtrar Fecha")
        filtro = st.selectbox("Ver:", ["Hoy", "Ayer", "Esta Semana", "Todo"])
        
        st.divider()
        st.subheader("💵 Tasa BCV")
        
        # Lógica BCV
        tasa_bcv = get_tasa_bcv()
        usar_manual = st.checkbox("Usar Tasa Manual", value=(tasa_bcv is None))
        
        if usar_manual or tasa_bcv is None:
            tasa_calculo = st.number_input("Tasa Manual (Bs/$)", value=60.0, format="%.2f")
            origen_tasa = "Manual"
        else:
            tasa_calculo = tasa_bcv
            origen_tasa = "BCV Oficial"
            st.success(f"Tasa cargada: {tasa_calculo} Bs")
            
        st.divider()
        if st.button("Cerrar Sesión"): logout()

    # --- PROCESAMIENTO DE DATOS ---
    raw_data = get_pagos()
    df = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()
    
    if not df.empty:
        df['monto_real'] = df['monto'].apply(limpiar_monto_ve)
        df['fecha_dt'] = pd.to_datetime(df['created_at'])
        # Ajuste Zona Horaria VENEZUELA
        if df['fecha_dt'].dt.tz is None: df['fecha_dt'] = df['fecha_dt'].dt.tz_localize('UTC')
        df['fecha_ve'] = df['fecha_dt'].dt.tz_convert('America/Caracas')
        df['fecha_fmt'] = df['fecha_ve'].dt.strftime('%d/%m %I:%M %p')
        
        # Aplicar Filtro Fecha
        hoy = datetime.now(df['fecha_ve'].dt.tz).date()
        if filtro == "Hoy":
            df = df[df['fecha_ve'].dt.date == hoy]
        elif filtro == "Ayer":
            df = df[df['fecha_ve'].dt.date == (hoy - timedelta(days=1))]
        elif filtro == "Esta Semana":
            inicio = hoy - timedelta(days=hoy.weekday())
            df = df[df['fecha_ve'].dt.date >= inicio]

    # --- DASHBOARD ---
    st.title("🏋️‍♂️ Control de Caja - XPLOSSION")
    st.caption(f"Calculando a Tasa: **{tasa_calculo} Bs/$** ({origen_tasa})")

    if df.empty:
        st.info("No hay movimientos registrados para este período.")
    else:
        # Métricas
        bs_total = df['monto_real'].sum()
        usd_total = bs_total / tasa_calculo
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Ingreso (Bs)", f"{bs_total:,.2f}")
        c2.metric("Estimado (USD)", f"{usd_total:,.2f}")
        c3.download_button(
            "📂 Bajar Reporte", 
            data=generar_excel(df, tasa_calculo), 
            file_name=f"Cierre_Gym_{filtro}.xlsx"
        )
        
        st.divider()
        
        # Tabla de Pagos
        for i, row in df.iterrows():
            # Estado del pago (Verde si ya tiene Plan, Rojo si no)
            listo = row['servicio'] and row['tipo_cliente']
            color_borde = "green" if listo else "#ff4b4b" # Rojo Streamlit
            
            with st.container(border=True):
                col_datos, col_edit = st.columns([3, 1])
                
                with col_datos:
                    st.markdown(f"**Ref: {row['referencia']}** | 🕒 {row['fecha_fmt']}")
                    st.markdown(f"<h3 style='margin:0; color:{color_borde}'>Bs. {row['monto']}</h3>", unsafe_allow_html=True)
                    if listo:
                        st.caption(f"✅ {row['servicio']} ({row['tipo_cliente']})")
                    else:
                        st.caption("⚠️ PAGO SIN CLASIFICAR")
                
                with col_edit:
                    with st.popover("Editar"):
                        st.write("Asignar Plan:")
                        # Índices para los selectbox
                        ix_p = PLANES.index(row['servicio']) if row['servicio'] in PLANES else 0
                        ix_t = TIPOS_CLIENTE.index(row['tipo_cliente']) if row['tipo_cliente'] in TIPOS_CLIENTE else 0
                        
                        nuevo_plan = st.selectbox("Plan", PLANES, index=ix_p, key=f"p_{row['id']}")
                        nuevo_tipo = st.selectbox("Tipo", TIPOS_CLIENTE, index=ix_t, key=f"t_{row['id']}")
                        
                        if st.button("💾 Guardar", key=f"save_{row['id']}"):
                            actualizar_pago(row['id'], nuevo_plan, nuevo_tipo)
                            st.rerun()
                        
                        if st.session_state['user_role'] == 'admin':
                            st.divider()
                            if st.button("🗑️ Borrar", key=f"del_{row['id']}"):
                                eliminar_pago(row['id'])
                                st.rerun()
                                
        # Refresco automático cada 10s
        time.sleep(10)
        st.rerun()
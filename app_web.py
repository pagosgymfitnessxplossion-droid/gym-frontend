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

# ESTILOS
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: white; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    [data-testid="stMetricValue"] { color: #fca311; font-size: 2.5rem; }
    h1, h2, h3 { color: #fca311; }
    </style>
    """, unsafe_allow_html=True)

# ================= CREDENCIALES EXACTAS =================
# ID del Proyecto: cxmwymmgsggzilcwotjv
SUPABASE_URL = "https://cxmwymmgsggzilcwotjv.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN4bXd5bW1nc2dnemlsY3dvdGp2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzExNDAxMDEsImV4cCI6MjA4NjcxNjEwMX0.-3a_zppjlwprHG4qw-PQfdEPPPee2-iKdAlXLaQZeSM"

# === CONFIGURACIÓN GYM ===
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

# ================= CONEXIONES =================
# Usamos ttl=0 para forzar reconexión si hay error y no cachear credenciales viejas
@st.cache_resource(ttl=0)
def init_connection():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Error conectando a Supabase: {e}")
        return None

supabase = init_connection()

@st.cache_data(ttl=3600)
def get_tasa_bcv():
    try:
        url = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=bcv"
        req = requests.get(url, timeout=5)
        if req.status_code == 200:
            data = req.json()
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
        # Intentamos obtener los datos. Si falla, mostramos error detallado
        response = supabase.table("pagos").select("*").order("id", desc=True).limit(1000).execute()
        return response.data
    except Exception as e:
        st.error(f"Error al leer la base de datos: {str(e)}")
        st.info("Intenta recargar la página o verifica que la tabla 'pagos' exista en Supabase.")
        return []

def actualizar_pago(id_pago, plan, tipo):
    try:
        supabase.table("pagos").update({"servicio": plan, "tipo_cliente": tipo}).eq("id", id_pago).execute()
        st.toast("✅ Actualizado correctamente")
    except Exception as e:
        st.error(f"No se pudo guardar: {e}")

def eliminar_pago(id_pago):
    try:
        supabase.table("pagos").delete().eq("id", id_pago).execute()
        st.toast("🗑️ Eliminado")
    except Exception as e:
        st.error(f"No se pudo eliminar: {e}")

# ================= EXCEL =================
def generar_excel(df, tasa):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        fmt_header = workbook.add_format({'bold': True, 'bg_color': '#fca311', 'border': 1})
        fmt_bs = workbook.add_format({'num_format': '#,##0.00 "Bs"', 'border': 1})
        
        df_export = df.copy()
        df_export = df_export[['fecha_ve', 'referencia', 'monto_real', 'servicio', 'tipo_cliente']]
        df_export.columns = ['Fecha', 'Referencia', 'Bs', 'Plan', 'Tipo']
        df_export['Fecha'] = df_export['Fecha'].dt.tz_localize(None)
        
        df_export.to_excel(writer, sheet_name='Pagos Gym', index=False)
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
    st.query_params.clear()
    st.rerun()

# ================= APP =================
if not st.session_state['logged_in']:
    login_form()
else:
    with st.sidebar:
        st.title(f"Hola, {st.session_state['user_name']}")
        filtro = st.selectbox("Ver:", ["Hoy", "Ayer", "Esta Semana", "Todo"])
        st.divider()
        tasa_bcv = get_tasa_bcv()
        if tasa_bcv:
            tasa_calculo = tasa_bcv
            origen_tasa = "BCV Oficial"
            st.success(f"Tasa: {tasa_calculo} Bs")
        else:
            tasa_calculo = st.number_input("Tasa Manual", value=60.0)
            origen_tasa = "Manual"
        st.divider()
        if st.button("Salir"): logout()

    # Carga de datos
    raw_data = get_pagos()
    df = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()

    if not df.empty:
        df['monto_real'] = df['monto'].apply(limpiar_monto_ve)
        df['fecha_dt'] = pd.to_datetime(df['created_at'])
        if df['fecha_dt'].dt.tz is None: df['fecha_dt'] = df['fecha_dt'].dt.tz_localize('UTC')
        df['fecha_ve'] = df['fecha_dt'].dt.tz_convert('America/Caracas')
        df['fecha_fmt'] = df['fecha_ve'].dt.strftime('%d/%m %I:%M %p')

        # Filtros
        hoy = datetime.now(df['fecha_ve'].dt.tz).date()
        if filtro == "Hoy": df = df[df['fecha_ve'].dt.date == hoy]
        elif filtro == "Ayer": df = df[df['fecha_ve'].dt.date == (hoy - timedelta(days=1))]
        elif filtro == "Esta Semana": df = df[df['fecha_ve'].dt.date >= (hoy - timedelta(days=hoy.weekday()))]

    st.title("🏋️‍♂️ Control GYM XPLOSSION")
    
    if df.empty:
        st.info("No hay pagos registrados o error de conexión.")
    else:
        bs_total = df['monto_real'].sum()
        usd_total = bs_total / tasa_calculo
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Bs", f"{bs_total:,.2f}")
        c2.metric("Total USD", f"{usd_total:,.2f}")
        c3.download_button("📂 Bajar Excel", data=generar_excel(df, tasa_calculo), file_name="Reporte.xlsx")
        
        st.divider()
        for i, row in df.iterrows():
            listo = row['servicio'] and row['tipo_cliente']
            color = "green" if listo else "#ff4b4b"
            with st.container(border=True):
                c_info, c_edit = st.columns([3, 1])
                with c_info:
                    st.markdown(f"**Ref: {row['referencia']}** | {row['fecha_fmt']}")
                    st.markdown(f"<h3 style='color:{color}'>Bs. {row['monto']}</h3>", unsafe_allow_html=True)
                    if listo: st.caption(f"✅ {row['servicio']} ({row['tipo_cliente']})")
                with c_edit:
                    with st.popover("Editar"):
                        ix_p = PLANES.index(row['servicio']) if row['servicio'] in PLANES else 0
                        ix_t = TIPOS_CLIENTE.index(row['tipo_cliente']) if row['tipo_cliente'] in TIPOS_CLIENTE else 0
                        np = st.selectbox("Plan", PLANES, index=ix_p, key=f"p_{row['id']}")
                        nt = st.selectbox("Tipo", TIPOS_CLIENTE, index=ix_t, key=f"t_{row['id']}")
                        if st.button("Guardar", key=f"s_{row['id']}"):
                            actualizar_pago(row['id'], np, nt)
                            st.rerun()
                        if st.session_state['user_role'] == 'admin':
                            if st.button("Borrar", key=f"d_{row['id']}"):
                                eliminar_pago(row['id'])
                                st.rerun()
    
    time.sleep(10)
    st.rerun()

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from io import BytesIO

# Configuración Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["GSHEETS_CREDS"], scope)
client = gspread.authorize(creds)

@st.cache_data(ttl=300)
def load_data():
    try:
        sheet = client.open_by_key("1VrcE5I9ZUpdps-t6rDl9cpmQGuFtsdmjlkaLFwG895g")
        datos = pd.DataFrame(sheet.worksheet("Datos").get_all_records())
        users = pd.DataFrame(sheet.worksheet("Usuarios").get_all_records())
        return datos, users
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame(), pd.DataFrame()

def authenticate(users_df, user, password):
    if users_df.empty:
        return False, None
    usuarios = users_df["Usuario"].astype(str).str.strip().str.lower()
    contrasenas = users_df["Contraseña"].astype(str).str.strip()
    matched_users = users_df[
        (usuarios == user.lower()) &
        (contrasenas == password)
    ]
    if not matched_users.empty:
        return True, matched_users.iloc[0].get("Usuario")
    return False, None

# Carga de datos
df, users_df = load_data()

# Login en el sidebar
st.set_page_config(layout="wide")
if "auth" not in st.session_state:
    st.session_state.auth = False
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.auth:
    st.sidebar.title("Inicio de Sesión")
    user = st.sidebar.text_input("Usuario").strip()
    password = st.sidebar.text_input("Contraseña", type="password").strip()
    if st.sidebar.button("Ingresar"):
        is_auth, usuario = authenticate(users_df, user, password)
        if is_auth:
            st.session_state.auth = True
            st.session_state.user = usuario
            st.sidebar.success("Acceso concedido")
        else:
            st.sidebar.error("Credenciales incorrectas")
    st.stop()

# Obtener el nombre del usuario autenticado
usuario_actual = st.session_state.user
nombre_usuario = ""
if not users_df.empty and "Usuario" in users_df.columns and "Nombre" in users_df.columns:
    mask = users_df["Usuario"].astype(str) == str(usuario_actual)
    if mask.any():
        nombre_usuario = users_df.loc[mask, "Nombre"].values[0]
    else:
        nombre_usuario = str(usuario_actual)
else:
    nombre_usuario = str(usuario_actual)

# Mostrar saludo arriba (sin ###)
st.header(f"Bienvenido {nombre_usuario}!")

# Limpia y normaliza los datos para evitar problemas de espacios o mayúsculas
df["Proveedor"] = df["Proveedor"].astype(str).str.strip().str.lower()
usuario_actual_limpio = str(usuario_actual).strip().lower()

# Filtra la tabla: solo muestra datos donde Proveedor == usuario autenticado
df_usuario = df[df["Proveedor"] == usuario_actual_limpio]

if df_usuario.empty:
    st.warning("No hay datos para mostrar para este usuario.")
    st.button("Cerrar sesión", on_click=lambda: st.session_state.clear())
    st.stop()

# --- FILTRO DE ESTADO CON BOTONES VERTICALES ---
estados = sorted(df_usuario["Estado"].dropna().astype(str).str.strip().unique().tolist())
estados = ["Todos"] + estados

if "Estado" not in st.session_state:
    st.session_state["Estado"] = "Todos"

col1, col2 = st.columns([1, 1])

with col1:
    # Gráfico de torta Estado (más pequeño)
    estado_counts = df_usuario["Estado"].dropna().astype(str).str.strip()
    estado_counts = estado_counts[estado_counts != ""]
    estado_counts = estado_counts.value_counts()
    fig, ax = plt.subplots(figsize=(3, 3))
    ax.pie(estado_counts, labels=estado_counts.index, autopct="%1.1f%%")
    ax.axis("equal")
    st.pyplot(fig)

with col2:
    # Espacio extra antes de los botones
    st.markdown("<div style='margin-top:70px'></div>", unsafe_allow_html=True)
    # Subtítulo y número de filas en verde
    filtered_df = df_usuario.copy()
    if st.session_state["Estado"] != "Todos":
        filtered_df = df_usuario[df_usuario["Estado"].astype(str).str.strip() == st.session_state["Estado"]]
    st.markdown(
        f"<div style='display:flex;align-items:center;gap:10px;'>"
        f"<span style='font-size:1.2em;font-weight:bold;'>Estado de Liquidaciones:</span>"
        f"<span style='background-color:#21c96b;color:white;padding:2px 10px;border-radius:10px;font-size:1em;'>"
        f"{len(filtered_df)}</span></div>",
        unsafe_allow_html=True
    )

    # Botones verticales de filtro de Estado, todos del mismo ancho
    max_estado_len = max(len(e) for e in estados)
    button_style = f"width:40%;min-width:60px;max-width:60px;padding:8px 0;margin-bottom:5px;font-size:1em;"
    for estado in estados:
        btn_clicked = st.button(
            estado,
            key=f"estado_{estado}",
            help=f"Filtrar por {estado}",
            use_container_width=True
        )
        if btn_clicked:
            st.session_state["Estado"] = estado
            st.rerun()


# Aplicar filtro de Estado
if st.session_state["Estado"] != "Todos":
    filtered_df = df_usuario[df_usuario["Estado"].astype(str).str.strip() == st.session_state["Estado"]]
else:
    filtered_df = df_usuario.copy()

# Excluir columnas no deseadas
columnas_excluir = [
    "Proveedor", "Nombre Acreedor", "FechaLib SP", "Contrato marco", "Pos Contrato",
    "Liquidado", "SP Lib", "Tiene OS", "OS Lib", "HES"
]
columnas_mostrar = [col for col in filtered_df.columns if col not in columnas_excluir]

# Mostrar tabla
st.dataframe(filtered_df[columnas_mostrar], height=400)

# Exportar a XLSX
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos')
    return output.getvalue()

st.download_button(
    "Exportar a Excel",
    data=to_excel(filtered_df[columnas_mostrar]),
    file_name="datos_filtrados.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

st.button("Cerrar sesión", on_click=lambda: st.session_state.clear())
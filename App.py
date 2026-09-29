import streamlit as st
import pandas as pd
import gspread
import plotly.express as px
import plotly.graph_objects as go
import re
import unicodedata


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="SISTEMA WES JAPAN IMPO PEREZ",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# CONFIGURACIÓN GOOGLE SHEETS
# ============================================================

SHEET_ID = "1eshOAGnZVw8i0zv5xXxd4x6gn1Ufc9hYRnu-KIZyA9s"

HOJA_PADRE = "VENTAS"
HOJA_HIJA = "VENTA"


# ============================================================
# VENDEDORES Y SUS COLORES
# ============================================================
# "claves" son palabras que identifican al vendedor si en la
# hoja aparece su nombre. También se reconoce por su código
# (1, 3, 4, 6, 9, 10, 13, 14).

VENDEDORES = {

    "1": {
        "nombre": "DIRECTOR DE VENTAS",
        "color": "#073599",   # azul oscuro
        "claves": ["DIRECTOR"]
    },

    "3": {
        "nombre": "ANADEYRA RAMOS PEREZ",
        "color": "#F70B9C",   # rosado oscuro
        "claves": ["ANADEYRA"]
    },

    "4": {
        "nombre": "LUIS TUCHAN",
        "color": "#F78C0B",   # anaranjado
        "claves": ["TUCHAN"]
    },

    "6": {
        "nombre": "SAMUEL RODRIGUEZ PRADO",
        "color": "#2E9E44",   # verde
        "claves": ["SAMUEL"]
    },

    "9": {
        "nombre": "WILLIAN WALDEMAR PRIMERO CEBALLOS",
        "color": "#AA8405EB",   # dorado
        "claves": ["WILLIAN", "CEBALLOS"]
    },

    "10": {
        "nombre": "DAMIAN MOTA",
        "color": "#09E3EB",   # celeste
        "claves": ["DAMIAN"]
    },

    "13": {
        "nombre": "GERENCIA IP",
        "color": "#4A4A4A",   # gris oscuro
        "claves": ["GERENCIA"]
    },

    "14": {
        "nombre": "CHESNY PEREZ BATRES",
        "color": "#4B0469",   # púrpura
        "claves": ["CHESNY"]
    }

}

COLOR_SIN_VENDEDOR = "#9E9E9E"

ETIQUETA_SIN_VENDEDOR = "SIN VENDEDOR"


def etiqueta_de_codigo(codigo):

    return f"{codigo} - {VENDEDORES[codigo]['nombre']}"


ETIQUETAS_ORDEN = [
    etiqueta_de_codigo(c)
    for c in VENDEDORES
]

COLORES_VENDEDOR = {
    etiqueta_de_codigo(c): info["color"]
    for c, info in VENDEDORES.items()
}

COLORES_VENDEDOR[ETIQUETA_SIN_VENDEDOR] = COLOR_SIN_VENDEDOR


def quitar_acentos(texto):

    texto = unicodedata.normalize(
        "NFD",
        str(texto)
    )

    return "".join(
        c
        for c in texto
        if unicodedata.category(c) != "Mn"
    ).upper().strip()


def identificar_vendedor(valor):

    if pd.isna(valor):
        return None

    texto = quitar_acentos(valor)

    if texto == "":
        return None

    # Por nombre
    for codigo, info in VENDEDORES.items():

        for clave in info["claves"]:

            if clave in texto:
                return codigo

    # Por código (ejemplo: "3", "3.0", "3 - ANADEYRA")
    coincidencia = re.match(
        r"^\s*(\d+)",
        texto
    )

    if coincidencia:

        codigo = coincidencia.group(1)

        if codigo in VENDEDORES:
            return codigo

    return None


def color_texto_contraste(color_hex):

    color_hex = color_hex.lstrip("#")

    r = int(color_hex[0:2], 16)
    g = int(color_hex[2:4], 16)
    b = int(color_hex[4:6], 16)

    luminancia = (
        0.299 * r
        +
        0.587 * g
        +
        0.114 * b
    ) / 255

    if luminancia > 0.6:
        return "#000000"

    return "#FFFFFF"


def agregar_etiqueta_vendedor(df):

    if df.empty:
        return df

    candidatos = [
        c
        for c in ("VENDEDOR", "NOMBRE VENDEDOR")
        if c in df.columns
    ]

    if not candidatos:

        df["VENDEDOR CODIGO"] = ""
        df["VENDEDOR ETIQUETA"] = ETIQUETA_SIN_VENDEDOR

        return df

    codigos = pd.Series(
        [None] * len(df),
        index=df.index,
        dtype="object"
    )

    for columna in candidatos:

        encontrados = df[columna].apply(
            identificar_vendedor
        )

        codigos = codigos.where(
            codigos.notna(),
            encontrados
        )

    original = (
        df[candidatos[0]]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    etiquetas = []

    for codigo, texto in zip(codigos, original):

        if codigo is not None and pd.notna(codigo):

            etiquetas.append(
                etiqueta_de_codigo(codigo)
            )

        elif texto != "":

            etiquetas.append(texto)

        else:

            etiquetas.append(
                ETIQUETA_SIN_VENDEDOR
            )

    df["VENDEDOR CODIGO"] = (
        codigos
        .fillna("")
        .astype(str)
    )

    df["VENDEDOR ETIQUETA"] = etiquetas

    return df


def estilizar_por_vendedor(df_mostrar, etiquetas):

    def estilo_fila(fila):

        etiqueta = etiquetas.get(
            fila.name,
            ETIQUETA_SIN_VENDEDOR
        )

        color = COLORES_VENDEDOR.get(
            etiqueta,
            COLOR_SIN_VENDEDOR
        )

        estilos = []

        for columna in fila.index:

            if columna in ("VENDEDOR", "NOMBRE VENDEDOR"):

                estilos.append(
                    f"background-color: {color}; "
                    f"color: {color_texto_contraste(color)}; "
                    f"font-weight: bold"
                )

            else:

                estilos.append(
                    f"background-color: {color}22; "
                    f"color: {color}; "
                    f"font-weight: 600"
                )

        return estilos

    return df_mostrar.style.apply(
        estilo_fila,
        axis=1
    )


# ============================================================
# CONEXIÓN GOOGLE SHEETS
# ============================================================

@st.cache_resource
def conectar_google_sheets():

    gc = gspread.service_account(
        filename="credentials.json"
    )

    spreadsheet = gc.open_by_key(
        SHEET_ID
    )

    hoja_padre = spreadsheet.worksheet(
        HOJA_PADRE
    )

    hoja_hija = spreadsheet.worksheet(
        HOJA_HIJA
    )

    return spreadsheet, hoja_padre, hoja_hija


# ============================================================
# CONECTAR
# ============================================================

try:

    spreadsheet, hoja_ventas, hoja_venta = (
        conectar_google_sheets()
    )

except Exception as e:

    st.error(
        "❌ Error conectando con Google Sheets"
    )

    st.code(str(e))

    st.stop()


# ============================================================
# CARGAR HOJA VENTAS
# ============================================================

@st.cache_data(ttl=30)
def cargar_ventas():

    datos = hoja_ventas.get_all_records()

    return pd.DataFrame(datos)


# ============================================================
# CARGAR HOJA VENTA
# ============================================================

@st.cache_data(ttl=30)
def cargar_venta_detalle():

    datos = hoja_venta.get_all_records()

    return pd.DataFrame(datos)


# ============================================================
# CARGAR DATOS
# ============================================================

try:

    df_ventas = cargar_ventas()
    df_venta = cargar_venta_detalle()

except Exception as e:

    st.error(
        "❌ No se pudieron cargar las hojas."
    )

    st.code(str(e))

    st.stop()


# ============================================================
# VALIDAR VENTAS
# ============================================================

if df_ventas.empty:

    st.warning(
        "⚠️ La hoja VENTAS está vacía."
    )

    st.stop()


# ============================================================
# LIMPIAR NOMBRES DE COLUMNAS
# ============================================================

df_ventas.columns = [
    str(c).strip()
    for c in df_ventas.columns
]

if not df_venta.empty:

    df_venta.columns = [
        str(c).strip()
        for c in df_venta.columns
    ]


# ============================================================
# FUNCIÓN PARA CONVERTIR MONEDAS / NÚMEROS
# ============================================================

def convertir_numero(valor):

    if pd.isna(valor):
        return 0.0

    texto = str(valor).strip()

    if texto == "":
        return 0.0

    # Quitar símbolo de moneda
    texto = texto.replace("Q", "")
    texto = texto.replace("q", "")

    # Quitar espacios
    texto = texto.replace(" ", "")

    # Quitar caracteres no numéricos excepto . , -
    texto = re.sub(
        r"[^0-9,.\-]",
        "",
        texto
    )

    if texto == "":
        return 0.0

    # --------------------------------------------------------
    # FORMATO:
    #
    # 1,234.56
    # 1.234,56
    # 1234.56
    # 1234,56
    # --------------------------------------------------------

    if "," in texto and "." in texto:

        ultima_coma = texto.rfind(",")
        ultimo_punto = texto.rfind(".")

        if ultima_coma > ultimo_punto:

            # Formato 1.234,56
            texto = texto.replace(".", "")
            texto = texto.replace(",", ".")

        else:

            # Formato 1,234.56
            texto = texto.replace(",", "")

    elif "," in texto:

        partes = texto.split(",")

        if len(partes[-1]) == 2:

            texto = texto.replace(",", ".")

        else:

            texto = texto.replace(",", "")

    elif texto.count(".") > 1:

        partes = texto.split(".")

        if len(partes[-1]) == 2:

            decimal = partes[-1]

            entero = "".join(
                partes[:-1]
            )

            texto = entero + "." + decimal

        else:

            texto = texto.replace(".", "")

    try:

        return float(texto)

    except Exception:

        return 0.0


# ============================================================
# FUNCIÓN ROBUSTA PARA FECHAS
# ============================================================

def convertir_fecha(serie):

    if serie.empty:
        return serie

    if pd.api.types.is_datetime64_any_dtype(serie):

        return pd.to_datetime(
            serie,
            errors="coerce"
        )

    serie_texto = (
        serie
        .fillna("")
        .astype(str)
        .str.strip()
    )

    resultado = pd.Series(
        pd.NaT,
        index=serie.index,
        dtype="datetime64[ns]"
    )

    # DD/MM/YYYY
    mascara = (
        serie_texto
        .str.match(
            r"^\d{1,2}/\d{1,2}/\d{4}$",
            na=False
        )
    )

    if mascara.any():

        resultado.loc[mascara] = pd.to_datetime(
            serie_texto.loc[mascara],
            format="%d/%m/%Y",
            errors="coerce"
        )

    # DD-MM-YYYY
    mascara2 = (
        resultado.isna()
        &
        serie_texto.str.match(
            r"^\d{1,2}-\d{1,2}-\d{4}$",
            na=False
        )
    )

    if mascara2.any():

        resultado.loc[mascara2] = pd.to_datetime(
            serie_texto.loc[mascara2],
            format="%d-%m-%Y",
            errors="coerce"
        )

    # YYYY-MM-DD
    mascara3 = resultado.isna()

    if mascara3.any():

        resultado.loc[mascara3] = pd.to_datetime(
            serie_texto.loc[mascara3],
            format="%Y-%m-%d",
            errors="coerce"
        )

    # Último intento
    mascara4 = resultado.isna()

    if mascara4.any():

        resultado.loc[mascara4] = pd.to_datetime(
            serie_texto.loc[mascara4],
            dayfirst=True,
            errors="coerce"
        )

    return resultado


# ============================================================
# FUNCIÓN PARA FORZAR COLUMNAS DE TEXTO
# ============================================================

def convertir_columna_texto(df, columna):

    if columna in df.columns:

        df[columna] = (
            df[columna]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    return df


# ============================================================
# NO VENTA = TEXTO
# ============================================================

if "NO VENTA" in df_ventas.columns:

    df_ventas["NO VENTA"] = (
        df_ventas["NO VENTA"]
        .fillna("")
        .astype(str)
        .str.strip()
    )


if (
    not df_venta.empty
    and
    "NO VENTA" in df_venta.columns
):

    df_venta["NO VENTA"] = (
        df_venta["NO VENTA"]
        .fillna("")
        .astype(str)
        .str.strip()
    )


# ============================================================
# ID = TEXTO
# ============================================================

if (
    not df_venta.empty
    and
    "ID" in df_venta.columns
):

    df_venta["ID"] = (
        df_venta["ID"]
        .fillna("")
        .astype(str)
        .str.strip()
    )


# ============================================================
# COLUMNAS NUMÉRICAS DE VENTAS
# ============================================================

columnas_numericas_ventas = [

    "TOTAL DE VENTA",
    "PAGO",
    "TOTAL VENTA FISICA",
    "SALDO",
    "NO PIEZAS",
    "DIAS HASTA HOY"

]


for columna in columnas_numericas_ventas:

    if columna in df_ventas.columns:

        df_ventas[columna] = (
            df_ventas[columna]
            .apply(convertir_numero)
        )


# ============================================================
# FECHA DE VENTAS
# ============================================================

if "FECHA" in df_ventas.columns:

    df_ventas["FECHA"] = convertir_fecha(
        df_ventas["FECHA"]
    )


# ============================================================
# COLUMNAS TEXTO DE VENTAS
# ============================================================

columnas_texto_ventas = [

    "VENDEDOR",
    "CLIENTE",
    "COMPROBANTE",
    "ARCHIVO",
    "TRANSPORTE",
    "NOTA",
    "STATUS",
    "NOMBRE ASESOR",
    "NOMBRE CLIENTE",
    "ADMINISTRACION VENTA",
    "NO GUIA ENTREGA",
    "DESTINO",
    "UPDATES",
    "NIT",
    "TOTAL EN LETRAS",
    "DTE",
    "ARCHIVO DTE",
    "NO ARCHIVO DTE",
    "FACTURADO",
    "DELETE",
    "GUIA PDF",
    "NO GUIA DE TRANSPORTE",
    "TIPO DE PAGO",
    "RUTA",
    "SECCION",
    "MONTH",
    "YEAR",
    "NOMBRE EMPRESA",
    "PAGO STATUS"

]


for columna in columnas_texto_ventas:

    convertir_columna_texto(
        df_ventas,
        columna
    )


# ============================================================
# COLUMNAS NUMÉRICAS DE VENTA
# ============================================================

columnas_numericas_venta = [

    "CANTIDAD",
    "PRECIO",
    "PRECIO DE VENTA",
    "SUBTOTAL",
    "TOTAL DE VENTA",
    "PRECIO OFERTA",
    "PRECIO CONTADO",
    "MONTO DEL ABONO",
    "NUMERO ABONOS",
    "Numero Abono",
    "Monto Abono",
    "IVA",
    "ItemTotalMontoImpuesto",
    "ItemGranTotal",
    "ItemImpuestoMontoGravable",
    "dte:GranTotal"

]


if not df_venta.empty:

    for columna in columnas_numericas_venta:

        if columna in df_venta.columns:

            df_venta[columna] = (
                df_venta[columna]
                .apply(convertir_numero)
            )


# ============================================================
# FECHA HOJA VENTA
# ============================================================

if (
    not df_venta.empty
    and
    "FECHA" in df_venta.columns
):

    df_venta["FECHA"] = convertir_fecha(
        df_venta["FECHA"]
    )


# ============================================================
# COLUMNAS TEXTO DE VENTA
# ============================================================

columnas_texto_venta = [

    "ID",
    "NO VENTA",
    "PRODUCTO",
    "VENDEDOR",
    "DESCRIPCION",
    "UBICACION",
    "OFERTA",
    "QR",
    "ACTUALIZAR",
    "IMAGEN",
    "NOMBRE VENDEDOR",
    "NOMBRE CLIENTE",
    "DTE",
    "FACTURADO",
    "DELETE",
    "TIPO DE PAGO",
    "RUTA",
    "SECCION",
    "MONTH",
    "YEAR",
    "NOMBRE EMPRESA",
    "CODIGO CLIENTE",
    "NumeroLinea",
    "BienOServicio",
    "DESCUENTOS",
    "OTROS DESCUENTOS",
    "NOTA",
    "NIT Receptor",
    "Nombre Receptor",
    "NUMERO AUTORIZACION",
    "SERIE",
    "NUMERO DE DTE",
    "NOMBRE EMISOR",
    "Nit Emisor",
    "EMPRESA EMISORA",
    "DIRECCION EMISOR",
    "EXCEL ARCHIVO",
    "DIRECCION",
    "Descripcion DTE",
    "ItemImpuestoNombreCorto",
    "TRANSPORTE",
    "DESARROLLO",
    "B O M",
    "TELEFONO"

]


if not df_venta.empty:

    for columna in columnas_texto_venta:

        convertir_columna_texto(
            df_venta,
            columna
        )


# ============================================================
# PROTECCIÓN ADICIONAL PYARROW - VENTA
# ============================================================

if not df_venta.empty:

    columnas_protegidas = set(
        columnas_numericas_venta
    )

    columnas_protegidas.add("FECHA")

    for columna in df_venta.columns:

        if (
            df_venta[columna].dtype == "object"
            and
            columna not in columnas_protegidas
        ):

            df_venta[columna] = (
                df_venta[columna]
                .fillna("")
                .astype(str)
                .str.strip()
            )


# ============================================================
# PROTECCIÓN PYARROW - VENTAS
# ============================================================

columnas_protegidas_ventas = set(
    columnas_numericas_ventas
)

columnas_protegidas_ventas.add("FECHA")

for columna in df_ventas.columns:

    if (
        df_ventas[columna].dtype == "object"
        and
        columna not in columnas_protegidas_ventas
    ):

        df_ventas[columna] = (
            df_ventas[columna]
            .fillna("")
            .astype(str)
            .str.strip()
        )


# ============================================================
# AGREGAR ETIQUETA DE VENDEDOR (PARA COLORES)
# ============================================================

df_ventas = agregar_etiqueta_vendedor(
    df_ventas
)

if not df_venta.empty:

    df_venta = agregar_etiqueta_vendedor(
        df_venta
    )


# Vendedores que no están en la lista reciben color gris

for _df in (df_ventas, df_venta):

    if (
        not _df.empty
        and
        "VENDEDOR ETIQUETA" in _df.columns
    ):

        for _etiqueta in _df["VENDEDOR ETIQUETA"].unique():

            if _etiqueta not in COLORES_VENDEDOR:

                COLORES_VENDEDOR[_etiqueta] = (
                    COLOR_SIN_VENDEDOR
                )


# ============================================================
# TÍTULO
# ============================================================

st.title(
    "📊 SISTEMA DE VENTAS DE WES JAPAN IMPO PEREZ"
)

st.caption(
    "REPORTE DE VENTAS CON SUS DATOS COMPLETOS"
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header(
    "🔎 FILTROS"
)


# ============================================================
# LEYENDA DE COLORES DE VENDEDORES
# ============================================================

leyenda_html = "<b>🎨 VENDEDORES</b><br>"

for etiqueta in ETIQUETAS_ORDEN:

    color = COLORES_VENDEDOR[etiqueta]

    leyenda_html += (
        f"<div style='margin-top:4px;'>"
        f"<span style='display:inline-block;"
        f"width:14px;height:14px;border-radius:3px;"
        f"background:{color};margin-right:8px;"
        f"vertical-align:middle;'></span>"
        f"<span style='font-size:13px;'>{etiqueta}</span>"
        f"</div>"
    )

st.sidebar.markdown(
    leyenda_html,
    unsafe_allow_html=True
)

st.sidebar.markdown("---")


# ============================================================
# FECHA
# ============================================================

rango_fechas = None

if "FECHA" in df_ventas.columns:

    fechas = (
        df_ventas["FECHA"]
        .dropna()
    )

    if not fechas.empty:

        fecha_min = fechas.min().date()
        fecha_max = fechas.max().date()

        rango_fechas = st.sidebar.date_input(

            "📅 FECHA DE VENTA",

            value=(
                fecha_min,
                fecha_max
            ),

            min_value=fecha_min,

            max_value=fecha_max,

            format="DD/MM/YYYY"

        )


# ============================================================
# FUNCIÓN PARA CREAR OPCIONES
# ============================================================

def obtener_opciones(df, columna):

    if columna not in df.columns:
        return []

    valores = (
        df[columna]
        .fillna("")
        .astype(str)
        .str.strip()
        .unique()
    )

    return sorted(
        [
            x
            for x in valores
            if x
        ]
    )


# ============================================================
# VENDEDOR
# ============================================================

vendedor_seleccionado = []

if "VENDEDOR ETIQUETA" in df_ventas.columns:

    presentes = obtener_opciones(
        df_ventas,
        "VENDEDOR ETIQUETA"
    )

    vendedores = (
        [
            e
            for e in ETIQUETAS_ORDEN
            if e in presentes
        ]
        +
        [
            e
            for e in presentes
            if e not in ETIQUETAS_ORDEN
        ]
    )

    vendedor_seleccionado = st.sidebar.multiselect(

        "👤 VENDEDOR",

        vendedores

    )


# ============================================================
# NOMBRE ASESOR
# ============================================================

asesor_seleccionado = []

if "NOMBRE ASESOR" in df_ventas.columns:

    asesores = obtener_opciones(
        df_ventas,
        "NOMBRE ASESOR"
    )

    asesor_seleccionado = st.sidebar.multiselect(

        "👔 NOMBRE ASESOR",

        asesores

    )


# ============================================================
# EMPRESA
# ============================================================

empresa_seleccionada = []

if "NOMBRE EMPRESA" in df_ventas.columns:

    empresas = obtener_opciones(
        df_ventas,
        "NOMBRE EMPRESA"
    )

    empresa_seleccionada = st.sidebar.multiselect(

        "🏢 EMPRESA",

        empresas

    )


# ============================================================
# TIPO DE PAGO
# ============================================================

pago_seleccionado = []

if "TIPO DE PAGO" in df_ventas.columns:

    tipos_pago = obtener_opciones(
        df_ventas,
        "TIPO DE PAGO"
    )

    pago_seleccionado = st.sidebar.multiselect(

        "💳 TIPO DE PAGO",

        tipos_pago

    )


# ============================================================
# STATUS
# ============================================================

status_seleccionado = []

if "STATUS" in df_ventas.columns:

    estados = obtener_opciones(
        df_ventas,
        "STATUS"
    )

    status_seleccionado = st.sidebar.multiselect(

        "📌 STATUS",

        estados

    )


# ============================================================
# DESTINO
# ============================================================

destino_seleccionado = []

if "DESTINO" in df_ventas.columns:

    destinos = obtener_opciones(
        df_ventas,
        "DESTINO"
    )

    destino_seleccionado = st.sidebar.multiselect(

        "📍 DESTINO",

        destinos

    )


# ============================================================
# PRODUCTO
# ============================================================

producto_seleccionado = []

if (
    not df_venta.empty
    and
    "PRODUCTO" in df_venta.columns
):

    productos = obtener_opciones(
        df_venta,
        "PRODUCTO"
    )

    producto_seleccionado = st.sidebar.multiselect(

        "📦 PRODUCTO",

        productos

    )


# ============================================================
# APLICAR FILTROS A VENTAS
# ============================================================

df_filtrado = df_ventas.copy()


# ============================================================
# FILTRO FECHA
# ============================================================

if (
    rango_fechas is not None
    and
    len(rango_fechas) == 2
    and
    "FECHA" in df_filtrado.columns
):

    fecha_inicio = rango_fechas[0]
    fecha_fin = rango_fechas[1]

    df_filtrado = df_filtrado[

        (
            df_filtrado["FECHA"].dt.date
            >= fecha_inicio
        )

        &

        (
            df_filtrado["FECHA"].dt.date
            <= fecha_fin
        )

    ].copy()


# ============================================================
# FILTRO VENDEDOR
# ============================================================

if (
    vendedor_seleccionado
    and
    "VENDEDOR ETIQUETA" in df_filtrado.columns
):

    df_filtrado = df_filtrado[
        df_filtrado["VENDEDOR ETIQUETA"].isin(
            vendedor_seleccionado
        )
    ].copy()


# ============================================================
# FILTRO ASESOR
# ============================================================

if (
    asesor_seleccionado
    and
    "NOMBRE ASESOR" in df_filtrado.columns
):

    df_filtrado = df_filtrado[
        df_filtrado["NOMBRE ASESOR"].isin(
            asesor_seleccionado
        )
    ].copy()


# ============================================================
# FILTRO EMPRESA
# ============================================================

if (
    empresa_seleccionada
    and
    "NOMBRE EMPRESA" in df_filtrado.columns
):

    df_filtrado = df_filtrado[
        df_filtrado["NOMBRE EMPRESA"].isin(
            empresa_seleccionada
        )
    ].copy()


# ============================================================
# FILTRO TIPO DE PAGO
# ============================================================

if (
    pago_seleccionado
    and
    "TIPO DE PAGO" in df_filtrado.columns
):

    df_filtrado = df_filtrado[
        df_filtrado["TIPO DE PAGO"].isin(
            pago_seleccionado
        )
    ].copy()


# ============================================================
# FILTRO STATUS
# ============================================================

if (
    status_seleccionado
    and
    "STATUS" in df_filtrado.columns
):

    df_filtrado = df_filtrado[
        df_filtrado["STATUS"].isin(
            status_seleccionado
        )
    ].copy()


# ============================================================
# FILTRO DESTINO
# ============================================================

if (
    destino_seleccionado
    and
    "DESTINO" in df_filtrado.columns
):

    df_filtrado = df_filtrado[
        df_filtrado["DESTINO"].isin(
            destino_seleccionado
        )
    ].copy()


# ============================================================
# RELACIONAR VENTA CON VENTAS
# ============================================================

if (
    not df_venta.empty
    and
    "NO VENTA" in df_venta.columns
    and
    "NO VENTA" in df_filtrado.columns
):

    numeros_venta_filtrados = set(

        df_filtrado["NO VENTA"]
        .fillna("")
        .astype(str)
        .str.strip()

    )

    numeros_venta_filtrados.discard("")

    df_detalle_filtrado = df_venta[

        df_venta["NO VENTA"].isin(
            numeros_venta_filtrados
        )

    ].copy()

else:

    df_detalle_filtrado = df_venta.copy()


# ============================================================
# FILTRO PRODUCTO
# ============================================================

if (
    producto_seleccionado
    and
    not df_detalle_filtrado.empty
    and
    "PRODUCTO" in df_detalle_filtrado.columns
):

    df_detalle_filtrado = (

        df_detalle_filtrado[

            df_detalle_filtrado["PRODUCTO"].isin(
                producto_seleccionado
            )

        ].copy()

    )


# ============================================================
# PRODUCTO FILTRA VENTAS PADRE
# ============================================================

if (
    producto_seleccionado
    and
    not df_detalle_filtrado.empty
    and
    "NO VENTA" in df_detalle_filtrado.columns
    and
    "NO VENTA" in df_filtrado.columns
):

    numeros_venta_producto = set(

        df_detalle_filtrado["NO VENTA"]
        .fillna("")
        .astype(str)
        .str.strip()

    )

    numeros_venta_producto.discard("")

    df_filtrado = df_filtrado[

        df_filtrado["NO VENTA"].isin(
            numeros_venta_producto
        )

    ].copy()


# ============================================================
# PROTEGER CONTRA DUPLICADOS
# ============================================================

if "NO VENTA" in df_filtrado.columns:

    df_metricas = df_filtrado.copy()

    df_metricas_con_numero = (

        df_metricas[

            df_metricas["NO VENTA"]
            .astype(str)
            .str.strip()
            != ""

        ]

        .drop_duplicates(

            subset=["NO VENTA"],

            keep="last"

        )

        .copy()

    )

    df_metricas_sin_numero = (

        df_metricas[

            df_metricas["NO VENTA"]
            .astype(str)
            .str.strip()
            == ""

        ]

        .copy()

    )

    df_metricas = pd.concat(

        [
            df_metricas_con_numero,
            df_metricas_sin_numero
        ],

        ignore_index=True

    )

else:

    df_metricas = df_filtrado.copy()


# ============================================================
# TOTAL DE VENTAS
# ============================================================

if "TOTAL DE VENTA" in df_metricas.columns:

    total_ventas = (
        df_metricas["TOTAL DE VENTA"]
        .sum()
    )

else:

    total_ventas = 0


# ============================================================
# NÚMERO DE VENTAS
# ============================================================

if "NO VENTA" in df_metricas.columns:

    ventas_unicas = (

        df_metricas["NO VENTA"]
        .fillna("")
        .astype(str)
        .str.strip()

    )

    ventas_unicas = ventas_unicas[
        ventas_unicas != ""
    ]

    numero_ventas = (
        ventas_unicas.nunique()
    )

else:

    numero_ventas = len(
        df_metricas
    )


# ============================================================
# TOTAL PAGADO
# ============================================================

if "PAGO" in df_metricas.columns:

    total_pagado = (
        df_metricas["PAGO"]
        .sum()
    )

else:

    total_pagado = 0


# ============================================================
# SALDO
# ============================================================

if "SALDO" in df_metricas.columns:

    total_saldo = (
        df_metricas["SALDO"]
        .sum()
    )

else:

    total_saldo = (
        total_ventas
        -
        total_pagado
    )


# ============================================================
# PROMEDIO
# ============================================================

if numero_ventas > 0:

    promedio_venta = (
        total_ventas
        /
        numero_ventas
    )

else:

    promedio_venta = 0


# ============================================================
# TOTAL PIEZAS
# ============================================================

if "NO PIEZAS" in df_metricas.columns:

    total_piezas = (
        df_metricas["NO PIEZAS"]
        .sum()
    )

else:

    total_piezas = 0


# ============================================================
# MÉTRICAS
# ============================================================

st.markdown("---")

m1, m2, m3, m4, m5 = st.columns(5)


m1.metric(
    "💰 TOTAL VENTAS",
    f"Q {total_ventas:,.2f}"
)


m2.metric(
    "🧾 CANT VENTAS",
    f"{numero_ventas:,}"
)

# ============================================================
# PROMEDIO
# ============================================================

st.caption(
    f"Promedio por venta: Q {promedio_venta:,.2f}"
)


# ============================================================
# TOTAL DE VENTAS ACTIVAS POR VENDEDOR (TARJETAS DE COLOR)
# ============================================================

st.markdown("---")

st.subheader(
    "🎨 TOTAL DE VENTAS ACTIVAS POR VENDEDOR"
)

if (
    "VENDEDOR ETIQUETA" in df_metricas.columns
    and
    "TOTAL DE VENTA" in df_metricas.columns
):

    resumen_total = (
        df_metricas
        .groupby("VENDEDOR ETIQUETA")["TOTAL DE VENTA"]
        .sum()
    )

    if "NO VENTA" in df_metricas.columns:

        resumen_cantidad = (
            df_metricas[
                df_metricas["NO VENTA"]
                .astype(str)
                .str.strip()
                != ""
            ]
            .groupby("VENDEDOR ETIQUETA")["NO VENTA"]
            .nunique()
        )

    else:

        resumen_cantidad = (
            df_metricas
            .groupby("VENDEDOR ETIQUETA")
            .size()
        )

    etiquetas_resumen = (
        ETIQUETAS_ORDEN
        +
        [
            e
            for e in resumen_total.index
            if e not in ETIQUETAS_ORDEN
        ]
    )

    for inicio in range(0, len(etiquetas_resumen), 4):

        grupo = etiquetas_resumen[inicio:inicio + 4]

        columnas_tarjetas = st.columns(4)

        for columna_st, etiqueta in zip(
            columnas_tarjetas,
            grupo
        ):

            color = COLORES_VENDEDOR.get(
                etiqueta,
                COLOR_SIN_VENDEDOR
            )

            texto_color = color_texto_contraste(color)

            monto = float(
                resumen_total.get(etiqueta, 0)
            )

            cantidad = int(
                resumen_cantidad.get(etiqueta, 0)
            )

            columna_st.markdown(

                f"<div style='background:{color};"
                f"color:{texto_color};"
                f"padding:12px;border-radius:10px;"
                f"margin-bottom:10px;'>"
                f"<div style='font-size:12px;"
                f"font-weight:bold;'>{etiqueta}</div>"
                f"<div style='font-size:20px;"
                f"font-weight:bold;'>Q {monto:,.2f}</div>"
                f"<div style='font-size:12px;'>"
                f"{cantidad:,} ventas</div>"
                f"</div>",

                unsafe_allow_html=True

            )


# ============================================================
# GRÁFICOS
# ============================================================

st.markdown("---")

grafico1, grafico2 = st.columns(2)


# ============================================================
# VENTAS POR VENDEDOR
# ============================================================

with grafico1:

    if (
        "VENDEDOR ETIQUETA" in df_metricas.columns
        and
        "TOTAL DE VENTA" in df_metricas.columns
    ):

        df_vendedor = (

            df_metricas

            .groupby(
                "VENDEDOR ETIQUETA",
                dropna=False
            )[

                "TOTAL DE VENTA"

            ]

            .sum()

            .reset_index()

            .sort_values(
                "TOTAL DE VENTA",
                ascending=False
            )

        )

        fig = px.bar(

            df_vendedor,

            x="VENDEDOR ETIQUETA",

            y="TOTAL DE VENTA",

            color="VENDEDOR ETIQUETA",

            color_discrete_map=COLORES_VENDEDOR,

            title="👤 VENTAS POR VENDEDOR",

            text_auto=".2f"

        )

        fig.update_layout(

            xaxis_title="VENDEDOR",

            yaxis_title="QUETZALES",

            legend_title_text="VENDEDOR"

        )

        st.plotly_chart(

            fig,

            width="stretch"

        )


# ============================================================
# VENTAS POR PRODUCTO
# ============================================================

with grafico2:

    if (
        not df_detalle_filtrado.empty
        and
        "PRODUCTO" in df_detalle_filtrado.columns
    ):

        if "SUBTOTAL" in df_detalle_filtrado.columns:

            columna_producto = "SUBTOTAL"

        elif "PRECIO DE VENTA" in df_detalle_filtrado.columns:

            columna_producto = "PRECIO DE VENTA"

        else:

            columna_producto = None


        if columna_producto:

            if "VENDEDOR ETIQUETA" in df_detalle_filtrado.columns:

                df_producto = (

                    df_detalle_filtrado

                    .groupby(
                        [
                            "PRODUCTO",
                            "VENDEDOR ETIQUETA"
                        ]
                    )[columna_producto]

                    .sum()

                    .reset_index()

                )

                orden_productos = (

                    df_producto

                    .groupby("PRODUCTO")[columna_producto]

                    .sum()

                    .sort_values(ascending=False)

                    .index

                    .tolist()

                )

                fig = px.bar(

                    df_producto,

                    x="PRODUCTO",

                    y=columna_producto,

                    color="VENDEDOR ETIQUETA",

                    color_discrete_map=COLORES_VENDEDOR,

                    category_orders={
                        "PRODUCTO": orden_productos
                    },

                    title="📦 VENTAS POR CODIGO",

                    text_auto=".2f"

                )

            else:

                df_producto = (

                    df_detalle_filtrado

                    .groupby(
                        "PRODUCTO"
                    )[columna_producto]

                    .sum()

                    .reset_index()

                    .sort_values(
                        columna_producto,
                        ascending=False
                    )

                )

                fig = px.bar(

                    df_producto,

                    x="PRODUCTO",

                    y=columna_producto,

                    title="📦 VENTAS POR CODIGO",

                    text_auto=".2f"

                )

            fig.update_layout(

                xaxis_title="CODIGO",

                yaxis_title="QUETZALES",

                legend_title_text="VENDEDOR"

            )

            st.plotly_chart(

                fig,

                width="stretch"

            )

        else:

            st.info(
                "No existe una columna monetaria válida para el gráfico de productos."
            )


# ============================================================
# SEGUNDA FILA DE GRÁFICOS
# ============================================================

grafico3, grafico4 = st.columns(2)


# ============================================================
# TIPO DE PAGO (BARRAS APILADAS POR VENDEDOR)
# ============================================================

with grafico3:

    if (
        "TIPO DE PAGO" in df_metricas.columns
        and
        "TOTAL DE VENTA" in df_metricas.columns
        and
        "VENDEDOR ETIQUETA" in df_metricas.columns
    ):

        df_pago = (

            df_metricas

            .groupby(
                [
                    "TIPO DE PAGO",
                    "VENDEDOR ETIQUETA"
                ],
                dropna=False
            )[

                "TOTAL DE VENTA"

            ]

            .sum()

            .reset_index()

        )

        fig = px.bar(

            df_pago,

            x="TIPO DE PAGO",

            y="TOTAL DE VENTA",

            color="VENDEDOR ETIQUETA",

            color_discrete_map=COLORES_VENDEDOR,

            title="💳 TIPO DE VENTAS",

            text_auto=".2f"

        )

        fig.update_layout(

            xaxis_title="TIPO DE PAGO",

            yaxis_title="QUETZALES",

            legend_title_text="VENDEDOR"

        )

        st.plotly_chart(

            fig,

            width="stretch"

        )


# ============================================================
# EMPRESA
# ============================================================

with grafico4:

    if (
        "NOMBRE EMPRESA" in df_metricas.columns
        and
        "TOTAL DE VENTA" in df_metricas.columns
        and
        "VENDEDOR ETIQUETA" in df_metricas.columns
    ):

        df_empresa = (

            df_metricas

            .groupby(
                [
                    "NOMBRE EMPRESA",
                    "VENDEDOR ETIQUETA"
                ],
                dropna=False
            )[

                "TOTAL DE VENTA"

            ]

            .sum()

            .reset_index()

        )

        orden_empresas = (

            df_empresa

            .groupby("NOMBRE EMPRESA")["TOTAL DE VENTA"]

            .sum()

            .sort_values(ascending=False)

            .index

            .tolist()

        )

        fig = px.bar(

            df_empresa,

            x="NOMBRE EMPRESA",

            y="TOTAL DE VENTA",

            color="VENDEDOR ETIQUETA",

            color_discrete_map=COLORES_VENDEDOR,

            category_orders={
                "NOMBRE EMPRESA": orden_empresas
            },

            title="🏢 VENTAS POR CLIENTE",

            text_auto=".2f"

        )

        fig.update_layout(

            xaxis_title="CLIENTE",

            yaxis_title="QUETZALES",

            legend_title_text="VENDEDOR"

        )

        st.plotly_chart(

            fig,

            width="stretch"

        )


# ============================================================
# EVOLUCIÓN DE VENTAS
# ============================================================

st.markdown("---")

st.subheader(
    "📈 EVOLUCION DE VENTAS"
)


if (
    "FECHA" in df_metricas.columns
    and
    "TOTAL DE VENTA" in df_metricas.columns
    and
    "VENDEDOR ETIQUETA" in df_metricas.columns
):

    df_tiempo = (

        df_metricas

        .dropna(
            subset=["FECHA"]
        )

        .groupby(
            [
                "FECHA",
                "VENDEDOR ETIQUETA"
            ]
        )[

            "TOTAL DE VENTA"

        ]

        .sum()

        .reset_index()

        .sort_values(
            "FECHA"
        )

    )

    if not df_tiempo.empty:

        fig = px.line(

            df_tiempo,

            x="FECHA",

            y="TOTAL DE VENTA",

            color="VENDEDOR ETIQUETA",

            color_discrete_map=COLORES_VENDEDOR,

            markers=True,

            title="📅 EVOLUCION DE TOTAL DE VENTAS"

        )

        fig.update_layout(

            xaxis_title="FECHA",

            yaxis_title="QUETZALES",

            hovermode="x unified",

            legend_title_text="VENDEDOR"

        )

        fig.update_xaxes(
            tickformat="%-d/%-m/%Y",
            hoverformat="%-d/%-m/%Y"
        )

        st.plotly_chart(

            fig,

            width="stretch"

        )


# ============================================================
# TABLA PRINCIPAL
# ============================================================

st.markdown("---")

st.subheader(
    "📋 PERIODO DE VENTAS ACTIVAS"
)


columnas_tabla = [

    "NO VENTA",
    "VENDEDOR",
    "FECHA",
    "CLIENTE",
    "NOMBRE CLIENTE",
    "NOMBRE EMPRESA",
    "TOTAL DE VENTA",
    "PAGO",
    "SALDO",
    "TIPO DE PAGO",
    "STATUS",
    "FACTURADO",
    "DTE",
    "DESTINO",
    "RUTA"

]


columnas_tabla_disponibles = [

    c

    for c in columnas_tabla

    if c in df_metricas.columns

]


if columnas_tabla_disponibles:

    df_mostrar = df_metricas[
        columnas_tabla_disponibles
    ].copy()

else:

    df_mostrar = df_metricas.copy()


# ============================================================
# PROTECCIÓN FINAL PYARROW
# ============================================================

for columna in df_mostrar.columns:

    if df_mostrar[columna].dtype == "object":

        df_mostrar[columna] = (
            df_mostrar[columna]
            .fillna("")
            .astype(str)
        )


if "VENDEDOR ETIQUETA" in df_metricas.columns:

    tabla_para_mostrar = estilizar_por_vendedor(
        df_mostrar,
        df_metricas["VENDEDOR ETIQUETA"]
    )

else:

    tabla_para_mostrar = df_mostrar


st.dataframe(

    tabla_para_mostrar,

    width="stretch",

    hide_index=True,

    column_config={
        "FECHA": st.column_config.DateColumn(
            "FECHA",
            format="D/M/YYYY"
        )
    }

)


# ============================================================
# DETALLE DE PRODUCTOS
# ============================================================

st.markdown("---")

st.subheader(
    "📦 DETALLE DE VENTAS"
)


if not df_detalle_filtrado.empty:

    columnas_detalle = [

        "ID",
        "NO VENTA",
        "PRODUCTO",
        "CANTIDAD",
        "PRECIO",
        "PRECIO DE VENTA",
        "SUBTOTAL",
        "VENDEDOR",
        "NOMBRE VENDEDOR",
        "NOMBRE CLIENTE",
        "TIPO DE PAGO",
        "FECHA",
        "NOMBRE EMPRESA"

    ]


    columnas_detalle_disponibles = [

        c

        for c in columnas_detalle

        if c in df_detalle_filtrado.columns

    ]


    df_detalle_mostrar = df_detalle_filtrado[
        columnas_detalle_disponibles
    ].copy()


    # ========================================================
    # PROTECCIÓN FINAL PYARROW DETALLE
    # ========================================================

    for columna in df_detalle_mostrar.columns:

        if (
            df_detalle_mostrar[columna].dtype == "object"
        ):

            df_detalle_mostrar[columna] = (
                df_detalle_mostrar[columna]
                .fillna("")
                .astype(str)
            )


    if "VENDEDOR ETIQUETA" in df_detalle_filtrado.columns:

        detalle_para_mostrar = estilizar_por_vendedor(
            df_detalle_mostrar,
            df_detalle_filtrado["VENDEDOR ETIQUETA"]
        )

    else:

        detalle_para_mostrar = df_detalle_mostrar


    st.dataframe(

        detalle_para_mostrar,

        width="stretch",

        hide_index=True,

        column_config={
            "FECHA": st.column_config.DateColumn(
                "FECHA",
                format="D/M/YYYY"
            )
        }

    )

else:

    st.info(
        "No hay productos para los filtros seleccionados."
    )


# ============================================================
# INFORMACIÓN FINAL
# ============================================================

st.markdown("---")


i1, i2, i3 = st.columns(3)


with i1:

    st.info(

        f"📊 TOTAL DE VENTAS ACTIVAS: "
        f"{numero_ventas:,}"

    )


with i2:

    st.info(

        f"💰 TOTAL: "
        f"Q {total_ventas:,.2f}"

    )


with i3:

    st.info(

        f"📅 INFORMACION DE REGISTROS: "
        f"{len(df_metricas):,}"

    )
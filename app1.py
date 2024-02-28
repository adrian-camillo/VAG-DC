import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from pandasql import sqldf

# Configura el zoom inicial
st.set_page_config(page_title="VAG DC", page_icon="http://www.doncredito.com.ar/wp-content/uploads/2022/11/LOGO-DON-CREDITO-V_Mesa-de-trabajo-1-copia-3-300x300.png",initial_sidebar_state="collapsed", layout="wide")
st.markdown(
    """
    <style>
    .css-1aumxhk {
        zoom: 0.8; /* Cambia el valor según tu preferencia */
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Define el alcance y autoriza el cliente de Google Sheets
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("doncredito-cffb060e61ef.json", scope)
client = gspread.authorize(creds)
sheet = client.open("Gestión de cobranzas").sheet1
values_list = sheet.get_all_values()
with st.sidebar:
    password = st.text_input(label="Ingrese su contraseña aqui")
if password == "Cordoba2021!":
    password = st.empty()
    # Convierte a DataFrame
    data = pd.DataFrame(values_list[1:], columns=values_list[0])
    # Verifica y convierte las fechas
    date_format = '%d/%m/%Y'
    try:
        data['fecha'] = pd.to_datetime(data['fecha'], format=date_format)
    except ValueError as e:
        st.error(f"Error al convertir las fechas: {e}")
    # Verifica si hay fechas fuera del rango esperado
    min_date = data['fecha'].min()
    max_date = data['fecha'].max()
    expected_min_date = pd.Timestamp('1900-01-01')
    expected_max_date = pd.Timestamp.now().ceil('D')  # Se redondea al siguiente día
    if min_date < expected_min_date or max_date > expected_max_date:
        st.warning(f"Advertencia: Fechas fuera del rango esperado ({expected_min_date.strftime(date_format)} - {expected_max_date.strftime(date_format)}): Min: {min_date}, Max: {max_date}")

    # Asegúrate de que la columna 'cuotas' está en formato numérico
    data['cuotas'] = pd.to_numeric(data['cuotas'], errors='coerce')  # Convierte a numérico, 'coerce' convierte los errores a NaN

    # ordenando los menues desplegables
    # Usando st.columns para posicionar en dos columnas
    col01, col12 = st.columns([3, 3])
    with col01:
        st.title("Seleccione el tipo de gráfico")
        tipo_grafico = st.selectbox("Puede seleccionar el tipo de grafico (Lineal o de barra)", ["Barra", "Línea"])
    with col12:
        # Utiliza widgets de Streamlit para seleccionar un rango de fechas
        st.title("Seleccione un rango de fechas")
        fecha_desde, fecha_hasta = st.date_input("Fecha desde y hasta", value=(data['fecha'].min(), data['fecha'].max()))
    fecha_desde, fecha_hasta = pd.Timestamp(fecha_desde), pd.Timestamp(fecha_hasta)

    # Filtra los datos según el rango de fechas seleccionado
    data_filtrado = data[(data['fecha'] >= fecha_desde) & (data['fecha'] <= fecha_hasta)]
    # Agrupa los datos por mes y realiza cálculos de cuotas y créditos únicos
    data_filtrado.loc[:, 'Mes'] = data_filtrado['fecha'].dt.strftime('%Y-%m') # Convertir Period a cadena
    sql_query = """
    SELECT 
        Mes, 
        SUM(`Monto otorgado por credito`) as `Monto a cobrar`,
        COUNT(DISTINCT `Nro Prestamo`) as `Cantidad de Créditos otorgados`,
        AVG(`Importe Cuota`) as `Monto promedio por cuota`,
        SUM(`Monto otorgado por credito`) as `Monto otorgado en el mes`,
        SUM(cuotas) as `Cantidad de Cuotas`,
        SUM(`Importe capital por credito`) as `Monto capital prestado por mes`
    FROM data_filtrado 
    WHERE 
        `Linea unica de credito` = "SI"
        AND Mes IS NOT NULL 
        AND Producto IS NOT NULL 
        AND Producto NOT LIKE '%Reestructuración%' 
        AND Producto != 'ENIAC' 
        AND Producto != 'PLAN DE PAGO'
        AND `Importe Capital` > 0
    GROUP BY Mes
    """
    sql_query2 = """
    SELECT 
        Mes, 
        SUM(`Monto vencido`) as 'Monto vencido'
    FROM data_filtrado 
    WHERE 
        Mes IS NOT NULL 
        AND Producto IS NOT NULL 
        AND Producto NOT LIKE '%Reestructuración%' 
        AND Producto != 'ENIAC' 
        AND Producto != 'PLAN DE PAGO'
        AND `Importe Capital` > 0
    GROUP BY Mes
    """
    df_aggregated = sqldf(sql_query)

    comodin=sqldf(sql_query2)
    df_aggregated["Monto vencido"]=comodin["Monto vencido"]

    sql_query_cuotas_por_padrones="""
    SELECT
        Mes,
        COUNT(DISTINCT `Nro Prestamo`) as `Cantidad de Créditos otorgados`,
        SUM(CASE WHEN `Estado de la cuota` = 'Cancelado' THEN 1 ELSE 0 End ) AS 'Cantidad de cuotas canceladas',
        SUM(CASE WHEN `Estado de la cuota` = 'Al día' AND `Linea unica de credito` = "SI" THEN 1 ELSE 0 End ) AS 'Cantidad de cuotas Al día',
        SUM(CASE WHEN `Estado de la cuota` = 'Atrasado' THEN 1 ELSE 0 End ) AS 'Cantidad de cuotas Atrasadas',
        SUM(CASE WHEN `Estado de la cuota` = 'Vence hoy' THEN 1 ELSE 0 End ) AS 'Cantidad de cuotas Vence hoy',
        COUNT(CASE WHEN `Fecha Pago` IS NOT NULL AND `vencida?` != 'Sin Fecha de pago' AND `Fecha Pago` != '' THEN 1 END) as 'Cantidad de cuotas cobradas'
    FROM data_filtrado
    WHERE
        `Fecha Pago` IS NOT NULL 
        AND Mes IS NOT NULL 
        AND Producto IS NOT NULL 
        AND Producto NOT LIKE '%Reestructuración%' 
        AND Producto != 'ENIAC' 
    GROUP BY Mes;
    """
    sql_query_montos_por_padrones="""
    SELECT 
        Mes,
        COUNT(DISTINCT `Nro Prestamo`) as `Cantidad de Créditos otorgados`, 
        SUM(CASE WHEN `Estado de la cuota` = 'Cancelado' THEN `Importe Cuota` ELSE 0 End ) AS `Cantidad de cuotas canceladas`, 
        SUM(CASE WHEN `Estado de la cuota` = 'Atrasado' THEN `Importe Cuota` ELSE 0 End ) AS `Cantidad de cuotas Atrasadas`, 
        SUM(CASE WHEN `Estado de la cuota` = 'Vence hoy' THEN `Importe Cuota` ELSE 0 End ) AS `Cantidad de cuotas Vence hoy`, 
        SUM(`Importe Cuota`) AS `Monto total`, 
        COUNT(CASE WHEN `Fecha Pago` IS NOT NULL AND `vencida?` != 'Sin Fecha de pago' AND `Fecha Pago` != '' THEN `Importe Cuota` END) as `Cantidad de cuotas cobradas`, 
        SUM(CASE WHEN `Fecha Pago` IS NOT NULL AND `vencida?` != 'Sin Fecha de pago' AND `Fecha Pago` != '' AND Mes IS NOT NULL 
        AND Producto IS NOT NULL 
        AND Producto NOT LIKE '%Reestructuración%' 
        AND Producto != 'ENIAC' THEN `Importe Cuota` ELSE 0 END) as `cantidad cobrada en el mes` 
    FROM data_filtrado 
    WHERE 
        `Fecha Pago` IS NOT NULL 
        AND Mes IS NOT NULL 
        AND Producto IS NOT NULL 
        AND Producto NOT LIKE '%Reestructuración%' 
        AND Producto != 'ENIAC' 
    GROUP BY Mes;
    """
    sql_query_montos_por_padrones_test="""
        SELECT 
        Mes AS 'Padron',
        'Nro Prestamo',
        fecha,
        'Fecha Vencimiento',
        vencida?,
        'mes vencimiento',
        'Mes actual',
        'mes pago',
        'Fecha Pago',
        'Total Pago',
        'Linea unica de credito',
        Pagado,
        sum(coutas),
        count()
        'Estado de la cuota'
    FROM data_filtrado 
    WHERE 
        AND `Fecha Pago` IS NOT NULL 
        AND Mes IS NOT NULL 
        AND Producto IS NOT NULL 
        AND Producto NOT LIKE '%Reestructuración%' 
        AND Producto != 'ENIAC' 
    """
    test = sqldf(sql_query_cuotas_por_padrones)
    with col01:
        if tipo_grafico == "Línea":
            fig = px.area(test, x='Mes', y=['Cantidad de cuotas canceladas', 'Cantidad de cuotas Al día', 'Cantidad de cuotas Atrasadas', 'Cantidad de cuotas Vence hoy', 'Cantidad de cuotas cobradas'],
                        title='Cantidad de Cuotas por Estado y Monto Cobrado en el Mes',
                        labels={'value': 'Cantidad', 'variable': 'Estado de la Cuota'},
                        color_discrete_sequence=px.colors.qualitative.Pastel)
        else:
            meses = test['Mes']
            cantidad_creditos = test['Cantidad de Créditos otorgados']
            cuotas_canceladas = test['Cantidad de cuotas canceladas']
            cuotas_al_dia = test['Cantidad de cuotas Al día']
            cuotas_atrasadas = test['Cantidad de cuotas Atrasadas']
            cuotas_vence_hoy = test['Cantidad de cuotas Vence hoy']
            cuotas_cobradas = test['Cantidad de cuotas cobradas']

            # Creamos el gráfico de barras apiladas
            fig = go.Figure(data=[
                go.Bar(name='Créditos otorgados', x=meses, y=cantidad_creditos),
                go.Bar(name='Cuotas Canceladas', x=meses, y=cuotas_canceladas),
                go.Bar(name='Cuotas Atrasadas', x=meses, y=cuotas_atrasadas),
                go.Bar(name='Cuotas Vence hoy', x=meses, y=cuotas_vence_hoy),
                go.Bar(name='Cuotas Cobradas', x=meses, y=cuotas_cobradas),
                go.Bar(name='Cuotas Al día', x=meses, y=cuotas_al_dia)
            ])
            # Actualizamos el diseño del gráfico
            fig.update_layout(width=730, height=400, barmode='stack', title='Análisis de Cuotas y Cobros por Mes', xaxis_title='Mes', yaxis_title='Cantidad')
        st.plotly_chart(fig)
    test1= sqldf(sql_query_montos_por_padrones)
    with col12:
        if tipo_grafico == "Línea":
            fig = px.area(test1, x='Mes', y=['Cantidad de cuotas canceladas', 'Cantidad de cuotas Atrasadas', 'Cantidad de cuotas Vence hoy', 'Cantidad de cuotas cobradas'],
                        title='Cantidad de Cuotas por Estado y Monto Cobrado en el Mes',
                        labels={'value': 'Cantidad', 'variable': 'Estado de la Cuota'},
                        color_discrete_sequence=px.colors.qualitative.Pastel)
        else:
            meses = test1['Mes']
            cantidad_creditos = test1['Cantidad de Créditos otorgados']
            cuotas_canceladas = test1['Cantidad de cuotas canceladas']
            cuotas_atrasadas = test1['Cantidad de cuotas Atrasadas']
            cuotas_vence_hoy = test1['Cantidad de cuotas Vence hoy']
            cuotas_cobradas = test1['Cantidad de cuotas cobradas']

            # Creamos el gráfico de barras apiladas
            fig = go.Figure(data=[
                go.Bar(name='Créditos otorgados', x=meses, y=cantidad_creditos),
                go.Bar(name='Cuotas Canceladas', x=meses, y=cuotas_canceladas),
                go.Bar(name='Cuotas Atrasadas', x=meses, y=cuotas_atrasadas),
                go.Bar(name='Cuotas Vence hoy', x=meses, y=cuotas_vence_hoy),
                go.Bar(name='Cuotas Cobradas', x=meses, y=cuotas_cobradas)
            ])
            # Actualizamos el diseño del gráfico
            fig.update_layout(width=730, height=400, barmode='stack', title='Análisis de montos y Cobros por Mes', xaxis_title='Mes', yaxis_title='Cantidad')
    # Mostrar el gráfico
        st.plotly_chart(fig)


    # Función para formatear como moneda argentina solo para columnas que no contienen "cantidad" en su nombre
    def format_as_currency(value, column_name):
        """
        Formatea un valor numérico como moneda argentina si el nombre de la columna no contiene "cantidad".
        """
        if "cantidad" in column_name.lower():
            return value
        # Asume que los valores negativos son errores y los convierte en positivos
        value = abs(value)
        # Formatea el número con separadores de miles y dos decimales
        return "${:,.2f}".format(value).replace(",", "X").replace(".", ",").replace("X", ".")

    # Agregar columna Ticket promedio
    df_aggregated["Credito promedio"] = df_aggregated["Monto otorgado en el mes"] / df_aggregated["Cantidad de Créditos otorgados"] 

    # Aplica el formateo a las columnas numéricas del DataFrame
    columns_to_format = ['Cantidad de Créditos otorgados', 'Cantidad de Cuotas', 'Monto otorgado en el mes', 'Credito promedio','Monto capital prestado por mes']
    for column in columns_to_format:
        df_aggregated[column] = df_aggregated[column].apply(lambda x: format_as_currency(x, column))

    col1, col2, col3, col4 = st.columns(4)

    # Columna 1: Gráfico de créditos únicos con elección de usuario
    with col1:
        if tipo_grafico == "Barra":
            fig_creditos = px.bar(df_aggregated, x='Mes', y='Cantidad de Créditos otorgados',
                                title='Cantidad de Créditos otorgados por Mes',
                                color='Mes',
                                labels={'Cantidad de Créditos otorgados': 'Cantidad', 'Mes': 'Mes'})
        else:
            fig_creditos = px.line(df_aggregated, x='Mes', y='Cantidad de Créditos otorgados',
                                    title='Cantidad de Créditos otorgados por Mes',
                                    markers=True, labels={'Cantidad de Créditos otorgados': 'Cantidad', 'Mes': 'Mes'})
        fig_creditos.update_layout(width=350, height=400)
        st.plotly_chart(fig_creditos)
        st.dataframe(df_aggregated.get(["Mes","Cantidad de Créditos otorgados"]))

    # Columna 2: Gráfico de cuotas con elección de usuario
    with col2:
        if tipo_grafico == "Barra":
            fig_cuotas = px.bar(df_aggregated, x='Mes', y='Cantidad de Cuotas', title='Cantidad de Cuotas por Mes',
                                color='Mes', labels={'Cantidad de Cuotas': 'Cantidad', 'Mes': 'Mes'})
        else:
            fig_cuotas = px.line(df_aggregated, x='Mes', y='Cantidad de Cuotas', title='Cantidad de Cuotas por Mes',
                                markers=True, labels={'Cantidad de Cuotas': 'Cantidad', 'Mes': 'Mes'})
        fig_cuotas.update_layout(width=350, height=400)
        st.plotly_chart(fig_cuotas)
        st.dataframe(df_aggregated.get(["Mes","Cantidad de Cuotas"]))

    # Utiliza value_counts() para obtener el recuento de cada producto
    sql_query_productos = """
                        SELECT Producto, COUNT(Producto) as Cantidad
                        FROM data_filtrado
                        WHERE Producto IS NOT NULL AND Producto NOT LIKE '%Reestructuración%' AND Producto IS NOT 'ENIAC' AND Producto IS NOT 'PLAN DE PAGO'
                        GROUP BY Producto
                        """
    lista_de_productos_refinada = sqldf(sql_query_productos)

    # Filtrar los productos con nombres de menos de 3 caracteres
    lista_de_productos_refinada = lista_de_productos_refinada[lista_de_productos_refinada['Producto'].apply(lambda x: len(x) >= 1)]

    with col3:
        # Muestra el DataFrame en Streamlit
        if tipo_grafico == "Barra":
            fig_monto_mes = px.bar(df_aggregated, x='Mes', y='Monto otorgado en el mes', 
                            title='Monto Otorgado por Mes',
                            labels={'Monto otorgado en el mes': 'Monto', 'Mes': 'Mes'},
                            color='Mes')
        else:
            fig_monto_mes = px.line(df_aggregated, x='Mes', y='Monto otorgado en el mes', 
                                    title='Monto Otorgado por Mes',
                                    markers=True, labels={'Monto otorgado en el mes': 'Monto', 'Mes': 'Mes'})
        fig_monto_mes.update_layout(width=350, height=400)
        st.plotly_chart(fig_monto_mes)
        st.dataframe(df_aggregated.get(["Mes","Monto otorgado en el mes","Monto capital prestado por mes"]))

    # Calcula el promedio de la columna 'cuotas'
    promedio_cuotas = data_filtrado['cuotas'].mean()

    with col4:
        if tipo_grafico == "Barra":
            fig_promedio_credito = px.bar(df_aggregated, x='Mes', y='Credito promedio', 
                                    title='Ticket promedio por mes',
                                    labels={'Monto promedio de ticket': 'Monto', 'Mes': 'Mes'},
                                    color='Mes')
        else:
            fig_promedio_credito = px.line(df_aggregated, x='Mes', y='Credito promedio', 
                                        title='Ticket promedio por mes',
                                        markers=True, labels={'Monto promedio de ticket': 'Monto', 'Mes': 'Mes'})
        fig_promedio_credito.update_layout(width=350, height=400)
        st.plotly_chart(fig_promedio_credito)
        st.dataframe(df_aggregated.get(["Mes","Credito promedio"]))


    data_filtrado['Fecha Vencimiento'] = pd.to_datetime(data_filtrado['Fecha Vencimiento'])

    # Función para calcular los DataFrames por patrón
    def calcular_dataframes_por_padron(data_filtrada):
        # Asegurarse de que la columna 'fecha' está en formato datetime
        data_filtrada['fecha'] = pd.to_datetime(data_filtrada['fecha'], errors='coerce')
        # Asegurarse de que 'Fecha Vencimiento' está en formato datetime
        data_filtrada['Fecha Vencimiento'] = pd.to_datetime(data_filtrada['Fecha Vencimiento'], errors='coerce')
        # Crear la columna 'Mes Vencimiento' a partir de 'Fecha Vencimiento'
        data_filtrada['Mes Vencimiento'] = data_filtrada['Fecha Vencimiento'].dt.to_period('M').astype(str)
        # Convertir 'Importe Cuota' a float
        data_filtrada['Importe Cuota'] = data_filtrada['Importe Cuota'].apply(lambda x: float(str(x).replace(",", ".").replace("$", "")) if isinstance(x, str) else x)
        # Agrupar los datos por 'Padron' y 'Mes Vencimiento' y calcular las métricas requeridas
        data_filtrada['Monto vencido'] = data_filtrada['Monto vencido'].apply(lambda x: float(str(x).replace(",", ".").replace("$", "")) if isinstance(x, str) else x)
        aggregated_data = data_filtrada.groupby(['Padron', 'Mes Vencimiento']).agg(
            Monto_a_cobrar=('Importe Cuota', 'sum'),
            Monto_vencido=('Monto vencido', 'sum'),
            Cantidad_cobrada=('Importe Cuota', lambda x: x[data_filtrada.loc[x.index, 'Pagado'] == 'SI'].sum()))
            # Calcular el porcentaje de mora
        aggregated_data['Porcentaje_mora'] = (1 - (aggregated_data['Cantidad_cobrada'] / aggregated_data['Monto_vencido'])) * 100
        aggregated_data['Porcentaje_mora'] = aggregated_data['Porcentaje_mora'].apply(lambda x: '{:.2f}%'.format(x))
        # Resetear el índice para convertir 'Padron' y 'Mes Vencimiento' a columnas
        aggregated_data.reset_index(inplace=True)
        # Devolver un diccionario de DataFrames, uno para cada patrón
        return {padron: group for padron, group in aggregated_data.groupby('Padron')}

    # Asegurarse de que la columna 'Padron' se crea correctamente en 'data_filtrado'
    data_filtrado['fecha'] = pd.to_datetime(data_filtrado['fecha'], errors='coerce')
    data_filtrado['Padron'] = data_filtrado['fecha'].dt.to_period('M').astype(str)

    # Streamlit: Selección de patrón por parte del usuario
    st.header('Cobranza por padron')
    patrones_unicos = data_filtrado['Padron'].dropna().unique()
    patron_seleccionado = str(st.selectbox('Seleccione un patrón:', patrones_unicos))



    sql_query_cuotas_por_padrones_test="""
    SELECT *
    FROM data_filtrado
    WHERE
        `Fecha Pago` IS NOT NULL 
        AND Mes IS NOT NULL 
        AND Producto IS NOT NULL 
        AND Producto NOT LIKE '%Reestructuración%' 
        AND Producto != 'ENIAC' 
        AND Producto != '' 
    """
    test=sqldf(sql_query_cuotas_por_padrones_test)
    # Streamlit: Mostrar el DataFrame para el patrón seleccionado
    dataframes_por_padron = calcular_dataframes_por_padron(test)
    # Asegúrate de que ya se ha seleccionado el patrón y se ha generado dataframes_por_padron
    if patron_seleccionado in dataframes_por_padron:
        df_para_graficar = dataframes_por_padron[patron_seleccionado]

        # Crear dos columnas: una para el DataFrame, otra para el gráfico
        col_df, col_grafico = st.columns([6, 6])

        # Mostrar el DataFrame en la columna de la izquierda
        with col_df:
            st.dataframe(df_para_graficar)

        # Crear el gráfico en la columna de la derecha
        with col_grafico:
            if tipo_grafico == "Línea":
                # Usando un gráfico de área o de línea según lo que funcione mejor para tu conjunto de datos
                # Si df_para_graficar es grande, considera especificar columnas específicas en lugar de usar df_para_graficar.columns directamente
                fig = px.line(df_para_graficar, x='Mes Vencimiento', y=[col for col in df_para_graficar.columns if df_para_graficar[col].dtype in ['float64', 'int64']],
                            title='Desempeño por Mes de Vencimiento',
                            labels={'value': 'Cantidad', 'variable': 'Métrica'},
                            markers=True)  # Usa markers=True si prefieres tener marcadores en el gráfico de línea
            else:
                # Gráfico de barra para todas las columnas numéricas
                fig = go.Figure()
                for columna in [col for col in df_para_graficar.columns if df_para_graficar[col].dtype in ['float64', 'int64']]:
                    fig.add_trace(go.Bar(name=columna, x=df_para_graficar['Mes Vencimiento'], y=df_para_graficar[columna]))

                # Actualizar el diseño del gráfico
                fig.update_layout(barmode='group', title='Desempeño por Mes de Vencimiento',
                                xaxis_title='Mes Vencimiento', yaxis_title='Cantidad', width=730, height=400)

            # Mostrar el gráfico
            st.plotly_chart(fig)
    else:
        st.error('No se encontraron datos para el patrón seleccionado.')

    col08, col18, col28 = st.columns([10, 5, 5])
    with col08:
        st.write(" ")
        st.write(" ")
        st.write(" ")
        if st.button('Mostrar todo el dataframe'):
            data=st.dataframe(data_filtrado)
    with col18:
        fig_pie = px.pie(lista_de_productos_refinada,
                        names='Producto',
                        values='Cantidad',
                        title='Distribución por tipo de producto',
                        hole=0.3)
        fig_pie.update_layout(width=350, height=400, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#333')
        st.write(" ")
        st.plotly_chart(fig_pie)
    with col28:
        st.write(" ")
        st.write(" ")
        st.write(" ")
        dataframe_de_productos=st.dataframe(lista_de_productos_refinada)

    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
else:
    st.title("Puede ingresar la contraseña en el menu lateral")

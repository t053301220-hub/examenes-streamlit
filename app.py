import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
from datetime import datetime
import io
import base64
from pdf2image import convert_from_bytes
import time
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.units import inch

# ==================== CONFIGURACIÓN ====================

st.set_page_config(
    page_title="Calificador de Exámenes - N8N Simulator",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS para móvil
st.markdown("""
<style>
    @media (max-width: 768px) {
        .main { padding: 0; }
        .block-container { padding: 1rem; }
    }
    .stButton > button { width: 100%; }
    .metric-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
    .n8n-simulator {
        background: #f0f0f0;
        border-left: 5px solid #ff6f00;
        padding: 15px;
        border-radius: 5px;
        margin: 15px 0;
    }
</style>
""", unsafe_allow_html=True)

# ==================== INICIALIZAR SESIÓN ====================

if 'resultados' not in st.session_state:
    st.session_state.resultados = None
if 'estadisticas' not in st.session_state:
    st.session_state.estadisticas = None
if 'api_key_configurada' not in st.session_state:
    st.session_state.api_key_configurada = False
if 'nombre_curso' not in st.session_state:
    st.session_state.nombre_curso = ""
if 'codigo_curso' not in st.session_state:
    st.session_state.codigo_curso = ""

# ==================== HEADER ====================

st.title("📋 Calificador Automático de Exámenes")
st.markdown("**Integración Streamlit + Google Gemini + N8N Simulator**")
st.markdown("---")

# ==================== CONFIGURACIÓN API EN SIDEBAR ====================

with st.sidebar:
    st.header("⚙️ Configuración API")
    
    api_key = st.text_input(
        "Ingresa tu API Key de Google Gemini",
        type="password",
        help="Obtén gratis en https://ai.google.dev"
    )
    
    if api_key:
        try:
            genai.configure(api_key=api_key)
            st.session_state.api_key_configurada = True
            st.success("✅ API Key configurada correctamente")
        except Exception as e:
            st.error(f"❌ Error de API: {str(e)}")
            st.session_state.api_key_configurada = False
    
    st.markdown("---")
    st.markdown("**📚 Instrucciones:**")
    st.markdown("""
    1. Obtén tu API Key en [Google AI Studio](https://ai.google.dev)
    2. Ingresa aquí (es gratis)
    3. Sigue los pasos en la app
    4. ¡Listo!
    """)

# ==================== FUNCIONES ====================

def extraer_respuestas_con_gemini(pdf_bytes, nombre_archivo):
    """Extrae respuestas del PDF usando Google Gemini Vision"""
    try:
        imagenes = convert_from_bytes(pdf_bytes, dpi=200)
        respuestas_totales = {}
        
        for idx, imagen in enumerate(imagenes):
            img_byte_arr = io.BytesIO()
            imagen.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            img_bytes = img_byte_arr.getvalue()
            
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = """Analiza este examen PDF escaneado. 
Identifica TODAS las respuestas que están marcadas con X, ✓, o círculo.
Para cada pregunta con respuesta marcada, devuelve SOLO en este formato (una por línea):
1:a
2:d
3:e
4:v
5:f

NO incluyas explicaciones, SOLO el formato anterior.
Si no hay marca visible, NO incluyas esa pregunta."""
            
            try:
                response = model.generate_content([
                    prompt,
                    {
                        "mime_type": "image/png",
                        "data": base64.b64encode(img_bytes).decode()
                    }
                ], timeout=30)
                
                texto_respuesta = response.text
                lineas = texto_respuesta.strip().split('\n')
                
                for linea in lineas:
                    if ':' in linea:
                        try:
                            pregunta, respuesta = linea.strip().split(':')
                            pregunta_num = int(pregunta)
                            respuesta_clean = respuesta.strip().lower()
                            if respuesta_clean in ['a', 'b', 'c', 'd', 'e', 'v', 'f']:
                                respuestas_totales[pregunta_num] = respuesta_clean
                        except:
                            continue
            except Exception as e:
                st.warning(f"⚠️ Timeout procesando página {idx+1}")
                continue
        
        return respuestas_totales if respuestas_totales else {}
    
    except Exception as e:
        st.error(f"❌ Error procesando PDF: {str(e)}")
        return {}

def procesar_claves(claves_input):
    """Procesa las claves de respuesta"""
    try:
        claves_dict = {}
        items = claves_input.split(',')
        
        for item in items:
            if ':' in item:
                numero, respuesta = item.strip().split(':')
                claves_dict[int(numero)] = respuesta.lower()
        
        return claves_dict
    except Exception as e:
        st.error(f"Error al procesar claves: {e}")
        return {}

def calificar_pdf(respuestas_estudiante, claves_correctas):
    """Califica un PDF comparando respuestas"""
    if not respuestas_estudiante:
        return {
            'correctas': 0,
            'incorrectas': 0,
            'sin_responder': 0,
            'nota': 0,
            'aprobado': False
        }
    
    correctas = 0
    incorrectas = 0
    sin_responder = 0
    
    for pregunta, respuesta_correcta in claves_correctas.items():
        respuesta_estudiante = respuestas_estudiante.get(pregunta)
        
        if respuesta_estudiante is None:
            sin_responder += 1
        elif respuesta_estudiante.lower() == respuesta_correcta.lower():
            correctas += 1
        else:
            incorrectas += 1
    
    total = len(claves_correctas)
    porcentaje = (correctas / total * 100) if total > 0 else 0
    nota = (porcentaje / 100) * 20
    
    return {
        'correctas': correctas,
        'incorrectas': incorrectas,
        'sin_responder': sin_responder,
        'nota': round(nota, 2),
        'aprobado': nota >= 11
    }

def calcular_estadisticas(resultados):
    """Calcula estadísticas generales"""
    if not resultados:
        return {}
    
    notas = [r['nota'] for r in resultados]
    aprobados = [r for r in resultados if r['aprobado']]
    desaprobados = [r for r in resultados if not r['aprobado']]
    
    promedio = sum(notas) / len(notas) if notas else 0
    promedio_aprobados = sum(r['nota'] for r in aprobados) / len(aprobados) if aprobados else 0
    
    return {
        'total_estudiantes': len(resultados),
        'promedio_general': round(promedio, 2),
        'promedio_aprobados': round(promedio_aprobados, 2),
        'cantidad_aprobados': len(aprobados),
        'cantidad_desaprobados': len(desaprobados),
        'nota_maxima': max(notas) if notas else 0,
        'nota_minima': min(notas) if notas else 0,
        'tasa_aprobacion': round((len(aprobados) / len(resultados) * 100) if resultados else 0, 1),
        'fecha_procesamiento': datetime.now().strftime('%d/%m/%Y %H:%M')
    }

def generar_pdf_reporte(nombre_curso, codigo_curso, resultados, estadisticas):
    """Genera PDF con el reporte completo"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20, bottomMargin=20)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=20,
        alignment=1
    )
    
    # Encabezado
    story.append(Paragraph("📋 REPORTE DE CALIFICACIONES", title_style))
    story.append(Paragraph(f"<b>Curso:</b> {nombre_curso}", styles['Normal']))
    story.append(Paragraph(f"<b>Código:</b> {codigo_curso}", styles['Normal']))
    story.append(Paragraph(f"<b>Fecha:</b> {estadisticas.get('fecha_procesamiento', '')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Tabla de resultados
    tabla_data = [['PDF', 'Correctas', 'Incorrectas', 'Nota (s/20)', 'Estado']]
    
    for resultado in resultados:
        estado = '✓ APROBADO' if resultado['aprobado'] else '✗ DESAPROBADO'
        tabla_data.append([
            resultado['nombre'][:30],
            str(resultado['correctas']),
            str(resultado['incorrectas']),
            f"{resultado['nota']:.2f}",
            estado
        ])
    
    tabla = Table(tabla_data, colWidths=[150, 80, 90, 80, 100])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')])
    ]))
    
    story.append(tabla)
    story.append(Spacer(1, 30))
    
    # Estadísticas
    stats_html = f"""
    <b style='font-size: 14px; color: #1f4788;'>ESTADÍSTICAS GENERALES</b><br/><br/>
    <b>Total de Estudiantes:</b> {estadisticas.get('total_estudiantes', 0)}<br/>
    <b>Promedio General (s/20):</b> {estadisticas.get('promedio_general', 0):.2f}<br/>
    <b>Promedio de Aprobados (s/20):</b> {estadisticas.get('promedio_aprobados', 0):.2f}<br/>
    <b>Aprobados:</b> {estadisticas.get('cantidad_aprobados', 0)}<br/>
    <b>Desaprobados:</b> {estadisticas.get('cantidad_desaprobados', 0)}<br/>
    <b>Tasa de Aprobación:</b> {estadisticas.get('tasa_aprobacion', 0):.1f}%<br/>
    <b>Nota Máxima:</b> {estadisticas.get('nota_maxima', 0):.2f}<br/>
    <b>Nota Mínima:</b> {estadisticas.get('nota_minima', 0):.2f}
    """
    
    story.append(Paragraph(stats_html, styles['Normal']))
    
    # Generar PDF
    doc.build(story)
    return buffer.getvalue()

# ==================== INTERFAZ PRINCIPAL ====================

# PASO 1: INFORMACIÓN DEL CURSO

st.header("📝 Paso 1: Información del Curso")

col1, col2 = st.columns(2)

with col1:
    nombre_curso = st.text_input(
        "Nombre del Curso",
        placeholder="Ej: Matemáticas I",
        key="nombre_curso_input"
    )
    st.session_state.nombre_curso = nombre_curso

with col2:
    codigo_curso = st.text_input(
        "Código del Curso",
        placeholder="Ej: MAT-101",
        key="codigo_curso_input"
    )
    st.session_state.codigo_curso = codigo_curso

st.markdown("---")

# PASO 2: CLAVES DE RESPUESTA

st.header("📌 Paso 2: Ingresa las Claves de Respuesta")

st.info("**Formato:** Separar con comas\n\n"
        "**Ejemplo completo:** `1:a, 2:d, 3:e, 4:v, 5:f`\n\n"
        "Soporta opción múltiple (a,b,c,d,e) y binario (v,f)")

claves_input = st.text_area(
    "Claves de respuesta",
    height=80,
    placeholder="1:a, 2:d, 3:e, 4:v, 5:f",
    key="claves_input"
)

if claves_input:
    try:
        claves_lista = [x.strip() for x in claves_input.split(',')]
        st.success(f"✅ {len(claves_lista)} preguntas detectadas")
        
        col1, col2 = st.columns(2)
        with col1:
            for clave in claves_lista[:len(claves_lista)//2]:
                st.text(f"  {clave}")
        with col2:
            for clave in claves_lista[len(claves_lista)//2:]:
                st.text(f"  {clave}")
    except:
        st.error("❌ Formato inválido")

st.markdown("---")

# PASO 3: CARGAR PDFs

st.header("📂 Paso 3: Carga de PDFs (Máximo 30)")

uploaded_files = st.file_uploader(
    "Sube los PDFs con las respuestas marcadas",
    type="pdf",
    accept_multiple_files=True
)

if uploaded_files:
    st.success(f"✅ {len(uploaded_files)} archivo(s) cargado(s)")
    
    if len(uploaded_files) > 30:
        st.error("❌ Máximo 30 PDFs permitidos")
    else:
        with st.expander(f"📄 Ver archivos ({len(uploaded_files)})"):
            for idx, file in enumerate(uploaded_files, 1):
                st.text(f"{idx}. {file.name} ({file.size/1024:.2f} KB)")

st.markdown("---")

# PASO 4: SIMULAR N8N

st.header("⚙️ Paso 4: Procesar (Simulación N8N)")

if st.button("🔄 ANALIZAR EN N8N", use_container_width=True, type="primary"):
    
    # Validaciones
    if not nombre_curso:
        st.error("❌ Ingresa el nombre del curso")
    elif not codigo_curso:
        st.error("❌ Ingresa el código del curso")
    elif not claves_input:
        st.error("❌ Ingresa las claves de respuesta")
    elif not uploaded_files:
        st.error("❌ Carga al menos un PDF")
    elif not st.session_state.api_key_configurada:
        st.error("❌ Configura tu API Key de Gemini en la barra lateral")
    else:
        claves = procesar_claves(claves_input)
        
        if not claves:
            st.error("❌ Error al procesar claves")
        else:
            # Simulación N8N
            st.markdown("<div class='n8n-simulator'>", unsafe_allow_html=True)
            st.markdown("### 🔗 Conectando a N8N Cloud...")
            st.markdown("</div>", unsafe_allow_html=True)
            
            # Placeholders para efectos visuales
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Simulación de conexión N8N
            pasos_n8n = [
                "📡 Iniciando conexión con N8N...",
                "🔐 Autenticando en N8N Cloud...",
                "📦 Empaquetando PDFs...",
                "🚀 Enviando a servidor N8N...",
                "🔍 Ejecutando workflow en N8N...",
            ]
            
            for i, paso in enumerate(pasos_n8n):
                status_text.text(paso)
                progress_bar.progress((i + 1) / (len(pasos_n8n) + 1))
                time.sleep(1)
            
            status_text.text("📖 Leyendo PDFs...")
            progress_bar.progress(0.6)
            
            # Procesar PDFs realmente
            resultados = []
            
            for idx, uploaded_file in enumerate(uploaded_files):
                try:
                    porcentaje = 0.6 + ((idx + 1) / len(uploaded_files)) * 0.3
                    progress_bar.progress(porcentaje)
                    status_text.text(f"🔍 Analizando {uploaded_file.name} con Gemini OCR...")
                    
                    pdf_bytes = uploaded_file.read()
                    respuestas = extraer_respuestas_con_gemini(pdf_bytes, uploaded_file.name)
                    calificacion = calificar_pdf(respuestas, claves)
                    
                    resultados.append({
                        'nombre': uploaded_file.name,
                        'correctas': calificacion['correctas'],
                        'incorrectas': calificacion['incorrectas'],
                        'sin_responder': calificacion['sin_responder'],
                        'nota': calificacion['nota'],
                        'aprobado': calificacion['aprobado']
                    })
                
                except Exception as e:
                    st.warning(f"⚠️ Error en {uploaded_file.name}")
                    resultados.append({
                        'nombre': uploaded_file.name,
                        'correctas': 0,
                        'incorrectas': 0,
                        'sin_responder': 0,
                        'nota': 0,
                        'aprobado': False
                    })
            
            # Últimos pasos de simulación
            status_text.text("📊 Calculando estadísticas...")
            progress_bar.progress(0.95)
            time.sleep(1)
            
            # Calcular estadísticas
            estadisticas = calcular_estadisticas(resultados)
            
            st.session_state.resultados = resultados
            st.session_state.estadisticas = estadisticas
            
            status_text.text("✅ ¡Procesamiento completado en N8N!")
            progress_bar.progress(1.0)
            time.sleep(1)
            
            st.success("✅ Exámenes procesados exitosamente")
            st.balloons()

st.markdown("---")

# PASO 5: RESULTADOS

if st.session_state.resultados and st.session_state.estadisticas:
    st.header("📊 Paso 5: Resultados")
    
    stats = st.session_state.estadisticas
    
    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 Promedio (s/20)", f"{stats['promedio_general']:.2f}")
    with col2:
        st.metric("✅ Aprobados", stats['cantidad_aprobados'])
    with col3:
        st.metric("❌ Desaprobados", stats['cantidad_desaprobados'])
    with col4:
        st.metric("👥 Total", stats['total_estudiantes'])
    
    st.markdown("---")
    
    # Tabla de resultados
    st.subheader("📋 Detalles por Estudiante")
    
    df_resultados = pd.DataFrame(st.session_state.resultados)
    df_resultados['Estado'] = df_resultados['aprobado'].apply(
        lambda x: "✅ Aprobado" if x else "❌ Desaprobado"
    )
    
    df_display = df_resultados[['nombre', 'correctas', 'incorrectas', 'nota', 'Estado']].copy()
    df_display.columns = ['PDF', 'Correctas', 'Incorrectas', 'Nota (s/20)', 'Estado']
    
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # Estadísticas detalladas
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Estadísticas Generales")
        st.info(f"""
        **Promedio General (s/20)**: {stats['promedio_general']:.2f}
        
        **Promedio Aprobados (s/20)**: {stats['promedio_aprobados']:.2f}
        
        **Nota Máxima**: {stats['nota_maxima']:.2f}
        
        **Nota Mínima**: {stats['nota_minima']:.2f}
        
        **Tasa Aprobación**: {stats['tasa_aprobacion']:.1f}%
        """)
    
    with col2:
        st.subheader("👥 Resumen")
        st.info(f"""
        **Total Procesados**: {stats['total_estudiantes']}
        
        **Aprobados**: {stats['cantidad_aprobados']}
        
        **Desaprobados**: {stats['cantidad_desaprobados']}
        
        **Curso**: {st.session_state.codigo_curso}
        
        **Fecha**: {stats['fecha_procesamiento']}
        """)
    
    st.markdown("---")
    
    # Descargas
    st.subheader("📥 Opciones de Descarga")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        csv_data = df_display.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📊 Descargar CSV",
            data=csv_data,
            file_name=f"calificaciones_{st.session_state.codigo_curso}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        json_data = json.dumps({
            'curso': st.session_state.nombre_curso,
            'codigo': st.session_state.codigo_curso,
            'estadisticas': stats,
            'resultados': st.session_state.resultados,
            'fecha': datetime.now().isoformat()
        }, indent=2, ensure_ascii=False)
        
        st.download_button(
            label="📄 Descargar JSON",
            data=json_data,
            file_name=f"reporte_{st.session_state.codigo_curso}_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
            use_container_width=True
        )
    
    with col3:
        pdf_data = generar_pdf_reporte(
            st.session_state.nombre_curso,
            st.session_state.codigo_curso,
            st.session_state.resultados,
            stats
        )
        
        st.download_button(
            label="📋 Descargar PDF",
            data=pdf_data,
            file_name=f"reporte_{st.session_state.codigo_curso}_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    
    st.markdown("---")
    
    if st.button("🔄 Procesar Nuevamente", use_container_width=True):
        st.session_state.resultados = None
        st.session_state.estadisticas = None
        st.rerun()

# ==================== FOOTER ====================

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray; font-size: 12px;'>
    <p>🎓 Calificador Automático de Exámenes v4.0</p>
    <p>Streamlit + Google Gemini OCR + Simulación N8N</p>
    <p>© 2025 - Todos los derechos reservados</p>
</div>
""", unsafe_allow_html=True)

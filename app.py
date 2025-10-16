import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
from datetime import datetime
import io
from PIL import Image
import base64

# ==================== CONFIGURACIÓN ====================

st.set_page_config(
    page_title="Calificador de Exámenes",
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
</style>
""", unsafe_allow_html=True)

# ==================== INICIALIZAR SESIÓN ====================

if 'resultados' not in st.session_state:
    st.session_state.resultados = None
if 'estadisticas' not in st.session_state:
    st.session_state.estadisticas = None
if 'api_key_configurada' not in st.session_state:
    st.session_state.api_key_configurada = False

# ==================== HEADER ====================

st.title("📋 Calificador Automático de Exámenes")
st.markdown("Solución 100% Streamlit con Google Gemini OCR")
st.markdown("---")

# ==================== CONFIGURAR API KEY ====================

with st.sidebar:
    st.header("⚙️ Configuración")
    
    api_key = st.text_input(
        "Ingresa tu API Key de Google Gemini",
        type="password",
        help="Obtén tu clave en https://ai.google.dev"
    )
    
    if api_key:
        try:
            genai.configure(api_key=api_key)
            st.session_state.api_key_configurada = True
            st.success("✅ API Key configurada")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.session_state.api_key_configurada = False

# ==================== FUNCIONES ====================

def extraer_respuestas_con_gemini(pdf_bytes, nombre_archivo):
    """Extrae respuestas del PDF usando Gemini Vision"""
    try:
        # Convertir PDF a imagen (usando pdf2image)
        from pdf2image import convert_from_bytes
        
        imagenes = convert_from_bytes(pdf_bytes, dpi=200)
        
        respuestas_totales = {}
        
        # Procesar cada página del PDF
        for idx, imagen in enumerate(imagenes):
            # Convertir imagen a bytes para Gemini
            img_byte_arr = io.BytesIO()
            imagen.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            img_bytes = img_byte_arr.getvalue()
            
            # Llamar a Gemini Vision
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = """Analiza este examen escaneado y extrae TODAS las respuestas marcadas con X, ✓ o similar.
            
Para cada pregunta identificada, devuelve el número de pregunta y la alternativa elegida.

FORMATO DE RESPUESTA REQUERIDO (sin explicaciones adicionales):
1:a
2:d
3:e
4:v
5:f

Si no hay marca, no incluyas esa pregunta.
Solo devuelve las respuestas en ese formato exacto, una por línea."""
            
            response = model.generate_content([
                prompt,
                {
                    "mime_type": "image/png",
                    "data": base64.b64encode(img_bytes).decode()
                }
            ])
            
            # Parsear respuestas
            texto_respuesta = response.text
            lineas = texto_respuesta.strip().split('\n')
            
            for linea in lineas:
                if ':' in linea:
                    try:
                        pregunta, respuesta = linea.strip().split(':')
                        respuestas_totales[int(pregunta)] = respuesta.lower()
                    except:
                        continue
        
        return respuestas_totales if respuestas_totales else {}
    
    except ImportError:
        st.error("❌ Instala: pip install pdf2image")
        return {}
    except Exception as e:
        st.error(f"❌ Error al procesar PDF: {str(e)}")
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

# ==================== INTERFAZ ====================

# PASO 1: INFORMACIÓN DEL CURSO

st.header("Paso 1️⃣ - Información del Curso")

col1, col2 = st.columns(2)

with col1:
    nombre_curso = st.text_input(
        "Nombre del Curso",
        placeholder="Ej: Matemáticas I"
    )

with col2:
    codigo_curso = st.text_input(
        "Código del Curso",
        placeholder="Ej: MAT-101"
    )

st.markdown("---")

# PASO 2: CLAVES DE RESPUESTA

st.header("Paso 2️⃣ - Claves de Respuesta")

st.info("📝 **Formato:** Separar con comas\n\n"
        "**Ejemplo:** `1:a, 2:d, 3:e, 4:v, 5:f`\n\n"
        "Soporta opción múltiple (a,b,c,d,e) y binario (v,f)")

claves_input = st.text_area(
    "Ingresa las claves de respuesta",
    height=80,
    placeholder="1:a, 2:d, 3:e, 4:v, 5:f"
)

if claves_input:
    try:
        claves_lista = [x.strip() for x in claves_input.split(',')]
        st.success(f"✓ {len(claves_lista)} preguntas detectadas")
    except Exception as e:
        st.error(f"❌ Error: {e}")

st.markdown("---")

# PASO 3: CARGAR PDFs

st.header("Paso 3️⃣ - Cargar PDFs (Máximo 30)")

uploaded_files = st.file_uploader(
    "Sube los PDFs de respuestas",
    type="pdf",
    accept_multiple_files=True
)

if uploaded_files:
    st.success(f"✓ {len(uploaded_files)} archivo(s) cargado(s)")
    
    if len(uploaded_files) > 30:
        st.error("❌ Máximo 30 PDFs permitidos")
    else:
        with st.expander(f"📄 Ver archivos cargados ({len(uploaded_files)})"):
            for idx, file in enumerate(uploaded_files, 1):
                st.text(f"{idx}. {file.name} ({file.size/1024:.2f} KB)")

st.markdown("---")

# PASO 4: PROCESAR

st.header("Paso 4️⃣ - Procesar Exámenes")

if st.button("🚀 Procesar Exámenes", use_container_width=True, type="primary"):
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
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            resultados = []
            
            for idx, uploaded_file in enumerate(uploaded_files):
                try:
                    # Actualizar progreso
                    porcentaje = (idx / len(uploaded_files))
                    progress_bar.progress(porcentaje)
                    status_text.text(f"📖 Procesando {uploaded_file.name}...")
                    
                    # Leer PDF
                    pdf_bytes = uploaded_file.read()
                    
                    # Extraer respuestas con Gemini
                    status_text.text(f"🔍 Analizando {uploaded_file.name} con Gemini OCR...")
                    respuestas = extraer_respuestas_con_gemini(pdf_bytes, uploaded_file.name)
                    
                    # Calificar
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
                    st.warning(f"⚠️ Error procesando {uploaded_file.name}: {str(e)}")
                    resultados.append({
                        'nombre': uploaded_file.name,
                        'correctas': 0,
                        'incorrectas': 0,
                        'sin_responder': 0,
                        'nota': 0,
                        'aprobado': False,
                        'error': str(e)
                    })
            
            # Calcular estadísticas
            estadisticas = calcular_estadisticas(resultados)
            
            st.session_state.resultados = resultados
            st.session_state.estadisticas = estadisticas
            
            progress_bar.progress(1.0)
            status_text.text("✅ ¡Procesamiento completado!")
            st.success("✓ Exámenes procesados exitosamente")
            st.balloons()

st.markdown("---")

# PASO 5: RESULTADOS

if st.session_state.resultados and st.session_state.estadisticas:
    st.header("Paso 5️⃣ - Resultados")
    
    stats = st.session_state.estadisticas
    
    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 Promedio (s/20)", f"{stats.get('promedio_general', 0):.2f}")
    with col2:
        st.metric("✅ Aprobados", stats.get('cantidad_aprobados', 0))
    with col3:
        st.metric("❌ Desaprobados", stats.get('cantidad_desaprobados', 0))
    with col4:
        st.metric("👥 Total", stats.get('total_estudiantes', 0))
    
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
    
    # Estadísticas
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Estadísticas")
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
        
        **Curso**: {codigo_curso}
        
        **Fecha**: {stats['fecha_procesamiento']}
        """)
    
    st.markdown("---")
    
    # Descargas
    st.subheader("📥 Opciones de Descarga")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        csv_data = df_display.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📊 CSV",
            data=csv_data,
            file_name=f"calificaciones_{codigo_curso}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        json_data = json.dumps({
            'curso': nombre_curso,
            'codigo': codigo_curso,
            'estadisticas': stats,
            'resultados': st.session_state.resultados,
            'fecha': datetime.now().isoformat()
        }, indent=2, ensure_ascii=False)
        
        st.download_button(
            label="📄 JSON",
            data=json_data,
            file_name=f"reporte_{codigo_curso}_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
            use_container_width=True
        )
    
    with col3:
        html_report = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial; margin: 40px; background: white; }}
                .header {{ text-align: center; border-bottom: 3px solid #1f4788; padding: 20px 0; }}
                h1 {{ color: #1f4788; margin: 0; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th {{ background: #1f4788; color: white; padding: 12px; text-align: left; }}
                td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
                .stats {{ background: #e7f3ff; padding: 20px; margin: 20px 0; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📋 REPORTE DE CALIFICACIONES</h1>
                <p><strong>Curso:</strong> {nombre_curso}</p>
                <p><strong>Código:</strong> {codigo_curso}</p>
                <p><strong>Fecha:</strong> {stats['fecha_procesamiento']}</p>
            </div>
            
            <h2>📊 Calificaciones</h2>
            <table>
                <tr>
                    <th>PDF</th>
                    <th>Correctas</th>
                    <th>Incorrectas</th>
                    <th>Nota (s/20)</th>
                    <th>Estado</th>
                </tr>
        """
        
        for _, row in df_display.iterrows():
            html_report += f"""
                <tr>
                    <td>{row['PDF']}</td>
                    <td>{row['Correctas']}</td>
                    <td>{row['Incorrectas']}</td>
                    <td><strong>{row['Nota (s/20)']}</strong></td>
                    <td>{row['Estado']}</td>
                </tr>
            """
        
        html_report += f"""
            </table>
            
            <div class="stats">
                <h2>📈 Estadísticas Generales</h2>
                <p><strong>Total de Estudiantes:</strong> {stats['total_estudiantes']}</p>
                <p><strong>Promedio General (s/20):</strong> {stats['promedio_general']:.2f}</p>
                <p><strong>Promedio Aprobados (s/20):</strong> {stats['promedio_aprobados']:.2f}</p>
                <p><strong>Aprobados:</strong> {stats['cantidad_aprobados']}</p>
                <p><strong>Desaprobados:</strong> {stats['cantidad_desaprobados']}</p>
                <p><strong>Tasa de Aprobación:</strong> {stats['tasa_aprobacion']:.1f}%</p>
                <p><strong>Nota Máxima:</strong> {stats['nota_maxima']:.2f}</p>
                <p><strong>Nota Mínima:</strong> {stats['nota_minima']:.2f}</p>
            </div>
        </body>
        </html>
        """
        
        st.download_button(
            label="📋 HTML",
            data=html_report,
            file_name=f"reporte_{codigo_curso}_{datetime.now().strftime('%Y%m%d')}.html",
            mime="text/html",
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
    <p>🎓 Calificador Automático de Exámenes | v3.0 (100% Streamlit)</p>
    <p>Optimizado para dispositivos móviles y desktop</p>
    <p>Powered by Google Gemini Vision OCR</p>
</div>
""", unsafe_allow_html=True)

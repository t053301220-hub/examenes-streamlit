import streamlit as st
import requests
import json
import base64
from datetime import datetime
import pandas as pd

# ==================== CONFIGURACIÓN ====================

st.set_page_config(
    page_title="Calificador de Exámenes",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ⚠️ IMPORTANTE: CAMBIA ESTA URL POR TU WEBHOOK DE N8N
N8N_WEBHOOK_URL = "https://n8n-xxxx.n8n.cloud/webhook/examenes-calificar"

# CSS para móvil
st.markdown("""
<style>
    @media (max-width: 768px) {
        .main {
            padding: 0;
        }
        .block-container {
            padding: 1rem;
        }
    }
    
    .stButton > button {
        width: 100%;
    }
    
    .success-box {
        background-color: #d4edda;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 5px solid #28a745;
    }
    
    .stats-box {
        background-color: #e7f3ff;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 5px solid #004085;
    }
</style>
""", unsafe_allow_html=True)

# Inicializar sesión
if 'resultados' not in st.session_state:
    st.session_state.resultados = None
if 'estadisticas' not in st.session_state:
    st.session_state.estadisticas = None
if 'procesando' not in st.session_state:
    st.session_state.procesando = False

# ==================== HEADER ====================

st.title("📋 Calificador Automático de Exámenes")
st.markdown("Solución en la nube con N8N + Streamlit")
st.markdown("---")

# ==================== PASO 1: INFORMACIÓN DEL CURSO ====================

st.header("Paso 1️⃣ - Información del Curso")

col1, col2 = st.columns(2)

with col1:
    nombre_curso = st.text_input(
        "Nombre del Curso",
        placeholder="Ej: Matemáticas I",
        help="Ingresa el nombre del curso"
    )

with col2:
    codigo_curso = st.text_input(
        "Código del Curso",
        placeholder="Ej: MAT-101",
        help="Código único del curso"
    )

st.markdown("---")

# ==================== PASO 2: CLAVES DE RESPUESTA ====================

st.header("Paso 2️⃣ - Claves de Respuesta")

st.info("📝 Formato: Separar preguntas con comas\n\n"
        "**Ejemplo múltiple**: `1:a, 2:d, 3:e, 4:b`\n\n"
        "**Ejemplo binario**: `1:v, 2:f, 3:v`\n\n"
        "**Mixto**: `1:a, 2:d, 3:e, 4:v, 5:f`")

claves_input = st.text_area(
    "Ingresa las claves de respuesta",
    height=80,
    placeholder="1:a, 2:d, 3:e, 4:v, 5:f",
    help="a,b,c,d,e para múltiple choice | v,f para verdadero/falso"
)

# Validar y mostrar claves procesadas
if claves_input:
    try:
        claves_lista = [x.strip() for x in claves_input.split(',')]
        st.success(f"✓ {len(claves_lista)} preguntas detectadas")
        
        # Mostrar en dos columnas
        col1, col2 = st.columns(2)
        with col1:
            st.text("**Preguntas procesadas:**")
            for clave in claves_lista[:len(claves_lista)//2]:
                st.text(f"  {clave}")
        with col2:
            for clave in claves_lista[len(claves_lista)//2:]:
                st.text(f"  {clave}")
    except Exception as e:
        st.error(f"❌ Error al procesar claves: {e}")

st.markdown("---")

# ==================== PASO 3: CARGAR PDFs ====================

st.header("Paso 3️⃣ - Cargar PDFs de Respuestas")

uploaded_files = st.file_uploader(
    "Sube los PDFs de respuestas (máximo 30)",
    type="pdf",
    accept_multiple_files=True,
    help="Selecciona hasta 30 archivos PDF"
)

if uploaded_files:
    st.success(f"✓ {len(uploaded_files)} archivo(s) cargado(s)")
    
    if len(uploaded_files) > 30:
        st.error("❌ Máximo 30 PDFs permitidos")
    else:
        # Mostrar lista de archivos
        with st.expander(f"📄 Ver archivos cargados ({len(uploaded_files)})"):
            for idx, file in enumerate(uploaded_files, 1):
                st.text(f"{idx}. {file.name} ({file.size/1024:.2f} KB)")

st.markdown("---")

# ==================== PASO 4: PROCESAR ====================

st.header("Paso 4️⃣ - Procesar Exámenes")

if st.button("🚀 Procesar Exámenes", use_container_width=True, type="primary"):
    # Validaciones
    if not nombre_curso:
        st.error("❌ Por favor ingresa el nombre del curso")
    elif not codigo_curso:
        st.error("❌ Por favor ingresa el código del curso")
    elif not claves_input:
        st.error("❌ Por favor ingresa las claves de respuesta")
    elif not uploaded_files:
        st.error("❌ Por favor carga al menos un PDF")
    elif len(uploaded_files) > 30:
        st.error("❌ Máximo 30 PDFs permitidos")
    else:
        # Mostrar progreso
        progress_bar = st.progress(0)
        status_text = st.empty()
        st.session_state.procesando = True
        
        try:
            # Convertir PDFs a base64
            status_text.text("📖 Preparando archivos...")
            progress_bar.progress(20)
            
            archivos_pdfs = []
            for file in uploaded_files:
                pdf_content = base64.b64encode(file.read()).decode('utf-8')
                archivos_pdfs.append({
                    "nombre": file.name,
                    "contenido": pdf_content
                })
            
            progress_bar.progress(40)
            status_text.text("📡 Enviando a N8N...")
            
            # Preparar payload
            payload = {
                "nombre_curso": nombre_curso,
                "codigo_curso": codigo_curso,
                "claves": claves_input,
                "archivos_pdfs": archivos_pdfs
            }
            
            # Enviar a N8N
            response = requests.post(
                N8N_WEBHOOK_URL,
                json=payload,
                timeout=300  # 5 minutos
            )
            
            progress_bar.progress(80)
            status_text.text("⏳ Procesando respuestas...")
            
            if response.status_code == 200:
                data = response.json()
                st.session_state.resultados = data.get('resultados', [])
                st.session_state.estadisticas = data.get('estadisticas', {})
                
                progress_bar.progress(100)
                status_text.text("✅ ¡Procesamiento completado!")
                st.success("✓ Exámenes procesados exitosamente")
                st.balloons()
                
            else:
                st.error(f"❌ Error: {response.status_code}")
                st.error(f"Respuesta: {response.text}")
        
        except requests.exceptions.Timeout:
            st.error("❌ Timeout: El procesamiento tardó demasiado")
        except requests.exceptions.ConnectionError:
            st.error("❌ Error de conexión con N8N. Verifica tu URL")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
        finally:
            st.session_state.procesando = False

st.markdown("---")

# ==================== PASO 5: RESULTADOS ====================

if st.session_state.resultados and st.session_state.estadisticas:
    st.header("Paso 5️⃣ - Resultados")
    
    # Estadísticas principales
    stats = st.session_state.estadisticas
    
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
    df_display.columns = ['PDF', 'Correctas', 'Incorrectas', 'Nota', 'Estado']
    
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # Estadísticas adicionales
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Estadísticas")
        stats_info = f"""
        **Promedio General**: {stats.get('promedio_general', 0):.2f}
        
        **Promedio Aprobados**: {stats.get('promedio_aprobados', 0):.2f}
        
        **Nota Máxima**: {stats.get('nota_maxima', 0):.2f}
        
        **Nota Mínima**: {stats.get('nota_minima', 0):.2f}
        """
        st.info(stats_info)
    
    with col2:
        st.subheader("👥 Resumen")
        tasa_aprobacion = (stats.get('cantidad_aprobados', 0) / max(stats.get('total_estudiantes', 1), 1)) * 100
        resumen_info = f"""
        **Total Procesados**: {stats.get('total_estudiantes', 0)}
        
        **Tasa Aprobación**: {tasa_aprobacion:.1f}%
        
        **Fecha**: {datetime.now().strftime('%d/%m/%Y %H:%M')}
        
        **Curso**: {codigo_curso}
        """
        st.info(resumen_info)
    
    st.markdown("---")
    
    # Opciones de descarga
    st.subheader("📥 Opciones de Descarga")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Descargar como CSV
        csv_data = df_display.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📊 Descargar como CSV",
            data=csv_data,
            file_name=f"calificaciones_{codigo_curso}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        # Descargar como JSON
        json_data = json.dumps({
            'curso': nombre_curso,
            'codigo': codigo_curso,
            'estadisticas': stats,
            'resultados': st.session_state.resultados,
            'fecha': datetime.now().isoformat()
        }, indent=2, ensure_ascii=False)
        
        st.download_button(
            label="📄 Descargar como JSON",
            data=json_data,
            file_name=f"reporte_{codigo_curso}_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
            use_container_width=True
        )
    
    st.markdown("---")
    
    # Botón limpiar
    if st.button("🔄 Procesar Nuevamente", use_container_width=True):
        st.session_state.resultados = None
        st.session_state.estadisticas = None
        st.rerun()

# ==================== FOOTER ====================

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray; font-size: 12px;'>
    <p>🎓 Calificador Automático de Exámenes | v2.0 (N8N Cloud + Streamlit Cloud)</p>
    <p>Optimizado para dispositivos móviles y desktop</p>
    <p>⚠️ Asegúrate de actualizar N8N_WEBHOOK_URL con tu webhook real</p>
</div>
""", unsafe_allow_html=True)
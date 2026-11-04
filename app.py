import streamlit as st
import subprocess
import requests
import json
import os
import re
import time

# Configuración de la página
st.set_page_config(page_title="Analizador Sintáctico - Bachillerato", layout="wide")
st.title("📐 Generador de Cajas Sintácticas")

# --- Configuración de la API Key en la barra lateral (para uso web) ---
st.sidebar.header("⚙️ Configuración")
user_api_key = st.sidebar.text_input("Introduce tu Gemini API Key:", type="password")

# Solo usa la clave introducida por el usuario en la interfaz web
api_key = user_api_key.strip().strip('"').strip("'")
api_key = re.sub(r'[^\w\.-]', '', api_key)

# Si no introduce nada, la app se detiene y le avisa amablemente en pantalla
if not api_key:
    st.warning("Por favor, introduce tu Gemini API Key en el menú lateral para poder utilizar la aplicación.")
    st.stop()

# Campo de texto para la oración
oracion = st.text_input(
    "Introduce la oración a analizar:", 
    value=""
)

if st.button("Analizar Oración"):
    if not oracion.strip():
        st.warning("Por favor, escribe una oración.")
    elif not api_key:
        st.sidebar.error("Error: Por favor, introduce tu Gemini API Key en la barra lateral.")
        st.error("Error: GEMINI_API_KEY no está configurada.")
    else:
        with st.spinner("Analizando oración y calculando niveles..."):
            
            # 1. Borrar archivos temporales antiguos
            for f in ["analisis.pdf", "analisis_out.png", "analisis.tex"]:
                if os.path.exists(f):
                    os.remove(f)

            # 2. Prompt pedagógico estructurado (JSON)
            prompt = f"""
Analiza sintácticamente la siguiente oración para 1º de Bachillerato en España: "{oracion}".

Devuelve ÚNICAMENTE un objeto JSON válido con esta estructura:
{{
  "words": ["palabra1", "palabra2", ...],
  "analysis": [
    {{"level": 1, "start": 0, "end": 0, "label": "D", "color": "cSuj"}},
    {{"level": 1, "start": 1, "end": 1, "label": "N", "color": "cSuj"}}
  ]
}}

REGLAS PEDAGÓGICAS Y ESTRUCTURALES OBLIGATORIAS:

1. TRATAMIENTO OBLIGATORIO DE SUJETOS OMITIDOS / ELÍPTICOS (SO):
   - Si un verbo principal o subordinado NO tiene sujeto explícito en la oración, ES OBLIGATORIO incluir el Sujeto Omitido en la etiqueta del Predicado entre paréntesis.
   - Ejemplo: "SV / PV (SO: ellos)", "SV / PV (SO: él/ella)", "SV / PV (SO: tú)".

2. ALINEACIÓN Y NIVELES VERTICALES (level):
   - Level 1: Categorías gramaticales individuales de TODAS las palabras (D, N, V, E, Nx...).
   - Level 2: Sintagmas simples inmediatos, Términos ("SN / T") y CD/CI/CC internos.
   - En CUALQUIER cláusula, el "SN / Suj" explícito y el "SV / PV" que están al mismo nivel sintáctico DEBEN compartir el mismo "level" (siempre que no se contengan).
   - NINGUNA caja/línea que contenga a otra puede tener un "level" menor o igual al de la caja contenida.

3. REGLAS ESTRICTAS DE COLOR:
   - "cSuj" (Azul): Sujetos explícitos (principales o subordinados) y sus componentes internos.
   - "cNuc" (Rojo): Predicados ("SV / PV") y Verbos ("V").
   - "cObl" (Naranja): Complementos ARGUMENTALES ("CD", "CI", "Atributo", "C.Rég.") y Subordinadas Sustantivas.
   - "cOpt" (Verde): Complementos ADJUNTOS/CIRCUNSTANCIALES (CC) y Subordinadas Adverbiales o Adjetivas (CN).
   - "cOrac" (Gris): La línea general "Oración Compuesta" / "Oración Simple" y Nexos (Nx).
"""

            # 3. Llamada a la API de Gemini con el modelo correcto
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"response_mime_type": "application/json"}
            }
            headers = {"Content-Type": "application/json"}

            res_data = None
            error_detalles = ""
            for intento in range(3):
                response = requests.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    res_data = response.json()
                    break
                else:
                    error_detalles = response.text
                    if response.status_code == 503:
                        time.sleep(2)

            if res_data and "candidates" in res_data:
                json_

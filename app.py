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
    value=" "
)

if st.button("Analizar Oración"):
    if not oracion.strip():
        st.warning("Por favor, escribe una oración.")
    elif not api_key:
        st.sidebar.error("Error: Por favor, introduce tu Gemini API Key en la barra lateral.")
        st.error("Error: GEMINI_API_KEY no está configurada en las variables de entorno ni en la barra lateral.")
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

            # 3. Llamada a la API de Gemini
           url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"response_mime_type": "application/json"}
            }
            headers = {"Content-Type": "application/json"}

            # Reintentos automáticos para evitar errores 503
            res_data = None
            for intento in range(3):
                response = requests.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    res_data = response.json()
                    break
                elif response.status_code == 503:
                    time.sleep(2)

            if res_data and "candidates" in res_data:
                json_text = res_data['candidates'][0]['content']['parts'][0]['text']
                data = json.loads(json_text)

                words = data.get("words", [])
                analysis = data.get("analysis", [])

                # 4. ALGORITMO DE AUTOCORRECCIÓN DE NIVEL EN PYTHON
                changed = True
                while changed:
                    changed = False
                    for i in range(len(analysis)):
                        for j in range(len(analysis)):
                            if i == j:
                                continue
                            item1 = analysis[i]
                            item2 = analysis[j]
                            s1, e1, l1 = item1.get("start", 0), item1.get("end", 0), item1.get("level", 1)
                            s2, e2, l2 = item2.get("start", 0), item2.get("end", 0), item2.get("level", 1)

                            if (s1 <= s2 and e1 >= e2) and (e1 - s1 > e2 - s2):
                                if l1 <= l2:
                                    item1["level"] = l2 + 1
                                    changed = True
                            elif max(s1, s2) <= min(e1, e2) and l1 == l2:
                                if (e1 - s1) >= (e2 - s2):
                                    item1["level"] = l2 + 1
                                else:
                                    item2["level"] = l1 + 1
                                changed = True

                # 5. GENERACIÓN DEL CÓDIGO TIKZ / LATEX
                tikz_elements = []

                for i, w in enumerate(words):
                    w_clean = w.replace("&", "\\&").replace("%", "\\%")
                    if i == 0:
                        tikz_elements.append(f'    \\node (w0) [word] {{{w_clean}}};')
                    else:
                        tikz_elements.append(f'    \\node (w{i}) [word, right=of w{i-1}] {{{w_clean}}};')

                max_level = max([item.get("level", 1) for item in analysis], default=5)
                for lvl in range(1, max_level + 1):
                    y_pos = -0.85 * lvl
                    tikz_elements.append(f'    \\coordinate (y{lvl}) at (0, {y_pos:.2f});')

                for item in analysis:
                    lvl = item.get("level", 1)
                    start = max(0, min(item.get("start", 0), len(words) - 1))
                    end = max(0, min(item.get("end", 0), len(words) - 1))
                    label = item.get("label", "").replace("&", "\\&").replace("%", "\\%")
                    color = item.get("color", "cOrac")

                    tikz_elements.append(
                        f'    \\draw[{color}, line width=1.3pt] (w{start}.west |- y{lvl}) -- (w{end}.east |- y{lvl}) node[midway, below, tag, {color}] {{{label}}};'
                    )

                tikz_body = "\n".join(tikz_elements)

                latex_code = f"""\\documentclass[tikz,border=20pt]{{standalone}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{helvet}}
\\renewcommand{{\\familydefault}}{{\\sfdefault}}
\\usepackage{{xcolor}}
\\usepackage{{amssymb}}
\\usetikzlibrary{{calc,positioning}}

\\pagecolor{{white}}

\\definecolor{{cSuj}}{{RGB}}{{37, 99, 235}}   % Azul
\\definecolor{{cNuc}}{{RGB}}{{196, 30, 58}}   % Rojo
\\definecolor{{cObl}}{{RGB}}{{217, 119, 6}}   % Naranja
\\definecolor{{cOpt}}{{RGB}}{{22, 128, 61}}   % Verde
\\definecolor{{cOrac}}{{RGB}}{{31, 41, 55}}   % Gris

\\begin{{document}}
\\begin{{tikzpicture}}[
    node distance=0.45cm,
    word/.style={{font=\\bfseries\\Large, inner xsep=4pt, inner ysep=2pt}},
    tag/.style={{font=\\small\\bfseries, inner sep=2pt}}
]

{tikz_body}

\\end{{tikzpicture}}
\\end{{document}}"""

                # 6. Guardar archivo .tex y compilar a PDF y PNG
                with open("analisis.tex", "w", encoding="utf-8") as f:
                    f.write(latex_code)

                subprocess.run(["pdflatex", "-interaction=nonstopmode", "analisis.tex"], stdout=subprocess.DEVNULL)
                subprocess.run(["pdftoppm", "-png", "-r", "150", "-singlefile", "analisis.pdf", "analisis_out"], stdout=subprocess.DEVNULL)

                # Limpieza de archivos secundarios .aux y .log
                for temp in ["analisis.aux", "analisis.log"]:
                    if os.path.exists(temp):
                        os.remove(temp)

                # 7. Renderizado en Streamlit
                if os.path.exists("analisis_out.png"):
                    st.image("analisis_out.png", caption=f"Análisis Sintáctico: {oracion}", use_container_width=True)

                    with open("analisis.pdf", "rb") as pdf_file:
                        st.download_button(
                            label="📄 Descargar diagrama en PDF",
                            data=pdf_file,
                            file_name="analisis_sintactico.pdf",
                            mime="application/pdf"
                        )
                else:
                    st.error("Error al generar la imagen. Revisa la compilación de LaTeX.")
            else:
                st.error("No se pudo obtener respuesta válida de Gemini.")

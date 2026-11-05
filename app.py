import streamlit as st
import subprocess
import requests
import json
import os
import re
import time

# Configuración de la página
st.set_page_config(page_title="Analizador Sintáctico - Bachillerato NGLE", layout="wide")
st.title("📐 Generador de Cajas Sintácticas (Rigurosidad NGLE)")

# --- Configuración de la API Key en la barra lateral (para uso web) ---
st.sidebar.header("⚙️ Configuración")
user_api_key = st.sidebar.text_input("Introduce tu Gemini API Key:", type="password")

api_key = user_api_key.strip().strip('"').strip("'")
api_key = re.sub(r'[^\w\.-]', '', api_key)

if not api_key:
    st.warning("Por favor, introduce tu Gemini API Key en el menú lateral para poder utilizar la aplicación.")
    st.stop()

# Campo de texto para la oración
oracion = st.text_input(
    "Introduce la oración a analizar:", 
    value="La materia orgánica es la que se quema para liberar la energía que contiene en su interior, nos comenta el autor"
)

if st.button("Analizar Oración"):
    if not oracion.strip():
        st.warning("Por favor, escribe una oración.")
    elif not api_key:
        st.sidebar.error("Error: Por favor, introduce tu Gemini API Key en la barra lateral.")
        st.error("Error: GEMINI_API_KEY no está configurada.")
    else:
        with st.spinner("Analizando sintaxis bajo criterios estrictos de la NGLE..."):
            
            # 1. Borrar archivos temporales antiguos
            for f in ["analisis.pdf", "analisis_out.png", "analisis.tex"]:
                if os.path.exists(f):
                    os.remove(f)

            # 2. Prompt estricto NGLE / RAE enfocado a evitar solapamientos
            prompt = f"""
Actúa como un catedrático experto en la Nueva Gramática de la Lengua Española (NGLE) de la RAE.
Analiza sintácticamente la oración: "{oracion}".

Devuelve ÚNICAMENTE un objeto JSON válido con esta estructura estricta:
{{
  "words": ["palabra1", "palabra2", ...],
  "analysis": [
    {{"level": 1, "start": 0, "end": 0, "label": "D", "color": "cSuj"}},
    {{"level": 2, "start": 0, "end": 2, "label": "SN / Sujeto", "color": "cSuj"}}
  ]
}}

REGLAS DE ORO PARA EVITAR SOLAPAMIENTOS Y ERRORES:
1. Índices precisos: "start" y "end" son los índices numéricos exactos de las palabras en el array "words" (empezando en 0). Asegúrate de que las cajas complejas abarquen exactamente el rango correcto sin solapar etiquetas vecinas en el mismo nivel.
2. Jerarquía estricta de niveles (level):
   - Level 1: Clases de palabras / categorías (D, N, V, E, Pron, Conj, etc.).
   - Level 2: Sintagmas inmediatos (SN, SV, S.Prep, S.Adj).
   - Level 3 o superior: Funciones sintácticas complejas (Sujeto, CD, CI, Atributo, CC, Proposiciones Subordinadas).
3. Nunca pongas dos etiquetas distintas que ocupen exactamente las mismas palabras en el mismo "level". Si una estructura contiene a otra, su "level" debe ser estrictamente mayor.
4. Colores obligatorios:
   - "cSuj" (Azul): Sujetos y sus componentes.
   - "cNuc" (Rojo): Predicados y Núcleos verbales.
   - "cObl" (Naranja): Complementos argumentales (CD, CI, Atributo, C.Rég) y subordinadas sustantivas.
   - "cOpt" (Verde): Adjuntos (CC) y subordinadas adjetivas/adverbiales.
   - "cOrac" (Gris): Estructuras oracionales generales y nexos (Nx).
"""

            # 3. Llamada a la API con sistema en cascada
            modelos_disponibles = ["gemini-1.5-flash", "gemini-2.5-flash", "gemini-1.5-pro"]
            res_data = None
            error_detalles = ""

            for modelo in modelos_disponibles:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={api_key}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"response_mime_type": "application/json"}
                }
                headers = {"Content-Type": "application/json"}

                modelo_exitoso = False
                for intento in range(2):
                    response = requests.post(url, json=payload, headers=headers)
                    if response.status_code == 200:
                        res_data = response.json()
                        modelo_exitoso = True
                        break
                    else:
                        error_detalles = f"[{modelo}] {response.text}"
                        if response.status_code in [429, 503]:
                            time.sleep(1)

                if modelo_exitoso:
                    break

            if res_data and "candidates" in res_data:
                json_text = res_data['candidates'][0]['content']['parts'][0]['text']
                data = json.loads(json_text)

                words = data.get("words", [])
                analysis = data.get("analysis", [])

                # 4. ALGORITMO ANTISOLAPAMIENTO Y AUTOCORRECCIÓN DE NIVELES
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

                            # Si se solapan parcialmente o una contiene a otra en el mismo nivel, escalamos niveles
                            if l1 == l2 and max(s1, s2) <= min(e1, e2):
                                if (e1 - s1) >= (e2 - s2):
                                    item1["level"] = l2 + 1
                                else:
                                    item2["level"] = l1 + 1
                                changed = True
                            elif (s1 <= s2 and e1 >= e2) and (e1 - s1 > e2 - s2) and l1 <= l2:
                                item1["level"] = l2 + 1
                                changed = True

                # 5. GENERACIÓN DEL CÓDIGO TIKZ / LATEX CON SEPARACIÓN VERTICAL ÓPTIMA
                tikz_elements = []

                for i, w in enumerate(words):
                    w_clean = w.replace("&", "\\&").replace("%", "\\%")
                    if i == 0:
                        tikz_elements.append(f'    \\node (w0) [word] {{{w_clean}}};')
                    else:
                        tikz_elements.append(f'    \\node (w{i}) [word, right=of w{i-1}] {{{w_clean}}};')

                max_level = max([item.get("level", 1) for item in analysis], default=5)
                for lvl in range(1, max_level + 1):
                    y_pos = -0.9 * lvl  # Espaciado vertical ligeramente mayor para evitar solapamientos visuales
                    tikz_elements.append(f'    \\coordinate (y{lvl}) at (0, {y_pos:.2f});')

                for item in analysis:
                    lvl = item.get("level", 1)
                    start = max(0, min(item.get("start", 0), len(words) - 1))
                    end = max(0, min(item.get("end", 0), len(words) - 1))
                    label = item.get("label", "").replace("&", "\\&").replace("%", "\\%")
                    color = item.get("color", "cOrac")

                    tikz_elements.append(
                        f'    \\draw[{color}, line width=1.2pt] (w{start}.west |- y{lvl}) -- (w{end}.east |- y{lvl}) node[midway, below, tag, {color}] {{{label}}};'
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

\\definecolor{{cSuj}}{{RGB}}{{37, 99, 235}}    % Azul
\\definecolor{{cNuc}}{{RGB}}{{196, 30, 58}}    % Rojo
\\definecolor{{cObl}}{{RGB}}{{217, 119, 6}}    % Naranja
\\definecolor{{cOpt}}{{RGB}}{{22, 128, 61}}    % Verde
\\definecolor{{cOrac}}{{RGB}}{{31, 41, 55}}    % Gris

\\begin{{document}}
\\begin{{tikzpicture}}[
    node distance=0.5cm,
    word/.style={{font=\\bfseries\\Large, inner xsep=5pt, inner ysep=3pt}},
    tag/.style={{font=\\small\\bfseries, inner sep=2pt}}
]

{tikz_body}

\\end{{tikzpicture}}
\\end{{document}}"""

                # 6. Guardar archivo .tex y compilar a PDF y PNG
                with open("analisis.tex", "w", encoding="utf-8") as f:
                    f.write(latex_code)

                proceso_latex = subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", "analisis.tex"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                if proceso_latex.returncode != 0:
                    st.error("Error en la compilación de LaTeX:")
                    st.text(proceso_latex.stdout[-1500:])
                else:
                    subprocess.run(
                        ["pdftoppm", "-png", "-r", "150", "-singlefile", "analisis.pdf", "analisis_out"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )

                for temp in ["analisis.aux", "analisis.log"]:
                    if os.path.exists(temp):
                        os.remove(temp)

                # 7. Renderizado en Streamlit
                if os.path.exists("analisis_out.png"):
                    st.image("analisis_out.png", caption=f"Análisis Sintáctico (NGLE): {oracion}", use_container_width=True)

                    with open("analisis.pdf", "rb") as pdf_file:
                        st.download_button(
                            label="📄 Descargar diagrama en PDF",
                            data=pdf_file,
                            file_name="analisis_sintactico_ngle.pdf",
                            mime="application/pdf"
                        )
                else:
                    if proceso_latex.returncode == 0:
                        st.error("Error al generar la imagen con pdftoppm.")
            else:
                st.error(f"Error al procesar la oración. Detalles: {error_detalles}")

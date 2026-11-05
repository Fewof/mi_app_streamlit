import streamlit as st
import subprocess
import requests
import json
import os
import re
import time

# Configuración de la página
st.set_page_config(page_title="Analizador Sintáctico - Bachillerato NGLE (Qwen)", layout="wide")
st.title("📐 Generador de Cajas Sintácticas (Motor Qwen - NGLE)")

# --- Configuración de la API Key en la barra lateral ---
st.sidebar.header("⚙️ Configuración")
user_api_key = st.sidebar.text_input("Introduce tu Qwen (DashScope) API Key:", type="password")

api_key = user_api_key.strip().strip('"').strip("'")
api_key = re.sub(r'[^\w\.-]', '', api_key)

if not api_key:
    st.warning("Por favor, introduce tu API Key de Qwen en el menú lateral para poder utilizar la aplicación.")
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
        st.sidebar.error("Error: Por favor, introduce tu API Key en la barra lateral.")
        st.error("Error: API Key no configurada.")
    else:
        with st.spinner("Analizando sintaxis con rigor estricto NGLE mediante Qwen..."):
            
            # 1. Borrar archivos temporales antiguos
            for f in ["analisis.pdf", "analisis_out.png", "analisis.tex"]:
                if os.path.exists(f):
                    os.remove(f)

            # 2. Prompt estricto y depurado para la sintaxis académica en español (NGLE)
            prompt = f"""
Actúa como un catedrático experto en la Nueva Gramática de la Lengua Española (NGLE) de la RAE.
Analiza sintácticamente con absoluta precisión y rigor académico la oración: "{oracion}".

CRITERIOS SINTÁCTICOS OBLIGATORIOS:
- Identifica correctamente la oración principal y sus incisos o complementos anticipados (por ejemplo, si hay una cita o inciso en posición invertida como "nos comenta el autor", el verbo principal es "comenta", "el autor" es el sujeto, "nos" es el CI, y todo el bloque anterior actúa globalmente como el Complemento Directo [CD] de dicho verbo).
- Aplica abreviaturas estándar en las etiquetas: "SN / Suj", "SV / PV", "CD", "CI", "N", "D", "E", "T", "S.Prep", "Atrib", "CC", "Nx", etc.

Devuelve ÚNICAMENTE un objeto JSON válido con esta estructura exacta:
{{
  "words": ["palabra1", "palabra2", ...],
  "analysis": [
    {{"level": 1, "start": 0, "end": 0, "label": "D", "color": "cSuj"}},
    {{"level": 2, "start": 0, "end": 2, "label": "SN / Suj", "color": "cSuj"}}
  ]
}}

REGLAS DE ORO:
1. "start" y "end" deben ser los índices exactos de las palabras en el array "words" (empezando en 0).
2. Jerarquía estricta de niveles (level): Las cajas contenedoras deben tener un "level" superior a las contenidas para evitar cruces.
3. Colores obligatorios:
   - "cSuj" (Azul): Sujetos y sus componentes.
   - "cNuc" (Rojo): Predicados y Núcleos verbales.
   - "cObl" (Naranja): Argumentos (CD, CI, Atributo, C.Rég).
   - "cOpt" (Verde): Adjuntos (CC) y subordinadas adjetivas/adverbiales.
   - "cOrac" (Gris): Estructura oracional general y nexos (Nx).
"""

            # 3. Endpoint oficial de Qwen (DashScope compatible con formato OpenAI)
            # Usamos el modelo 'qwen-plus' o 'qwen-max' que tienen un razonamiento gramatical excelente.
            url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions"
            
            payload = {
                "model": "qwen-plus",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.0  # Temperatura a 0 para garantizar análisis 100% deterministas y sin variaciones
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }

            res_data = None
            error_detalles = ""
            
            for intento in range(2):
                response = requests.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    res_data = response.json()
                    break
                else:
                    error_detalles = response.text
                    if response.status_code in [429, 503]:
                        time.sleep(1)

            if res_data and "choices" in res_data:
                json_text = res_data['choices'][0]['message']['content']
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
                    y_pos = -0.9 * lvl
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
                with open("analisis.tex", "w

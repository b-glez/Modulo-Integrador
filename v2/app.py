import streamlit as st
import os
import json
import pandas as pd
import numpy as np
from openai import OpenAI
from collections import Counter

st.set_page_config(page_title="CocinaAI — Tu chef de alacena", page_icon="🌮", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=DM+Sans:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background-color: #FDF6EE; }
#MainMenu, header, footer { visibility: hidden; }
.hero-title { font-family: 'Playfair Display', serif; font-size: 2.4rem; font-weight: 700; color: #1C1208; margin-bottom: 0.15rem; }
.hero-sub { font-size: 0.95rem; color: #7A6550; margin-bottom: 1.5rem; font-weight: 300; }
.step-label { font-size: 0.75rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.08em; color: #B5722A; margin-bottom: 0.5rem; margin-top: 1rem; }
.stButton > button { background-color: #B5722A !important; color: #FFF8F0 !important; border: none !important; border-radius: 10px !important; font-weight: 500 !important; }
.stButton > button:hover { background-color: #9A5E1F !important; }
[data-testid="stChatInputTextArea"] { background-color: #FFF8F0 !important; }
.data-badge { display: inline-block; background: #F2E4CE; color: #7A4F1E; font-size: 0.75rem; padding: 3px 10px; border-radius: 99px; margin: 2px 3px; }
.data-badge.match { background: #DFF5E8; color: #1D6B3A; }
</style>
""", unsafe_allow_html=True)

# ── Cargar datos del EDA ──────────────────────────────────────────────────────
@st.cache_data
def load_data():
    try:
        import os
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        df = pd.read_csv(os.path.join(BASE_DIR, "data", "recipes_df.csv"))
        with open(os.path.join(BASE_DIR, "data", "top_ingredientes_alacena.json")) as f:
            top_ings = json.load(f)
        return df, top_ings
    except Exception as e:
        return None, []

recipes_df, top_ingredientes = load_data()

# ── Tools del EDA ─────────────────────────────────────────────────────────────
def get_perfil_alacena(ingredientes_usuario: list) -> dict:
    """
    Analiza qué tan comunes son los ingredientes del usuario
    en el dataset de recetas mexicanas del EDA.
    Conecta el análisis de datos con la recomendación en tiempo real.
    """
    if recipes_df is None:
        return {"error": "Dataset no disponible"}

    user_set = set(i.lower().strip() for i in ingredientes_usuario)
    top_set = set(i.lower() for i in top_ingredientes)

    # Ingredientes del usuario que están en el top de alacena mexicana
    en_alacena = list(user_set & top_set)
    no_comunes = list(user_set - top_set)

    # Recetas del dataset que más coinciden con los ingredientes del usuario
    def calcular_match(ings_str):
        if not isinstance(ings_str, str):
            return 0
        ings = set(i.strip().lower() for i in ings_str.split(','))
        return len(ings & user_set) / max(len(user_set), 1)

    recipes_df['match_score'] = recipes_df['ingredientes'].apply(calcular_match)
    top_recetas = recipes_df.nlargest(3, 'match_score')[
        ['titulo', 'score_alacena', 'dificultad', 'tiempo_minutos', 'match_score']
    ].to_dict('records')

    # Score promedio de alacena para ingredientes similares
    score_promedio = recipes_df[recipes_df['match_score'] > 0]['score_alacena'].mean()

    return {
        "ingredientes_comunes_alacena_mexicana": en_alacena,
        "ingredientes_poco_comunes": no_comunes,
        "pct_en_alacena_tipica": round(len(en_alacena) / max(len(user_set), 1) * 100),
        "recetas_similares_en_dataset": top_recetas,
        "score_alacena_promedio_recetas_similares": round(score_promedio, 3) if not np.isnan(score_promedio) else 0,
        "total_recetas_analizadas": len(recipes_df),
        "fuente": "Análisis de 103 recetas mexicanas (Spoonacular + TheMealDB)"
    }

# ── Configuración ─────────────────────────────────────────────────────────────
ALACENA_CATEGORIAS = {
    "🫘 Legumbres (frijoles, lentejas, garbanzos)": ["frijoles", "lentejas", "garbanzos"],
    "🥫 Enlatados (atún, chiles, jitomate)": ["atún", "sardinas", "chiles chipotles", "jitomate en lata"],
    "🌾 Granos (arroz, pasta, harina, avena)": ["arroz", "pasta", "harina", "avena", "quinoa"],
    "🍫 Despensa dulce (cacao, mermelada, cajeta)": ["cacao", "mermelada", "cajeta", "chocolate"],
    "🥚 Básicos (huevos, tortillas, pan, leche)": ["huevos", "tortillas", "pan", "leche", "mantequilla"],
}

MODOS_ENERGIA = {
    "Con energía": {"emoji": "⚡", "tiempo": 90, "desc": "Podemos hacer algo elaborado y especial."},
    "Normal": {"emoji": "😊", "tiempo": 45, "desc": "Algo rico sin complicarnos demasiado."},
    "Cansada": {"emoji": "😴", "tiempo": 25, "desc": "Fácil, máximo 3 pasos, que esté bueno."},
    "Muerta de hambre": {"emoji": "🤤", "tiempo": 15, "desc": "Lo más rápido posible. Ya."},
}

MOMENTOS = {"Desayuno": "🌅", "Comida": "☀️", "Cena": "🌙", "Snack": "🍿"}

# ── Session state ─────────────────────────────────────────────────────────────
defaults = {
    "onboarding_done": False, "alacena_base": [], "modo_energia": "Normal",
    "momento": "Comida", "messages": [], "ingredientes_frescos": "",
    "perfil_data": None
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── System prompt ─────────────────────────────────────────────────────────────
def build_system_prompt(perfil_data=None):
    modo = MODOS_ENERGIA[st.session_state.modo_energia]
    alacena_str = f"\nTambién tiene en alacena: {', '.join(st.session_state.alacena_base)}." if st.session_state.alacena_base else ""

    perfil_str = ""
    if perfil_data and "error" not in perfil_data:
        en_alacena = perfil_data.get("ingredientes_comunes_alacena_mexicana", [])
        pct = perfil_data.get("pct_en_alacena_tipica", 0)
        recetas_sim = perfil_data.get("recetas_similares_en_dataset", [])
        recetas_str = ", ".join([r['titulo'] for r in recetas_sim[:2]]) if recetas_sim else "ninguna"
        perfil_str = f"""
ANÁLISIS DE DATOS DEL EDA (103 recetas mexicanas analizadas):
- {pct}% de los ingredientes del usuario son comunes en alacenas mexicanas típicas
- Ingredientes reconocidos como típicos: {', '.join(en_alacena) if en_alacena else 'ninguno en el top'}
- Recetas similares encontradas en el dataset: {recetas_str}
- Usa este análisis para contextualizar tus recomendaciones."""

    return f"""Eres CocinaAI, un chef experto y cálido en cocina mexicana tradicional y regional.
Tu misión es resolver la carga cognitiva de cocinar: cuando alguien llega cansada, con prisa o con hambre y no sabe qué hacer con lo que tiene.

CONTEXTO DEL USUARIO:
- Momento: {st.session_state.momento}
- Estado: {st.session_state.modo_energia} — {modo['desc']}
- Tiempo máximo sugerido: {modo['tiempo']} minutos
- Ingredientes frescos: {st.session_state.ingredientes_frescos}{alacena_str}
{perfil_str}

CÓMO RESPONDER:
1. Sugiere 1 receta DESTACADA — la mejor para este momento y estado.
2. Da 2 alternativas compactas (nombre, tiempo, por qué aplica).
3. Usa los ingredientes como PUNTO DE PARTIDA, no como restricción estricta.
4. Si una receta mejor requiere algo clave que no mencionó, pregunta UNA SOLA COSA.
5. Sé preciso con tipos de ingredientes — harina de trigo es diferente a masa de maíz,
   frijoles crudos son diferentes a frijoles cocidos, pollo crudo diferente a cocido.
   Si el tipo importa para la receta, pregunta antes de sugerirla.
6. Si una receta requiere un ingrediente en estado específico (cocido, descongelado, etc.),
   pregunta en qué estado lo tiene el usuario O incluye instrucciones desde ese paso.
7. Menciona sutilmente si la receta es balanceada cuando aplique.
8. Siempre incluye qué hacer con lo que sobre.
9. Tono según estado: con energía = entusiasta, cansada = directo y reconfortante,
   muerta de hambre = urgente y brevísimo.

REGLAS:
- Solo cocina mexicana auténtica. Sin tex-mex ni fusión.
- Siempre en español.
- Cálido y conversacional, como un amigo chef.
- Máximo 1 pregunta de seguimiento por turno."""

# ── API ───────────────────────────────────────────────────────────────────────
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
if not OPENAI_API_KEY:
    st.error("Falta la OPENAI_API_KEY.")
    st.stop()
client = OpenAI(api_key=OPENAI_API_KEY)

# ── UI ────────────────────────────────────────────────────────────────────────
st.markdown('<div class="hero-title">CocinaAI 🌮</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Tu chef de alacena. Dime qué tienes y cómo estás — yo me encargo del resto.</div>', unsafe_allow_html=True)

if not st.session_state.onboarding_done:
    st.markdown("#### Antes de empezar 🧺")
    st.markdown("*¿Qué tienes en tu alacena? Marca lo que sí tienes:*")

    alacena_sel = []
    for cat, items in ALACENA_CATEGORIAS.items():
        emoji = cat.split()[0]
        nombre = ' '.join(cat.split()[1:])
        seleccionados = st.multiselect(
            f"{emoji} {nombre}",
            options=items,
            key=f"ms_{cat}"
        )
        alacena_sel.extend(seleccionados)

    st.markdown('<div class="step-label">¿Qué estás preparando?</div>', unsafe_allow_html=True)
    momento_sel = st.radio(
        "momento",
        options=[f"{emoji} {m}" for m, emoji in MOMENTOS.items()],
        horizontal=True,
        label_visibility="collapsed",
        key="radio_momento"
    )
    st.session_state.momento = momento_sel.split(" ", 1)[1]
    
    st.markdown('<div class="step-label">¿Cómo estás ahorita?</div>', unsafe_allow_html=True)
    energia_sel = st.radio(
        "energia",
        options=[f"{info['emoji']} {modo}" for modo, info in MODOS_ENERGIA.items()],
        horizontal=True,
        label_visibility="collapsed",
        key="radio_energia"
    )
    st.session_state.modo_energia = energia_sel.split(" ", 1)[1]

    st.markdown('<div class="step-label">¿Qué tienes disponible?</div>', unsafe_allow_html=True)
    ing_input = st.text_area("ing", placeholder="ej. pollo, jitomate, cebolla, chile poblano, crema...",
                              height=80, label_visibility="collapsed")

    if st.button("¡A cocinar! →", use_container_width=True):
        if not ing_input.strip():
            st.warning("Escribe al menos un ingrediente.")
        else:
            st.session_state.alacena_base = alacena_sel
            st.session_state.ingredientes_frescos = ing_input.strip()
            st.session_state.onboarding_done = True

            # Ejecutar tool del EDA
            user_ings = [i.strip() for i in ing_input.split(',')]
            perfil = get_perfil_alacena(user_ings)
            st.session_state.perfil_data = perfil

            # Construir primer mensaje
            momento_txt = st.session_state.momento.lower()
            energia_txt = st.session_state.modo_energia.lower()
            alacena_txt = f" También tengo en alacena: {', '.join(alacena_sel)}." if alacena_sel else ""
            primer_msg = f"Hola! Preparo {momento_txt}, me siento {energia_txt}. Tengo: {ing_input.strip()}.{alacena_txt} ¿Qué me recomiendas?"

            st.session_state.messages.append({"role": "user", "content": primer_msg})

            with st.spinner("Analizando tu alacena y pensando en algo rico..."):
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": build_system_prompt(perfil)},
                        {"role": "user", "content": primer_msg}
                    ],
                    temperature=0.8
                )
                reply = resp.choices[0].message.content
                st.session_state.messages.append({"role": "assistant", "content": reply})

            st.rerun()

else:
    # Sidebar
    with st.sidebar:
        st.markdown("### Tu sesión")
        st.markdown(f"**{MOMENTOS[st.session_state.momento]} {st.session_state.momento}**")
        st.markdown(f"**{MODOS_ENERGIA[st.session_state.modo_energia]['emoji']} {st.session_state.modo_energia}**")
        st.markdown(f"*{st.session_state.ingredientes_frescos}*")

        # Mostrar perfil del EDA
        if st.session_state.perfil_data and "error" not in st.session_state.perfil_data:
            p = st.session_state.perfil_data
            st.divider()
            st.markdown("### 📊 Análisis de alacena")
            st.markdown(f"**{p['pct_en_alacena_tipica']}%** de tus ingredientes son típicos de cocinas mexicanas")
            if p['ingredientes_comunes_alacena_mexicana']:
                st.markdown("**Ingredientes reconocidos:**")
                for ing in p['ingredientes_comunes_alacena_mexicana']:
                    st.markdown(f"✓ {ing}")
            if p['recetas_similares_en_dataset']:
                st.markdown("**Recetas similares en dataset:**")
                for r in p['recetas_similares_en_dataset'][:2]:
                    st.markdown(f"• {r['titulo']} (score: {r['score_alacena']:.2f})")
            st.caption(f"*{p['fuente']}*")

        st.divider()
        if st.button("🔄 Nueva consulta", use_container_width=True):
            for k, v in defaults.items():
                st.session_state[k] = v
            st.rerun()

    # Chat
    for i, msg in enumerate(st.session_state.messages):
        if i == 0:
            continue
        with st.chat_message(msg["role"], avatar="🌮" if msg["role"] == "assistant" else "🧑‍🍳"):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Responde, pregunta o pide algo diferente..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="🧑‍🍳"):
            st.markdown(prompt)
        with st.chat_message("assistant", avatar="🌮"):
            with st.spinner(""):
                all_msgs = [{"role": "system", "content": build_system_prompt(st.session_state.perfil_data)}] + st.session_state.messages
                resp = client.chat.completions.create(model="gpt-4o-mini", messages=all_msgs, temperature=0.8)
                reply = resp.choices[0].message.content
                st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})

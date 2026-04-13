import streamlit as st
import os
import json
import pandas as pd
import numpy as np
from openai import OpenAI

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
</style>
""", unsafe_allow_html=True)

# ── Cargar datos del EDA ──────────────────────────────────────────────────────
@st.cache_data
def load_data():
    try:
        # Intentar múltiples paths para compatibilidad con Streamlit Cloud
        base = os.path.dirname(os.path.abspath(__file__))
        paths_csv = [
            os.path.join(base, "data", "recipes_df.csv"),
            "v2/data/recipes_df.csv",
            "data/recipes_df.csv",
        ]
        paths_json = [
            os.path.join(base, "data", "top_ingredientes_alacena.json"),
            "v2/data/top_ingredientes_alacena.json",
            "data/top_ingredientes_alacena.json",
        ]
        df = None
        for path in paths_csv:
            if os.path.exists(path):
                df = pd.read_csv(path)
                break
        top_ings = []
        for path in paths_json:
            if os.path.exists(path):
                with open(path) as f:
                    top_ings = json.load(f)
                break
        return df, top_ings
    except Exception as e:
        return None, []

recipes_df, top_ingredientes = load_data()

# ── Tool del EDA ──────────────────────────────────────────────────────────────
def get_perfil_alacena(ingredientes_usuario: list) -> dict:
    if recipes_df is None or len(ingredientes_usuario) == 0:
        return {"error": "Dataset no disponible"}

    user_set = set(i.lower().strip() for i in ingredientes_usuario if i.strip())
    top_set = set(i.lower() for i in top_ingredientes)
    en_alacena = list(user_set & top_set)

    def calcular_match(ings_str):
        if not isinstance(ings_str, str): return 0
        ings = set(i.strip().lower() for i in ings_str.split(','))
        return len(ings & user_set) / max(len(user_set), 1)

    df_copy = recipes_df.copy()
    df_copy['match_score'] = df_copy['ingredientes'].apply(calcular_match)
    top_recetas = df_copy.nlargest(3, 'match_score')[
        ['titulo', 'score_alacena', 'dificultad', 'tiempo_minutos', 'match_score']
    ].to_dict('records')
    scores = df_copy[df_copy['match_score'] > 0]['score_alacena']
    score_promedio = scores.mean() if len(scores) > 0 else 0

    return {
        "ingredientes_comunes_alacena_mexicana": en_alacena,
        "pct_en_alacena_tipica": round(len(en_alacena) / max(len(user_set), 1) * 100),
        "recetas_similares_en_dataset": top_recetas,
        "score_alacena_promedio": round(score_promedio, 3) if not np.isnan(score_promedio) else 0,
        "total_recetas_analizadas": len(recipes_df),
    }

# ── Configuración ─────────────────────────────────────────────────────────────
MODOS_ENERGIA = {
    "Con energía":      {"emoji": "⚡", "tiempo": 90, "desc": "Podemos hacer algo elaborado y especial."},
    "Normal":           {"emoji": "😊", "tiempo": 45, "desc": "Algo rico sin complicarnos demasiado."},
    "Cansada":          {"emoji": "😴", "tiempo": 25, "desc": "Fácil, máximo 3 pasos, que esté bueno."},
    "Muerta de hambre": {"emoji": "🤤", "tiempo": 15, "desc": "Lo más rápido posible. Ya."},
}
MOMENTOS = {"Desayuno": "🌅", "Comida": "☀️", "Cena": "🌙", "Snack": "🍿"}

# ── Session state ─────────────────────────────────────────────────────────────
defaults = {
    "onboarding_done": False, "modo_energia": "Normal",
    "momento": "Comida", "messages": [], "ingredientes_frescos": "",
    "perfil_data": None
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── System prompt ─────────────────────────────────────────────────────────────
def build_system_prompt(perfil_data=None):
    modo = MODOS_ENERGIA[st.session_state.modo_energia]
    momento = st.session_state.momento
    energia = st.session_state.modo_energia
    tiempo = modo['tiempo']
    desc = modo['desc']
    ingredientes = st.session_state.ingredientes_frescos

    perfil_str = ""
    if perfil_data and "error" not in perfil_data:
        en_alacena = perfil_data.get("ingredientes_comunes_alacena_mexicana", [])
        pct = perfil_data.get("pct_en_alacena_tipica", 0)
        perfil_str = f"""
ANÁLISIS DE DATOS (103 recetas mexicanas analizadas):
- {pct}% de los ingredientes del usuario son típicos de cocinas mexicanas
- Ingredientes reconocidos como típicos de alacena mexicana: {', '.join(en_alacena) if en_alacena else 'ninguno identificado'}
- Score de aprovechamiento promedio: {perfil_data.get('score_alacena_promedio', 0)}
- Usa este análisis para contextualizar tus recomendaciones."""

    return f"""Eres CocinaAI, un chef mexicano experto con una habilidad especial:
con solo saber qué ingredientes tiene alguien en casa, identifica exactamente
qué platillo mexicano auténtico y delicioso puede preparar.
Tu misión es eliminar la carga mental de decidir qué cocinar.

CONTEXTO:
- Momento: {momento}
- Estado: {energia} — {desc}
- Tiempo disponible: {tiempo} minutos
- Ingredientes que tiene el usuario: {ingredientes}
{perfil_str}

REGLA MÁS IMPORTANTE — INGREDIENTES:
Los ingredientes mencionados por el usuario son la BASE de la receta.
- Puedes asumir básicos que casi todos tienen: sal, aceite, agua, ajo, cebolla.
- Si una receta mejor requiere algo adicional, PREGUNTA primero si lo tiene.
- Si dice que no tiene ese ingrediente, busca una alternativa con lo que sí tiene.
- NUNCA sugieras una receta que requiera ingredientes que el usuario no mencionó
  y no confirmó tener. Eso es frustrante e inútil.

TU FORMA DE TRABAJAR:
- Haz 1 pregunta estratégica si un ingrediente adicional desbloquearía 
  una receta mucho mejor. Considera que en cocinas mexicanas es común tener:
  chile seco (ancho, guajillo, pasilla), crema, queso fresco, limón, 
  tortillas, caldito de pollo.
- Razona sobre viabilidad real dado el tiempo y estado del usuario.
- Los condimentos (cebolla, ajo, chile, sal) son apoyo, no el platillo central.
- Las recetas deben ser RICAS: tatemarlos, un chile con profundidad, 
  hierbas frescas al final. Comparte ese secreto.
- Nunca lo más obvio. Busca algo que sorprenda y dé ganas de cocinar.
- Cuando sugieras, da pasos completos con cantidades.
- Da 2 alternativas compactas además de la receta principal.
- Siempre incluye qué hacer con lo que sobre.
- Máximo 1 pregunta por turno.

REGLAS:
- Prioriza cocina mexicana auténtica, siempre en español.
- Cálido y conversacional, como un amigo chef de confianza.
- Si no tiene algo, ajusta sin drama y busca otra opción con lo que sí tiene."""

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

    st.markdown('<div class="step-label">¿Qué estás preparando?</div>', unsafe_allow_html=True)
    momento_sel = st.radio("momento",
        options=[f"{emoji} {m}" for m, emoji in MOMENTOS.items()],
        horizontal=True, label_visibility="collapsed", key="radio_momento")
    st.session_state.momento = momento_sel.split(" ", 1)[1]

    st.markdown('<div class="step-label">¿Cómo estás ahorita?</div>', unsafe_allow_html=True)
    energia_sel = st.radio("energia",
        options=[f"{info['emoji']} {modo}" for modo, info in MODOS_ENERGIA.items()],
        horizontal=True, label_visibility="collapsed", key="radio_energia")
    st.session_state.modo_energia = energia_sel.split(" ", 1)[1]

    st.markdown('<div class="step-label">¿Qué tienes disponible?</div>', unsafe_allow_html=True)
    st.caption("No te compliques — escribe lo que veas. El chat te preguntará si necesita saber algo más.")
    ing_input = st.text_area("ing",
        placeholder="ej. pollo, jitomate, cebolla, chile poblano, crema, arroz...",
        height=80, label_visibility="collapsed")

    if st.button("¡A cocinar! →", use_container_width=True):
        if not ing_input.strip():
            st.warning("Escribe al menos un ingrediente.")
        else:
            st.session_state.ingredientes_frescos = ing_input.strip()
            st.session_state.onboarding_done = True

            user_ings = [i.strip() for i in ing_input.split(',')]
            perfil = get_perfil_alacena(user_ings)
            st.session_state.perfil_data = perfil

            momento_txt = st.session_state.momento.lower()
            energia_txt = st.session_state.modo_energia.lower()
            primer_msg = (
                f"Hola! Preparo {momento_txt}, me siento {energia_txt}. "
                f"Tengo: {ing_input.strip()}. ¿Qué me recomiendas?"
            )
            st.session_state.messages.append({"role": "user", "content": primer_msg})

            with st.spinner("Pensando en algo rico para ti..."):
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": build_system_prompt(perfil)},
                        {"role": "user", "content": primer_msg}
                    ],
                    temperature=0.5
                )
                reply = resp.choices[0].message.content
                st.session_state.messages.append({"role": "assistant", "content": reply})

            st.rerun()

else:
    with st.sidebar:
        st.markdown("### Tu sesión")
        st.markdown(f"**{MOMENTOS[st.session_state.momento]} {st.session_state.momento}**")
        st.markdown(f"**{MODOS_ENERGIA[st.session_state.modo_energia]['emoji']} {st.session_state.modo_energia}**")
        st.markdown(f"*{st.session_state.ingredientes_frescos}*")

        if st.session_state.perfil_data and "error" not in st.session_state.perfil_data:
            p = st.session_state.perfil_data
            st.divider()
            st.markdown("### 📊 Análisis de alacena")
            st.markdown(f"**{p['pct_en_alacena_tipica']}%** de tus ingredientes son típicos de cocinas mexicanas")
            if p['ingredientes_comunes_alacena_mexicana']:
                st.markdown("**Reconocidos como típicos:**")
                for ing in p['ingredientes_comunes_alacena_mexicana']:
                    st.markdown(f"✓ {ing}")
            if p['recetas_similares_en_dataset']:
                st.markdown("**Recetas similares en dataset:**")
                for r in p['recetas_similares_en_dataset'][:2]:
                    st.markdown(f"• {r['dificultad']} · {int(r['tiempo_minutos'])} min · {r['score_alacena']:.0%} aprovechamiento")
            st.caption(f"*Basado en {p['total_recetas_analizadas']} recetas mexicanas*")
        else:
            st.divider()
            st.caption("⚠️ Análisis de datos no disponible")

        st.divider()
        if st.button("🔄 Nueva consulta", use_container_width=True):
            for k, v in defaults.items():
                st.session_state[k] = v
            st.rerun()

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
                resp = client.chat.completions.create(
                    model="gpt-4o-mini", messages=all_msgs, temperature=0.5
                )
                reply = resp.choices[0].message.content
                st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})

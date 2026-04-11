import streamlit as st
import os
import json
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

# Top ingredientes del EDA
TOP_INGREDIENTES_EDA = [
    "ajo", "cebolla", "jitomate", "chile", "cilantro", "crema", "aceite",
    "sal", "pimienta", "comino", "oregano", "laurel", "epazote",
    "chile serrano", "chile ancho", "chile guajillo", "chipotle",
    "limon", "aguacate", "tomate verde", "tomatillo"
]

ALACENA_CATEGORIAS = {
    "🫘 Legumbres (frijoles, lentejas, garbanzos)": ["frijoles", "lentejas", "garbanzos"],
    "🥫 Enlatados (atun, chiles, jitomate)": ["atun", "sardinas", "chiles chipotles en lata", "jitomate en lata"],
    "🌾 Granos (arroz, pasta, harina, avena)": ["arroz", "pasta", "harina", "avena", "quinoa"],
    "🍫 Despensa dulce (cacao, mermelada, cajeta)": ["cacao", "mermelada", "cajeta", "chocolate"],
    "🥚 Basicos (huevos, tortillas, pan, leche)": ["huevos", "tortillas", "pan", "leche", "mantequilla"],
}

MODOS_ENERGIA = {
    "Con energia": {"emoji": "⚡", "tiempo": 90, "desc": "Podemos hacer algo elaborado y especial."},
    "Normal": {"emoji": "😊", "tiempo": 45, "desc": "Algo rico sin complicarnos demasiado."},
    "Cansada": {"emoji": "😴", "tiempo": 25, "desc": "Facil, maximo 3 pasos, que este bueno."},
    "Muerta de hambre": {"emoji": "🤤", "tiempo": 15, "desc": "Lo mas rapido posible. Ya."},
}

MOMENTOS = {"Desayuno": "🌅", "Comida": "☀️", "Cena": "🌙", "Snack": "🍿"}

# Session state
defaults = {"onboarding_done": False, "alacena_base": [], "modo_energia": "Normal",
            "momento": "Comida", "messages": [], "ingredientes_frescos": ""}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

def build_system_prompt():
    modo = MODOS_ENERGIA[st.session_state.modo_energia]
    alacena_str = f"\nTambien tiene en alacena: {', '.join(st.session_state.alacena_base)}." if st.session_state.alacena_base else ""
    top_eda = ", ".join(TOP_INGREDIENTES_EDA)
    return f"""Eres CocinaAI, un chef experto y calido en cocina mexicana tradicional y regional.
Tu mision es resolver la carga cognitiva de cocinar: cuando alguien llega cansada, con prisa o con hambre y no sabe que hacer con lo que tiene en casa.

CONTEXTO DEL USUARIO:
- Momento: {st.session_state.momento}
- Estado: {st.session_state.modo_energia} — {modo['desc']}
- Tiempo maximo sugerido: {modo['tiempo']} minutos
- Ingredientes frescos: {st.session_state.ingredientes_frescos}{alacena_str}

INGREDIENTES COMUNES EN COCINAS MEXICANAS (del analisis de datos del sistema):
{top_eda}
Puedes mencionarlos como opciones pero NO asumas que el usuario los tiene. Si son clave para una receta mejor, PREGUNTA.

COMO RESPONDER:
1. Sugiere 1 receta DESTACADA — la mejor para este momento y estado.
2. Da 2 alternativas compactas (nombre, tiempo, por que aplica).
3. Usa los ingredientes como PUNTO DE PARTIDA, no como restriccion estricta.
4. Si una receta mejor requiere algo clave que no menciono, pregunta UNA SOLA COSA.
5. Menciona sutilmente si la receta es balanceada cuando aplique.
6. Siempre incluye que hacer con lo que sobre.
7. Tono segun estado: con energia = entusiasta, cansada = directo y reconfortante, muerta de hambre = urgente y brevísimo.

REGLAS:
- Solo cocina mexicana autentica. Sin tex-mex ni fusion.
- Siempre en espanol.
- Calido y conversacional, como un amigo chef.
- Maximo 1 pregunta de seguimiento por turno.
- Si no tiene un ingrediente, ajusta sin drama."""

# UI
st.markdown('<div class="hero-title">CocinaAI 🌮</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Tu chef de alacena. Dime qué tienes y cómo estás — yo me encargo del resto.</div>', unsafe_allow_html=True)

if not st.session_state.onboarding_done:
    with st.container():
        st.markdown("#### Antes de empezar 🧺")
        st.markdown("*¿Qué tienes en tu alacena? Marca lo que sí tienes:*")

        alacena_sel = []
        for cat, items in ALACENA_CATEGORIAS.items():
            if st.checkbox(cat, key=f"cb_{cat}"):
                alacena_sel.extend(items)

        st.markdown('<div class="step-label">¿Qué estás preparando?</div>', unsafe_allow_html=True)
        momento_cols = st.columns(4)
        momento_sel = st.session_state.momento
        for i, (m, emoji) in enumerate(MOMENTOS.items()):
            if momento_cols[i].button(f"{emoji} {m}", key=f"m_{m}", use_container_width=True):
                momento_sel = m
                st.session_state.momento = m

        st.markdown('<div class="step-label">¿Cómo estás ahorita?</div>', unsafe_allow_html=True)
        energia_cols = st.columns(4)
        energia_sel = st.session_state.modo_energia
        for i, (modo, info) in enumerate(MODOS_ENERGIA.items()):
            if energia_cols[i].button(f"{info['emoji']} {modo}", key=f"e_{modo}", use_container_width=True):
                energia_sel = modo
                st.session_state.modo_energia = modo

        st.markdown('<div class="step-label">¿Qué tienes disponible?</div>', unsafe_allow_html=True)
        ing_input = st.text_area("ing", placeholder="ej. pollo, jitomate, cebolla, chile poblano, crema...",
                                  height=80, label_visibility="collapsed")

        if st.button("¡A cocinar! →", use_container_width=True):
            if not ing_input.strip():
                st.warning("Escribe al menos un ingrediente.")
            else:
                st.session_state.alacena_base = alacena_sel
                st.session_state.modo_energia = energia_sel
                st.session_state.momento = momento_sel
                st.session_state.ingredientes_frescos = ing_input.strip()
                st.session_state.onboarding_done = True

                momento_txt = momento_sel.lower()
                energia_txt = energia_sel.lower()
                alacena_txt = f" Tambien tengo en alacena: {', '.join(alacena_sel)}." if alacena_sel else ""
                primer_msg = f"Hola! Preparo {momento_txt}, me siento {energia_txt}. Tengo: {ing_input.strip()}.{alacena_txt} Que me recomiendas?"

                st.session_state.messages.append({"role": "user", "content": primer_msg})

                with st.spinner("Pensando en algo rico para ti..."):
                    resp = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "system", "content": build_system_prompt()},
                                   {"role": "user", "content": primer_msg}],
                        temperature=0.8
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
        if st.session_state.alacena_base:
            st.markdown(f"Alacena: {', '.join(st.session_state.alacena_base[:3])}{'...' if len(st.session_state.alacena_base) > 3 else ''}")
        st.divider()
        if st.button("🔄 Nueva consulta", use_container_width=True):
            for k in list(defaults.keys()):
                st.session_state[k] = defaults[k]
            st.rerun()

    for i, msg in enumerate(st.session_state.messages):
        if i == 0:
            continue  # Ocultamos el primer mensaje automático
        with st.chat_message(msg["role"], avatar="🌮" if msg["role"] == "assistant" else "🧑‍🍳"):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Responde, pregunta o pide algo diferente..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="🧑‍🍳"):
            st.markdown(prompt)
        with st.chat_message("assistant", avatar="🌮"):
            with st.spinner(""):
                all_msgs = [{"role": "system", "content": build_system_prompt()}] + st.session_state.messages
                resp = client.chat.completions.create(model="gpt-4o-mini", messages=all_msgs, temperature=0.8)
                reply = resp.choices[0].message.content
                st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})

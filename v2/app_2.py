import streamlit as st
import requests
import os
import json
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import List

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CocinaAI — Zero Waste",
    page_icon="🌮",
    layout="centered"
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=DM+Sans:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background-color: #FDF6EE; }
#MainMenu, header, footer { visibility: hidden; }
.hero-title { font-family: 'Playfair Display', serif; font-size: 2.8rem; font-weight: 700; color: #1C1208; line-height: 1.1; margin-bottom: 0.15rem; }
.hero-sub { font-size: 1rem; color: #7A6550; margin-bottom: 0.5rem; font-weight: 300; }
.hero-badge { display: inline-block; background: #DFF5E8; color: #1D6B3A; font-size: 0.78rem; font-weight: 500; padding: 3px 10px; border-radius: 99px; margin-bottom: 1.5rem; }
.stTextArea textarea { background-color: #FFF8F0 !important; border: 1.5px solid #D4A96A !important; border-radius: 12px !important; font-family: 'DM Sans', sans-serif !important; font-size: 0.95rem !important; color: #1C1208 !important; padding: 14px !important; }
.stTextArea textarea:focus { border-color: #B5722A !important; box-shadow: 0 0 0 3px rgba(181,114,42,0.15) !important; }
.stButton > button { background-color: #B5722A !important; color: #FFF8F0 !important; border: none !important; border-radius: 10px !important; font-family: 'DM Sans', sans-serif !important; font-weight: 500 !important; font-size: 0.95rem !important; padding: 0.6rem 2rem !important; width: 100% !important; transition: background 0.2s !important; }
.stButton > button:hover { background-color: #9A5E1F !important; }
.receta-card { background: #FFFAF4; border: 1px solid #E8D5B7; border-radius: 16px; padding: 1.5rem 1.75rem; margin-bottom: 1.25rem; }
.receta-card.top-zw { border: 2px solid #1D9E75; }
.receta-nombre { font-family: 'Playfair Display', serif; font-size: 1.5rem; font-weight: 600; color: #1C1208; margin-bottom: 0.5rem; }
.receta-resumen { font-size: 0.92rem; color: #5C4A32; line-height: 1.6; margin-bottom: 1rem; font-style: italic; }
.meta-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 1rem; }
.meta-pill { background: #F2E4CE; color: #7A4F1E; font-size: 0.78rem; font-weight: 500; padding: 4px 12px; border-radius: 99px; }
.meta-pill.verde { background: #DFF0D8; color: #2D6A1F; }
.meta-pill.rojo { background: #FAE0D5; color: #8B2E12; }
.meta-pill.azul { background: #E3F0FF; color: #1A4E8A; }
.zw-bar-wrap { background: #F0F0F0; border-radius: 99px; height: 8px; margin: 4px 0 10px; }
.zw-bar-fill { background: linear-gradient(90deg, #1D9E75, #5DCAA5); border-radius: 99px; height: 8px; }
.zw-label { font-size: 0.75rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.08em; color: #1D9E75; margin-bottom: 2px; }
.aprovechamiento-row { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.ing-match { background: #DFF5E8; color: #1D6B3A; font-size: 0.78rem; padding: 3px 10px; border-radius: 99px; }
.ing-extra { background: #FFF3DC; color: #7A4F1E; font-size: 0.78rem; padding: 3px 10px; border-radius: 99px; }
.section-label { font-size: 0.75rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.08em; color: #B5722A; margin: 1rem 0 0.4rem; }
.consejo-box { background: #FFF3DC; border-left: 3px solid #D4A96A; border-radius: 0 8px 8px 0; padding: 10px 14px; font-size: 0.88rem; color: #5C3D0E; line-height: 1.5; margin-top: 0.75rem; }
.sobra-box { background: #F0F7FF; border-left: 3px solid #378ADD; border-radius: 0 8px 8px 0; padding: 10px 14px; font-size: 0.88rem; color: #1A3A5C; line-height: 1.5; margin-top: 0.75rem; }
.sustitucion-item { font-size: 0.88rem; color: #4A3520; padding: 2px 0; }
.apto-pill { display: inline-block; background: #E8F5E9; color: #2E6B35; font-size: 0.75rem; padding: 3px 10px; border-radius: 99px; margin: 2px 3px 2px 0; }
.divider { border: none; border-top: 1px solid #E8D5B7; margin: 1rem 0; }
.empty-state { text-align: center; padding: 3rem 1rem; color: #A08060; font-size: 0.95rem; }
.empty-emoji { font-size: 3rem; margin-bottom: 0.75rem; }
.orden-label { font-size: 0.82rem; color: #7A6550; margin-bottom: 1rem; }
</style>
""", unsafe_allow_html=True)

# ── Constantes Zero Waste ─────────────────────────────────────────────────────
# Ingredientes comunes de despensa mexicana (top 50 aproximado)
DESPENSA_COMUN = {
    "garlic", "onion", "tomato", "salt", "pepper", "olive oil", "cumin",
    "chicken", "lime", "cilantro", "jalapeno", "chili", "cheese", "cream",
    "egg", "flour", "oil", "butter", "sugar", "oregano", "bay leaf",
    "beef", "pork", "rice", "beans", "corn", "avocado", "serrano",
    "chipotle", "ancho", "pasilla", "epazote", "lard", "vinegar",
    "chicken broth", "water", "milk", "sour cream", "black beans",
    "pinto beans", "white onion", "red onion", "tomatillo", "poblano"
}

# ── Pydantic ──────────────────────────────────────────────────────────────────
class RecetaInsights(BaseModel):
    nombre: str = Field(description="Nombre del platillo")
    tiempo_minutos: int = Field(description="Tiempo total en minutos")
    dificultad: str = Field(description="Facil, Media o Dificil")
    ingredientes_clave: List[str] = Field(description="Ingredientes más importantes")
    resumen: str = Field(description="Descripción breve y apetitosa en 2 oraciones")
    consejo_chef: str = Field(description="Un consejo práctico")
    sustituciones: List[str] = Field(description="2-3 sustituciones posibles")
    apto_para: List[str] = Field(description="Perfiles ideales")
    puntuacion_facilidad: int = Field(description="Facilidad del 1 al 10")
    que_hacer_con_sobras: str = Field(description="Sugerencia breve de qué hacer con los ingredientes que sobran o no se usan en esta receta")

# ── Helpers API ───────────────────────────────────────────────────────────────
def search_recipes(ingredients: str, api_key: str, number: int = 4) -> list:
    try:
        resp = requests.get(
            "https://api.spoonacular.com/recipes/complexSearch",
            params={"cuisine": "mexican", "includeIngredients": ingredients,
                    "number": number, "addRecipeInformation": True, "apiKey": api_key},
            timeout=10
        )
        return resp.json().get("results", [])
    except Exception:
        return []

def get_recipe_detail(recipe_id: int, api_key: str) -> dict:
    try:
        resp = requests.get(
            f"https://api.spoonacular.com/recipes/{recipe_id}/information",
            params={"includeNutrition": False, "apiKey": api_key},
            timeout=10
        )
        return resp.json()
    except Exception:
        return {}

def calcular_aprovechamiento(recipe: dict, user_ingredients: list) -> dict:
    """
    Calcula qué ingredientes del usuario usa la receta y cuáles no.
    Retorna porcentaje de aprovechamiento y listas de matches/extras.
    """
    recipe_ings = [i.get("name", "").lower() for i in recipe.get("extendedIngredients", [])]
    user_set = set(u.lower().strip() for u in user_ingredients)

    matches = []
    for user_ing in user_set:
        for recipe_ing in recipe_ings:
            if user_ing in recipe_ing or recipe_ing in user_ing:
                matches.append(user_ing)
                break

    pct = round(len(matches) / len(user_set) * 100) if user_set else 0
    extras = [u for u in user_set if u not in matches]

    # Score Zero Waste: combina aprovechamiento + proporción de ingredientes comunes
    recipe_ing_names = set(i.get("name", "").lower() for i in recipe.get("extendedIngredients", []))
    prop_comunes = len(recipe_ing_names & DESPENSA_COMUN) / max(len(recipe_ing_names), 1)
    pocos = 1 if len(recipe_ing_names) <= 7 else 0
    score_zw = round(0.5 * (pct / 100) + 0.3 * prop_comunes + 0.2 * pocos, 3)

    return {
        "pct_aprovechamiento": pct,
        "ingredientes_match": matches,
        "ingredientes_extra": extras,
        "score_zero_waste": score_zw
    }

def render_recipe_text(recipe: dict, user_ingredients: list) -> str:
    title = recipe.get("title", "")
    time = recipe.get("readyInMinutes", "?")
    ingredients = recipe.get("extendedIngredients", [])
    ing_text = "\n".join(f"  - {i.get('original','')}" for i in ingredients)
    steps = []
    for instr in recipe.get("analyzedInstructions", []):
        for step in instr.get("steps", []):
            steps.append(f"  {step['number']}. {step['step']}")
    steps_text = "\n".join(steps) if steps else "No disponible"
    user_str = ", ".join(user_ingredients)
    return (
        f"Receta: {title}\nTiempo: {time} minutos\n"
        f"Ingredientes del usuario disponibles: {user_str}\n\n"
        f"Ingredientes completos de la receta:\n{ing_text}\n\n"
        f"Preparacion:\n{steps_text}"
    )

def get_insights(recipe: dict, client: OpenAI, user_ingredients: list) -> RecetaInsights:
    recipe_text = render_recipe_text(recipe, user_ingredients)
    json_template = (
        '{\n'
        '  "nombre": "nombre del platillo",\n'
        '  "tiempo_minutos": 30,\n'
        '  "dificultad": "Facil",\n'
        '  "ingredientes_clave": ["ingrediente1", "ingrediente2"],\n'
        '  "resumen": "descripcion breve y apetitosa en 2 oraciones",\n'
        '  "consejo_chef": "un consejo practico para mejor resultado",\n'
        '  "sustituciones": ["sustitucion1", "sustitucion2"],\n'
        '  "apto_para": ["perfil1", "perfil2"],\n'
        '  "puntuacion_facilidad": 8,\n'
        '  "que_hacer_con_sobras": "sugerencia breve para ingredientes que no se usan"\n'
        '}'
    )
    prompt = (
        "Eres un chef experto en cocina mexicana con enfoque en Zero Waste (cero desperdicio). "
        "Analiza la receta considerando los ingredientes que el usuario tiene disponibles. "
        "Para 'que_hacer_con_sobras' sugiere brevemente cómo usar los ingredientes del usuario "
        "que NO usa esta receta.\n\n"
        "Responde EXACTAMENTE con este JSON (campos en español, nombres exactos):\n\n"
        + json_template
        + "\n\nReceta a analizar:\n"
        + recipe_text
    )
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Responde SOLO con JSON valido, sin texto adicional."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    data = json.loads(completion.choices[0].message.content)
    field_map = {
        "name": "nombre", "title": "nombre",
        "time_minutes": "tiempo_minutos", "difficulty": "dificultad",
        "key_ingredients": "ingredientes_clave", "summary": "resumen",
        "description": "resumen", "chef_tip": "consejo_chef", "tip": "consejo_chef",
        "substitutions": "sustituciones", "suitable_for": "apto_para",
        "ease_score": "puntuacion_facilidad", "leftovers": "que_hacer_con_sobras",
        "leftover_tip": "que_hacer_con_sobras", "waste_tip": "que_hacer_con_sobras"
    }
    normalized = {field_map.get(k, k): v for k, v in data.items()}
    defaults = {
        "nombre": recipe.get("title", "Receta"),
        "tiempo_minutos": recipe.get("readyInMinutes", 30),
        "dificultad": "Media",
        "ingredientes_clave": [],
        "resumen": "Una deliciosa receta mexicana.",
        "consejo_chef": "Sigue los pasos con cuidado.",
        "sustituciones": [],
        "apto_para": [],
        "puntuacion_facilidad": 5,
        "que_hacer_con_sobras": "Puedes usar los ingredientes restantes en otra preparacion."
    }
    defaults.update(normalized)
    return RecetaInsights(**defaults)

def dificultad_color(d: str) -> str:
    d_lower = d.lower()
    if "f" in d_lower and "cil" in d_lower: return "verde"
    if "dif" in d_lower: return "rojo"
    return ""

# ── UI ────────────────────────────────────────────────────────────────────────
st.markdown('<div class="hero-title">CocinaAI 🌮</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Recetas mexicanas con lo que tienes en casa.</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-badge">♻ Enfoque Zero Waste — aprovecha tu despensa al máximo</div>', unsafe_allow_html=True)

SPOONACULAR_API = st.secrets.get("SPOONACULAR_API", os.getenv("SPOONACULAR_API", ""))
OPENAI_API_KEY  = st.secrets.get("OPENAI_API_KEY",  os.getenv("OPENAI_API_KEY", ""))

if not SPOONACULAR_API or not OPENAI_API_KEY:
    st.error("Faltan las API keys. Agrégalas en Secrets de Streamlit Cloud.")
    st.stop()

client = OpenAI(api_key=OPENAI_API_KEY)

ingredientes_raw = st.text_area(
    "ingredientes",
    placeholder="ej. pollo, chile poblano, crema, cebolla, ajo...",
    height=90,
    label_visibility="collapsed"
)

buscar = st.button("Buscar recetas →")

if buscar and ingredientes_raw.strip():
    user_ingredients = [i.strip() for i in ingredientes_raw.split(",") if i.strip()]

    with st.spinner("Buscando recetas mexicanas..."):
        resultados = search_recipes(ingredientes_raw, SPOONACULAR_API)

    if not resultados:
        st.markdown("""
        <div class="empty-state">
            <div class="empty-emoji">🫙</div>
            No encontré recetas con esos ingredientes.<br>
            Intenta con ingredientes más comunes: pollo, frijoles, chile, jitomate, cebolla.
        </div>
        """, unsafe_allow_html=True)
    else:
        # Calculamos aprovechamiento para ordenar por Zero Waste
        recetas_con_zw = []
        for r in resultados:
            detail = get_recipe_detail(r["id"], SPOONACULAR_API)
            if detail:
                zw_data = calcular_aprovechamiento(detail, user_ingredients)
                recetas_con_zw.append((r, detail, zw_data))

        # Ordenamos por score Zero Waste descendente
        recetas_con_zw.sort(key=lambda x: x[2]["score_zero_waste"], reverse=True)

        n = len(recetas_con_zw)
        st.markdown(
            f'<div class="orden-label">{n} recetas encontradas — ordenadas por mayor aprovechamiento de tus ingredientes</div>',
            unsafe_allow_html=True
        )

        for idx, (r, detail, zw_data) in enumerate(recetas_con_zw):
            with st.spinner(f"Analizando {r.get('title', 'receta')}..."):
                insights = get_insights(detail, client, user_ingredients)

            pct = zw_data["pct_aprovechamiento"]
            score_zw = zw_data["score_zero_waste"]
            matches = zw_data["ingredientes_match"]
            extras = zw_data["ingredientes_extra"]
            is_top = idx == 0

            dc = dificultad_color(insights.dificultad)
            card_class = "receta-card top-zw" if is_top else "receta-card"
            top_badge = '<span class="meta-pill verde">♻ Mejor aprovechamiento</span>' if is_top else ""

            # Ingredientes match / extra
            match_html = "".join(f'<span class="ing-match">✓ {m}</span>' for m in matches)
            extra_html  = "".join(f'<span class="ing-extra">+ {e}</span>' for e in extras[:3])

            # Barra Zero Waste
            zw_pct = int(score_zw * 100)
            zw_bar = (
                f'<div class="zw-label">Score Zero Waste — {zw_pct}%</div>'
                f'<div class="zw-bar-wrap"><div class="zw-bar-fill" style="width:{zw_pct}%"></div></div>'
            )

            ing_html  = "".join(f'<div class="ingrediente-item">• {i}</div>' for i in insights.ingredientes_clave)
            sust_html = "".join(f'<div class="sustitucion-item">↔ {s}</div>' for s in insights.sustituciones)
            apto_html = "".join(f'<span class="apto-pill">{a}</span>' for a in insights.apto_para)

            st.markdown(f"""
            <div class="{card_class}">
                <div class="receta-nombre">{insights.nombre}</div>
                <div class="receta-resumen">{insights.resumen}</div>
                <div class="meta-row">
                    {top_badge}
                    <span class="meta-pill">⏱ {insights.tiempo_minutos} min</span>
                    <span class="meta-pill {dc}">{'★' if dc=='verde' else ('⚠' if dc=='rojo' else '◆')} {insights.dificultad}</span>
                    <span class="meta-pill">Facilidad {insights.puntuacion_facilidad}/10</span>
                    <span class="meta-pill azul">Usas {pct}% de tus ingredientes</span>
                </div>
                {zw_bar}
                <div class="section-label">Tus ingredientes que usa esta receta</div>
                <div class="aprovechamiento-row">{match_html}{extra_html}</div>
                <div class="section-label">Ingredientes clave</div>
                {ing_html}
                <div class="consejo-box">💡 {insights.consejo_chef}</div>
                <div class="sobra-box">♻ <strong>¿Qué hago con lo que sobra?</strong> {insights.que_hacer_con_sobras}</div>
                <hr class="divider">
                <div class="section-label">Sustituciones</div>
                {sust_html}
                <div class="section-label">Apto para</div>
                {apto_html}
            </div>
            """, unsafe_allow_html=True)

elif buscar and not ingredientes_raw.strip():
    st.warning("Escribe al menos un ingrediente para buscar recetas.")
else:
    st.markdown("""
    <div class="empty-state">
        <div class="empty-emoji">🧅</div>
        Escribe los ingredientes que tienes disponibles<br>y te sugiero qué cocinar hoy.
    </div>
    """, unsafe_allow_html=True)

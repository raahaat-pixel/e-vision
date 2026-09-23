import json
import hashlib
from datetime import datetime
from io import BytesIO

import streamlit as st
from PIL import Image, ImageOps
from google import genai
from google.genai import types


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="Анализатор состава продуктов E-vision",
    page_icon="🧪",
    layout="wide",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1400px;
        padding-top: 1.8rem;
        padding-bottom: 3rem;
    }

    .main-title {
        font-size: 38px;
        font-weight: 800;
        letter-spacing: -1px;
        margin-bottom: 4px;
    }

    .subtitle {
        font-size: 16px;
        opacity: .65;
        margin-bottom: 28px;
    }

    .score-number {
        font-size: 58px;
        font-weight: 800;
        line-height: 1;
        margin: 8px 0 0;
    }

    .verdict-title {
        font-size: 19px;
        font-weight: 750;
        line-height: 1.4;
    }

    .scale {
        position: relative;
        width: 100%;
        height: 15px;
        margin-top: 25px;
        border-radius: 999px;
        background: linear-gradient(
            90deg,
            #ef4444 0%,
            #f97316 25%,
            #facc15 50%,
            #a3e635 75%,
            #22c55e 100%
        );
    }

    .scale-marker {
        position: absolute;
        left: var(--score);
        top: 50%;
        width: 5px;
        height: 29px;
        transform: translate(-50%, -50%);
        background: white;
        border-radius: 5px;
        box-shadow: 0 1px 5px rgba(0,0,0,.4);
    }

    .scale-labels {
        display: flex;
        justify-content: space-between;
        margin-top: 8px;
        font-size: 11px;
        opacity: .55;
    }

    .scale-description {
        margin-top: 18px;
        font-size: 11px;
        line-height: 1.55;
        opacity: .58;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# GEMINI
# ============================================================

MODEL_NAME = "gemini-3.5-flash-lite"


def gemini_client():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])


def gemini_text_request(prompt):
    client = gemini_client()

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )

    return response.text or ""


def gemini_image_request(image_bytes, mime_type, prompt):
    client = gemini_client()

    image_part = types.Part.from_bytes(
        data=image_bytes,
        mime_type=mime_type,
    )

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[image_part, prompt],
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )

    return response.text or ""


# ============================================================
# ANALYSIS PROMPT
# ============================================================

ANALYSIS_RULES = """
Ты — интеллектуальный анализатор состава потребительских продуктов
E-vision.

Твоя задача — анализировать состав продукта информативно, аккуратно
и без выдумывания данных.

ВАЖНЫЕ ПРАВИЛА:

1. Анализируй только информацию, которую реально получил.
2. Никогда не придумывай ингредиенты, концентрации, проценты, свойства
   или информацию, которой нет во входных данных.
3. Учитывай назначение продукта и контекст его категории.
4. Не считай сложное химическое название автоматически вредным.
5. Не считай синтетический компонент автоматически плохим.
6. Учитывай функцию каждого компонента.
7. Если порядок ингредиентов имеет значение для категории, учитывай его.
8. Если состав неполный или часть фотографии нечитаема,
   composition_complete должен быть false.
9. При неполной информации снижай confidence.
10. Не ставь медицинские диагнозы.
11. Не обещай лечение.
12. Не утверждай абсолютную безопасность.
13. Не утверждай гарантированный вред.
14. Для фармацевтических и медицинских продуктов давай только
    информационную оценку состава и не давай назначений по лечению.
15. Для аллергенов говори только о потенциально значимых компонентах.
    Не утверждай, что у человека обязательно будет аллергическая реакция.
16. Не используй red только потому, что название вещества выглядит
    «химическим».
17. Объяснения должны быть понятными обычному пользователю.

КАТЕГОРИИ:

- Еда
- Напитки
- Косметика
- Средства личной гигиены
- Бытовая химия
- Чистящие средства
- Товары для животных
- Фармацевтические / медицинские продукты
- Другое

После категории обязательно указывай конкретный тип продукта.
Например:
Категория: Косметика
Тип: Очищающая пенка для лица

Категория: Еда
Тип: Шоколадный батончик

Категория: Напитки
Тип: Газированный напиток

Категория: Бытовая химия
Тип: Средство для мытья посуды

Не используй название категории как product_type.

ОЦЕНКА ПО КАТЕГОРИЯМ:

Для еды учитывай:
- добавленные сахара;
- соль;
- насыщенные жиры;
- белок;
- клетчатку;
- степень переработки;
- характер добавок.

Для напитков учитывай:
- сахар;
- подсластители;
- кофеин;
- кислотность;
- основные компоненты.

Для косметики учитывай:
- ПАВ;
- увлажнители;
- кондиционирующие компоненты;
- консерванты;
- отдушки;
- потенциально раздражающие компоненты;
- функциональность формулы.

Для средств личной гигиены учитывай:
- очищающие компоненты;
- ПАВ;
- увлажняющие и кондиционирующие компоненты;
- консерванты;
- отдушки;
- потенциально раздражающие компоненты;
- назначение средства.

Для бытовой химии и чистящих средств учитывай:
- ПАВ;
- растворители;
- отдушки;
- консерванты;
- потенциально раздражающие компоненты;
- назначение продукта.

Для товаров для животных учитывай:
- основные питательные компоненты;
- наполнители;
- консерванты;
- соответствие назначению.

ИНДЕКС СОСТАВА:

0–39 — требуется осторожность
40–69 — средний
70–84 — хороший
85–100 — очень благоприятный

Индекс является информационной оценкой благоприятности состава
с учётом назначения продукта. Это НЕ показатель абсолютной безопасности
и НЕ медицинский показатель.

VERDICT:

green — в целом благоприятный состав
orange — есть особенности, требующие внимания
red — есть существенные основания для осторожности

СТАТУС ИНГРЕДИЕНТА:

green — обычный функциональный компонент
orange — может требовать внимания в зависимости от продукта
и индивидуальной переносимости
red — существенные основания для осторожности

Не ставь red только из-за сложного названия вещества.

Если компонент не требует отдельного внимания, обязательно возвращай `attention_reason: null`, а не строку `None`, `null`, `нет` или пустое текстовое значение.

ALLERGY_ALERTS:

Выделяй потенциально значимые аллергены или компоненты,
которые могут иметь значение при индивидуальной чувствительности.
Не утверждай наличие аллергии у конкретного человека.

ФОРМАТ:

Верни только валидный JSON со следующими полями:

{
  "score": 0,
  "verdict": "green",
  "verdict_text": "Краткий вывод",
  "category": "Косметика",
  "product_type": "Конкретный тип продукта",
  "confidence": "high",
  "composition_complete": true,
  "composition_text": "Распознанный или предоставленный состав",
  "summary": "Понятное подробное описание состава",
  "ingredients": [
    {
      "name": "Название ингредиента",
      "type": "Назначение",
      "status": "green",
      "explanation": "Что делает компонент и зачем он нужен",
      "attention_reason": null
    }
  ],
  "benefits": [
    "Положительная сторона"
  ],
  "risks": [
    "Что требует внимания"
  ],
  "allergy_alerts": [
    {
      "name": "Компонент",
      "reason": "Почему он может быть значим при индивидуальной чувствительности",
      "level": "attention"
    }
  ],
  "allergy_note": "Общая осторожная заметка",
  "recommendation": "Итоговая рекомендация"
}

Ограничения JSON:
- score — только целое число от 0 до 100;
- verdict — только green, orange или red;
- confidence — только high, medium или low;
- status — только green, orange или red;
- allergy level — high, attention или low;
- не добавляй Markdown;
- не добавляй комментарии вне JSON;
- не добавляй выдуманные ингредиенты.
"""


# ============================================================
# HELPERS
# ============================================================

def clean_json(text):
    text = (text or "").strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    return text


def as_list(value):
    return value if isinstance(value, list) else []


def safe_score(value):
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 50


def verdict_icon(verdict):
    return {
        "green": "🟢",
        "orange": "🟠",
        "red": "🔴",
    }.get(str(verdict).lower(), "🟠")


def confidence_label(value):
    return {
        "high": "Высокая",
        "medium": "Средняя",
        "low": "Низкая",
    }.get(str(value).lower(), "Средняя")


def normalize_result(data):
    if not isinstance(data, dict):
        raise ValueError("Gemini вернул неправильный формат JSON.")

    result = dict(data)

    result["score"] = safe_score(result.get("score"))
    result["verdict"] = str(result.get("verdict", "orange")).lower()

    if result["verdict"] not in {"green", "orange", "red"}:
        result["verdict"] = "orange"

    result["confidence"] = str(
        result.get("confidence", "medium")
    ).lower()

    if result["confidence"] not in {"high", "medium", "low"}:
        result["confidence"] = "medium"

    result["ingredients"] = as_list(result.get("ingredients", []))
    result["benefits"] = as_list(result.get("benefits", []))
    result["risks"] = as_list(result.get("risks", []))
    result["allergy_alerts"] = as_list(
        result.get("allergy_alerts", [])
    )

    result["composition_complete"] = bool(
        result.get("composition_complete", True)
    )

    return result


# ============================================================
# HISTORY
# ============================================================

HISTORY_FILE = "history.json"


def load_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            history = json.load(file)

        return history if isinstance(history, list) else []

    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(
            history,
            file,
            ensure_ascii=False,
            indent=2,
        )


def add_to_history(product_text, result):
    history = load_history()

    item = {
        "id": hashlib.md5(
            f"{product_text}|{datetime.now().isoformat()}".encode("utf-8")
        ).hexdigest(),
        "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "text": product_text,
        "result": result,
    }

    history.insert(0, item)
    save_history(history[:50])


def delete_from_history(item_id):
    history = load_history()

    history = [
        item
        for item in history
        if item.get("id") != item_id
    ]

    save_history(history)


# ============================================================
# TEXT ANALYSIS
# ============================================================

def analyze_text_product(text):
    prompt = f"""
{ANALYSIS_RULES}

ИСТОЧНИК ДАННЫХ: ТЕКСТ.

Проанализируй следующий предоставленный пользователем состав:

--- НАЧАЛО СОСТАВА ---
{text}
--- КОНЕЦ СОСТАВА ---

Не добавляй сведения, которых нет в составе.
Если состав выглядит неполным, укажи composition_complete=false.

Верни только JSON.
"""

    answer = gemini_text_request(prompt)
    data = json.loads(clean_json(answer))
    return normalize_result(data)


# ============================================================
# PHOTO ANALYSIS — GEMINI VISION
# ============================================================

def analyze_photo_product(image_bytes, mime_type):
    prompt = f"""
{ANALYSIS_RULES}

ИСТОЧНИК ДАННЫХ: ФОТОГРАФИЯ ЭТИКЕТКИ.

Сначала внимательно прочитай текст на фотографии.
Затем используй только действительно читаемую информацию
с фотографии для анализа.

КРИТИЧЕСКИ ВАЖНО:

1. Не придумывай отсутствующие ингредиенты.
2. Не восстанавливай нечитаемые слова по догадке.
3. Если часть состава размыта, закрыта, слишком мелкая
   или обрезана, отметь это.
4. composition_complete=false, если состав невозможно
   прочитать полностью или уверенно определить.
5. composition_text должен содержать только текст состава,
   который реально удалось прочитать с фотографии.
6. Сохраняй порядок ингредиентов.
7. Не подменяй нечитаемый текст похожим веществом.
8. Если на фотографии видна дополнительная информация,
   используй её только если она действительно читаема.
9. Анализируй именно тот продукт, который виден на фото.

Верни только JSON.
"""

    answer = gemini_image_request(
        image_bytes,
        mime_type,
        prompt,
    )

    data = json.loads(clean_json(answer))
    return normalize_result(data)


# ============================================================
# RENDER HISTORY RESULT
# ============================================================

def render_analysis_result(
    result,
    source_text,
    saved_date=None,
    show_close=False,
):
    score = safe_score(result.get("score"))

    verdict = str(
        result.get("verdict", "orange")
    ).lower()

    if verdict not in {"green", "orange", "red"}:
        verdict = "orange"

    icon = verdict_icon(verdict)

    category = str(
        result.get("category", "Не определено")
    )

    product_type = str(
        result.get("product_type", "Не определено")
    )

    if product_type.strip().lower() == category.strip().lower():
        product_type = "Не удалось точно определить"

    confidence = confidence_label(
        result.get("confidence", "medium")
    )

    st.divider()
    st.subheader("📊 Результат анализа")

    if saved_date:
        st.caption(f"Дата анализа: {saved_date}")

    score_col, verdict_col, scale_col = st.columns(
        [1, 1.7, 1.25],
        gap="medium",
    )

    with score_col:
        with st.container(border=True):
            st.caption("ИНДЕКС СОСТАВА")

            st.markdown(
                f"""
                <div class="score-number">{score}</div>
                """,
                unsafe_allow_html=True,
            )

            st.caption("/100")

            st.markdown(
                f"**Категория:** {category}"
            )

            st.markdown(
                f"**Тип продукта:** {product_type}"
            )

    with verdict_col:
        with st.container(border=True):
            verdict_text = str(
                result.get(
                    "verdict_text",
                    "Состав требует внимания",
                )
            )

            st.markdown(
                f"""
                <div class="verdict-title">
                    {icon} {verdict_text}
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.write(
                result.get(
                    "summary",
                    "Описание отсутствует.",
                )
            )

            st.caption(
                f"Уверенность анализа: {confidence}"
            )

    with scale_col:
        with st.container(border=True):
            st.markdown("**Индекс состава**")

            scale_html = f"""
            <div class="scale" style="--score:{score}%;">
                <div class="scale-marker"></div>
            </div>

            <div class="scale-labels">
                <span>0</span>
                <span>25</span>
                <span>50</span>
                <span>75</span>
                <span>100</span>
            </div>

            <div class="scale-description">
                0–39 — требуется осторожность<br>
                40–69 — средний<br>
                70–84 — хороший<br>
                85–100 — очень благоприятный
            </div>
            """

            st.markdown(
                scale_html,
                unsafe_allow_html=True,
            )

    if not result.get("composition_complete", True):
        st.warning(
            "⚠️ Состав может быть неполным или часть информации "
            "на фотографии/в исходных данных могла быть нечитаемой. "
            "Индекс и вывод могут быть менее точными."
        )

    composition_text = str(
        result.get("composition_text", "")
    ).strip()

    if composition_text:
        with st.expander("📄 Состав, использованный для анализа"):
            st.code(
                composition_text,
                language=None,
            )

    # ========================================================
    # INGREDIENTS
    # ========================================================

    st.subheader("🧬 Разбор компонентов")

    ingredients = as_list(
        result.get("ingredients", [])
    )

    if ingredients:
        cols = st.columns(
            4,
            gap="small",
        )

        for i, ingredient in enumerate(ingredients):
            if not isinstance(ingredient, dict):
                continue

            name = str(
                ingredient.get(
                    "name",
                    "Ингредиент",
                )
            )

            ingredient_type = str(
                ingredient.get(
                    "type",
                    "Назначение не указано",
                )
            )

            status = str(
                ingredient.get(
                    "status",
                    "orange",
                )
            ).lower()

            icon = {
                "green": "🟢",
                "orange": "🟠",
                "red": "🔴",
            }.get(status, "🟠")

            with cols[i % 4]:
                with st.container(border=True):
                    st.markdown(
                        f"**{icon} {name}**"
                    )

                    st.caption(
                        ingredient_type
                    )

                    explanation = str(
                        ingredient.get(
                            "explanation",
                            "",
                        )
                    ).strip()

                    if explanation:
                        st.write(explanation)

                    raw_attention_reason = ingredient.get(
                        "attention_reason"
                    )

                    attention_reason = (
                        str(raw_attention_reason).strip()
                        if raw_attention_reason is not None
                        else ""
                    )

                    # Не показываем технические значения, которые
                    # Gemini может вернуть вместо отсутствия предупреждения.
                    ignored_attention_values = {
                        "",
                        "none",
                        "null",
                        "нет",
                        "не выявлено",
                    }

                    if attention_reason.lower() not in ignored_attention_values:
                        st.warning(
                            f"⚠️ {attention_reason}"
                        )

    else:
        st.info(
            "Подробный разбор компонентов не получен."
        )

    # ========================================================
    # ALLERGY ALERTS
    # ========================================================

    allergy_alerts = as_list(
        result.get("allergy_alerts", [])
    )

    allergy_note = str(
        result.get("allergy_note", "")
    ).strip()

    st.subheader(
        "⚠️ Аллергены и чувствительность"
    )

    if allergy_alerts:
        for alert in allergy_alerts:
            if not isinstance(alert, dict):
                continue

            alert_name = str(
                alert.get(
                    "name",
                    "Компонент",
                )
            )

            alert_reason = str(
                alert.get(
                    "reason",
                    "Может требовать внимания "
                    "при индивидуальной чувствительности.",
                )
            )

            alert_level = str(
                alert.get(
                    "level",
                    "attention",
                )
            ).lower()

            if alert_level == "high":
                alert_icon = "🔴"
                alert_title = "Требует особого внимания"
            elif alert_level == "low":
                alert_icon = "🟡"
                alert_title = "Невысокий уровень внимания"
            else:
                alert_icon = "🟠"
                alert_title = "Требует внимания"

            with st.container(border=True):
                st.markdown(
                    f"### {alert_icon} {alert_name}"
                )

                st.caption(alert_title)
                st.write(alert_reason)

    else:
        st.success(
            "✅ По предоставленному составу явных компонентов, "
            "требующих отдельного внимания с точки зрения "
            "аллергенности, не обнаружено."
        )

    if allergy_note:
        st.caption(
            f"ℹ️ {allergy_note}"
        )

    # ========================================================
    # FINAL INFORMATION
    # ========================================================

    st.subheader("📋 Итог")

    benefits_col, risks_col, recommendation_col = st.columns(
        3,
        gap="medium",
    )

    benefits = as_list(
        result.get("benefits", [])
    )

    risks = as_list(
        result.get("risks", [])
    )

    with benefits_col:
        with st.container(border=True):
            st.markdown(
                "### ✅ Положительные стороны"
            )

            if benefits:
                for item in benefits:
                    st.markdown(f"• {item}")
            else:
                st.caption(
                    "Существенных положительных "
                    "сторон не выделено."
                )

    with risks_col:
        with st.container(border=True):
            st.markdown(
                "### ⚠️ Что требует внимания"
            )

            if risks:
                for item in risks:
                    st.markdown(f"• {item}")
            else:
                st.caption(
                    "Существенных замечаний не выделено."
                )

    with recommendation_col:
        with st.container(border=True):
            st.markdown(
                "### 💡 Рекомендация"
            )

            st.write(
                result.get(
                    "recommendation",
                    "Рекомендация отсутствует.",
                )
            )

    st.divider()

    st.caption(
        "ℹ️ Индекс состава является информационной оценкой "
        "благоприятности состава с учётом назначения продукта. "
        "Он не гарантирует абсолютную безопасность и не является "
        "медицинской рекомендацией."
    )

    if show_close:
        if st.button("✖️ Закрыть сохранённый анализ"):
            st.session_state.pop(
                "selected_history",
                None,
            )
            st.rerun()


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🧪 Анализатор состава продуктов E-vision</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">'
    "Проверьте состав продукта и получите понятный "
    "анализ с рекомендациями."
    "</div>",
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR — HISTORY
# ============================================================

with st.sidebar:
    st.header("📚 История анализов")

    history = load_history()

    if not history:
        st.caption("Здесь появятся ваши анализы.")
    else:
        st.caption(
            f"Сохранено анализов: {len(history)}"
        )

        if st.button(
            "🗑️ Очистить всю историю",
            use_container_width=True,
        ):
            save_history([])
            st.session_state.pop(
                "selected_history",
                None,
            )
            st.rerun()

        st.divider()

        for item in history:
            saved_result = item.get(
                "result",
                {},
            )

            score = safe_score(
                saved_result.get("score")
            )

            verdict = str(
                saved_result.get(
                    "verdict",
                    "orange",
                )
            ).lower()

            icon = verdict_icon(verdict)

            product_type = saved_result.get(
                "product_type",
                "Неизвестный продукт",
            )

            category = saved_result.get(
                "category",
                "Другое",
            )

            st.markdown(
                f"**{icon} {product_type}**"
            )

            st.caption(
                f"{category} · {score}/100"
            )

            st.caption(
                item.get("date", "")
            )

            col_open, col_delete = st.columns(
                [3, 1]
            )

            with col_open:
                if st.button(
                    "Открыть",
                    key=f"open_{item['id']}",
                    use_container_width=True,
                ):
                    st.session_state.selected_history = item
                    st.rerun()

            with col_delete:
                if st.button(
                    "🗑️",
                    key=f"delete_{item['id']}",
                    use_container_width=True,
                ):
                    delete_from_history(
                        item["id"]
                    )

                    if (
                        st.session_state.get(
                            "selected_history",
                            {},
                        ).get("id")
                        == item["id"]
                    ):
                        st.session_state.pop(
                            "selected_history",
                            None,
                        )

                    st.rerun()

            st.divider()


# ============================================================
# SELECTED HISTORY ANALYSIS
# ============================================================

selected_history = st.session_state.get(
    "selected_history"
)

if selected_history:
    saved_result = selected_history.get(
        "result",
        {},
    )

    st.subheader("📚 Сохранённый анализ")

    render_analysis_result(
        saved_result,
        selected_history.get("text", ""),
        saved_date=selected_history.get("date", ""),
        show_close=True,
    )


# ============================================================
# INPUT
# ============================================================

input_col, info_col = st.columns(
    [1, 1],
    gap="large",
)


# ============================================================
# INPUT COLUMN
# ============================================================

with input_col:
    st.subheader("📝 Данные продукта")

    method = st.radio(
        "Способ ввода",
        [
            "✍️ Ввести вручную",
            "📷 Загрузить фото",
        ],
        horizontal=True,
        label_visibility="collapsed",
    )

    product_text = ""
    uploaded_image_bytes = None
    uploaded_mime_type = None

    # --------------------------------------------------------
    # MANUAL INPUT
    # --------------------------------------------------------

    if method == "✍️ Ввести вручную":
        product_text = st.text_area(
            "Состав",
            placeholder=(
                "Введите состав продукта...\n\n"
                "Например: вода, сахар, какао-порошок..."
            ),
            height=220,
        )

    # --------------------------------------------------------
    # PHOTO INPUT
    # --------------------------------------------------------

    else:
        uploaded = st.file_uploader(
            "Фотография состава",
            type=[
                "jpg",
                "jpeg",
                "png",
                "webp",
            ],
            help=(
                "Лучше фотографировать этикетку прямо, "
                "близко и при хорошем освещении."
            ),
        )

        if uploaded:
            image_bytes = uploaded.getvalue()

            image_hash = hashlib.md5(
                image_bytes
            ).hexdigest()

            try:
                image = ImageOps.exif_transpose(
                    Image.open(
                        BytesIO(image_bytes)
                    )
                ).convert("RGB")

                st.image(
                    image,
                    caption="Загруженная фотография",
                    use_container_width=True,
                )

                uploaded_image_bytes = image_bytes

                uploaded_mime_type = (
                    uploaded.type
                    or "image/jpeg"
                )

                st.success(
                    "✅ Фото готово. Gemini будет читать "
                    "состав непосредственно с изображения."
                )

                # Храним хеш, чтобы при rerun не запускать
                # анализ автоматически.
                st.session_state.image_hash = image_hash

            except Exception as error:
                st.error(
                    f"Не удалось открыть изображение: {error}"
                )

    # --------------------------------------------------------
    # ANALYZE BUTTON
    # --------------------------------------------------------

    analyze = st.button(
        "🔍 Анализировать состав",
        type="primary",
        use_container_width=True,
    )


# ============================================================
# HOW IT WORKS
# ============================================================

with info_col:
    st.subheader("⚙️ Как работает анализ")

    if method == "📷 Загрузить фото":
        steps = [
            (
                "1️⃣",
                "Получаем фотографию",
                "Вы загружаете фото этикетки продукта.",
            ),
            (
                "2️⃣",
                "Читаем изображение",
                "Gemini Vision непосредственно читает текст на фотографии.",
            ),
            (
                "3️⃣",
                "Проверяем читаемость",
                "ИИ отмечает нечитаемые или отсутствующие участки.",
            ),
            (
                "4️⃣",
                "Определяем продукт",
                "Определяются категория и конкретный тип.",
            ),
            (
                "5️⃣",
                "Анализируем состав",
                "Компоненты оцениваются с учётом назначения продукта.",
            ),
        ]
    else:
        steps = [
            (
                "1️⃣",
                "Получаем состав",
                "Вы вводите состав продукта вручную.",
            ),
            (
                "2️⃣",
                "Определяем продукт",
                "Определяются категория и конкретный тип.",
            ),
            (
                "3️⃣",
                "Анализируем состав",
                "Компоненты оцениваются с учётом назначения продукта.",
            ),
            (
                "4️⃣",
                "Ищем особенности",
                "ИИ выделяет потенциально важные компоненты.",
            ),
            (
                "5️⃣",
                "Формируем вывод",
                "Вы получаете индекс, объяснение и рекомендации.",
            ),
        ]

    with st.container(border=True):
        for icon, title, description in steps:
            st.markdown(
                f"**{icon}  {title}**"
            )

            st.caption(description)


# ============================================================
# ANALYSIS
# ============================================================

if analyze:
    # --------------------------------------------------------
    # PHOTO
    # --------------------------------------------------------

    if method == "📷 Загрузить фото":
        if not uploaded_image_bytes:
            st.warning(
                "⚠️ Сначала загрузите фотографию состава."
            )
            st.stop()

        with st.spinner(
            "🤖 Gemini читает фотографию и анализирует состав..."
        ):
            try:
                result = analyze_photo_product(
                    uploaded_image_bytes,
                    uploaded_mime_type,
                )

            except Exception as error:
                st.error(
                    f"Ошибка анализа фотографии: {error}"
                )
                st.stop()

        composition_text = str(
            result.get(
                "composition_text",
                "",
            )
        ).strip()

        history_text = (
            composition_text
            if composition_text
            else "[Анализ выполнен непосредственно по фотографии]"
        )

    # --------------------------------------------------------
    # MANUAL TEXT
    # --------------------------------------------------------

    else:
        if not product_text.strip():
            st.warning(
                "⚠️ Введите состав продукта."
            )
            st.stop()

        with st.spinner(
            "🤖 Анализируем состав..."
        ):
            try:
                result = analyze_text_product(
                    product_text
                )

            except Exception as error:
                st.error(
                    f"Ошибка анализа Gemini: {error}"
                )
                st.stop()

        history_text = product_text

    # --------------------------------------------------------
    # SAVE + DISPLAY
    # --------------------------------------------------------

    add_to_history(
        history_text,
        result,
    )

    render_analysis_result(
        result,
        history_text,
    )

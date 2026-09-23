import json
import hashlib
from datetime import datetime
from io import BytesIO

import streamlit as st
import pytesseract
from PIL import Image, ImageEnhance, ImageOps
from google import genai


# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="Анализатор состава продуктов E-vision",
    page_icon="🧪",
    layout="wide"
)


# ============================================================
# CSS
# ============================================================

st.markdown("""
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
""", unsafe_allow_html=True)


# ============================================================
# GEMINI
# ============================================================

def gemini_request(prompt):
    """
    Создаём новый клиент для каждого запроса.
    Это предотвращает ошибку:
    'Cannot send a request, as the client has been closed.'
    """

    client = genai.Client(
        api_key=st.secrets["GEMINI_API_KEY"]
    )

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt
    )

    return response.text or ""


# ============================================================
# HELPERS
# ============================================================

def clean_json(text):
    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "")
        text = text.replace("```JSON", "")
        text = text.replace("```", "")

    return text.strip()


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
        "red": "🔴"
    }.get(verdict, "🟠")


def confidence_label(value):
    return {
        "high": "Высокая",
        "medium": "Средняя",
        "low": "Низкая"
    }.get(str(value).lower(), "Средняя")


# ============================================================
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
        json.dump(history, file, ensure_ascii=False, indent=2)


def add_to_history(product_text, result):
    history = load_history()

    item = {
        "id": hashlib.md5(
            f"{product_text}|{datetime.now().isoformat()}".encode("utf-8")
        ).hexdigest(),
        "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "text": product_text,
        "result": result
    }

    history.insert(0, item)
    save_history(history[:50])


def delete_from_history(item_id):
    history = load_history()
    history = [
        item for item in history
        if item.get("id") != item_id
    ]
    save_history(history)


# ============================================================
# OCR — IMAGE PREPROCESSING
# ============================================================

def prepare_ocr_variants(image):
    """
    Создаём несколько вариантов изображения,
    чтобы Tesseract имел больше шансов распознать мелкий текст.
    """

    # Увеличиваем изображение
    scale = 3

    image = image.resize(
        (
            image.width * scale,
            image.height * scale
        ),
        Image.Resampling.LANCZOS
    )

    gray = ImageOps.grayscale(image)

    variants = []

    # Вариант 1 — обычный контраст
    contrast = ImageEnhance.Contrast(gray).enhance(2.5)
    variants.append(contrast)

    # Вариант 2 — автоматический контраст
    auto = ImageOps.autocontrast(gray)
    variants.append(auto)

    # Вариант 3 — сильный контраст
    strong = ImageEnhance.Contrast(gray).enhance(3.5)
    variants.append(strong)

    # Вариант 4 — чёрно-белый
    bw = gray.point(
        lambda pixel: 0 if pixel < 170 else 255
    )
    variants.append(bw)

    return variants


# ============================================================
# OCR
# ============================================================

def ocr_image(image):
    """
    Распознаёт текст несколькими вариантами обработки
    и несколькими режимами Tesseract.
    """

    variants = prepare_ocr_variants(image)

    configs = [
        "--psm 6",
        "--psm 11",
        "--psm 3"
    ]

    results = []

    for variant in variants:

        for config in configs:

            try:
                text = pytesseract.image_to_string(
                    variant,
                    lang="rus+eng",
                    config=config
                ).strip()

            except Exception:
                continue

            if not text:
                continue

            # Убираем слишком короткий мусор
            if len(text) < 15:
                continue

            # Считаем полезность результата
            lines = [
                line.strip()
                for line in text.splitlines()
                if line.strip()
            ]

            words = text.split()

            # Больше строк + больше слов = обычно
            # более информативный OCR
            score = (
                len(lines) * 3
                + len(words)
                + min(len(text) / 50, 20)
            )

            results.append({
                "text": text,
                "score": score
            })

    if not results:
        return ""

    # Сначала удаляем точные дубли
    unique = {}

    for result in results:
        normalized = " ".join(
            result["text"].split()
        ).lower()

        if normalized not in unique:
            unique[normalized] = result

    results = list(unique.values())

    # Берём наиболее информативный результат
    best = max(
        results,
        key=lambda item: item["score"]
    )

    return best["text"]


# ============================================================
# OCR CORRECTION
# ============================================================

def correct_ocr(text):

    if not text.strip():
        return ""

    prompt = f"""
Ты исправляешь результат OCR с фотографии этикетки продукта.

ТЕКСТ OCR:

{text}

Твоя задача — сделать текст максимально похожим
на настоящий текст на упаковке.

Правила:

1. Исправляй только очевидные ошибки OCR.
2. НЕ добавляй новые ингредиенты.
3. НЕ удаляй существующие ингредиенты.
4. Сохраняй исходный порядок.
5. Не меняй смысл.
6. Не придумывай неизвестные слова.
7. Английские названия ингредиентов сохраняй на английском.
8. Латинские названия растений и веществ не переводи.
9. Если слово сомнительное — лучше оставить исходный вариант.
10. Не анализируй состав.
11. Не давай рекомендации.
12. Не добавляй объяснения.
13. Верни только исправленный текст.

ВАЖНО:

Если OCR пропустил часть информации,
не пытайся её придумать.

Верни только исправленный текст.
"""

    try:
        answer = gemini_request(prompt).strip()

        return answer if answer else text

    except Exception:
        return text


# ============================================================
# PRODUCT ANALYSIS
# ============================================================

def analyze_product(text):

    prompt = f"""
Ты — универсальный ИИ-анализатор состава потребительских продуктов.

Проанализируй ТОЛЬКО предоставленный состав:

{text}

============================================================
КАТЕГОРИЯ
============================================================

Определи одну категорию:

- Еда
- Напитки
- Косметика
- Средства личной гигиены
- Бытовая химия
- Чистящие средства
- Товары для животных
- Фармацевтические / медицинские продукты
- Другое

После категории обязательно определи
КОНКРЕТНЫЙ ТИП ПРОДУКТА.

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

============================================================
ОБЩИЕ ПРАВИЛА
============================================================

1. Анализируй только предоставленный состав.
2. Не придумывай отсутствующие ингредиенты.
3. Учитывай порядок ингредиентов, если он информативен.
4. Не считай сложное химическое название автоматически вредным.
5. Не считай синтетический компонент автоматически плохим.
6. Не утверждай абсолютную безопасность.
7. Не утверждай гарантированный вред.
8. Не ставь медицинские диагнозы.
9. Не обещай лечение.
10. Если состав неполный — обязательно укажи это.
11. Если информации недостаточно — снижай confidence.
12. Учитывай назначение продукта.

============================================================
ОЦЕНКА
============================================================

Для еды учитывай:

- добавленные сахара;
- соль;
- насыщенные жиры;
- белок;
- клетчатку;
- степень переработки;
- характер добавок.

Для напитков:

- сахар;
- подсластители;
- кофеин;
- кислотность;
- основные компоненты.

Для косметики:

- ПАВ;
- увлажнители;
- кондиционирующие компоненты;
- консерванты;
- отдушки;
- потенциально раздражающие компоненты;
- функциональность формулы.

Для бытовой химии:

- ПАВ;
- растворители;
- отдушки;
- консерванты;
- потенциально раздражающие компоненты;
- назначение продукта.

Для товаров животных:

- основные питательные компоненты;
- наполнители;
- консерванты;
- соответствие назначению.

Для фармацевтических / медицинских продуктов:

Только информационная оценка состава.
Без диагностики и рекомендаций по лечению.

============================================================
ИНДЕКС СОСТАВА
============================================================

0–39 — требуется осторожность
40–69 — средний
70–84 — хороший
85–100 — очень благоприятный

Индекс показывает общую благоприятность
состава с учётом назначения продукта.

Это НЕ показатель абсолютной безопасности.

============================================================
VERDICT
============================================================

green:
в целом благоприятный состав

orange:
есть компоненты или особенности,
требующие внимания

red:
есть существенные основания
для осторожности

============================================================
STATUS ИНГРЕДИЕНТА
============================================================

green:
обычный функциональный компонент

orange:
может требовать внимания
в зависимости от продукта и индивидуальной переносимости

red:
существенные основания для осторожности

Не ставь red только потому,
что название вещества звучит химически.

============================================================
ФОРМАТ ОТВЕТА
============================================================

Верни ТОЛЬКО JSON.

{{
    "score": 0,
    "verdict": "green",
    "verdict_text": "Краткий вывод",
    "category": "Категория",
    "product_type": "Конкретный тип продукта",
    "confidence": "high",
    "composition_complete": true,
    "summary": "Подробное, но понятное описание состава",
    "ingredients": [
        {{
            "name": "Название ингредиента",
            "type": "Назначение",
            "status": "green"
        }}
    ],
    "benefits": [
        "Положительная сторона"
    ],
    "risks": [
        "Что требует внимания"
    ],
    "recommendation": "Итоговая рекомендация"
}}
"""

    try:

        answer = gemini_request(prompt)

        data = json.loads(
            clean_json(answer)
        )

        if not isinstance(data, dict):
            raise ValueError("Gemini вернул неправильный формат JSON.")

        return data

    except Exception as error:

        st.error(
            f"Ошибка анализа Gemini: {error}"
        )

        return None


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">🧪 Анализатор состава продуктов E-vision</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Проверьте состав продукта и получите понятный '
    'анализ с рекомендациями.'
    '</div>',
    unsafe_allow_html=True
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
        st.caption(f"Сохранено анализов: {len(history)}")

        if st.button("🗑️ Очистить всю историю", use_container_width=True):
            save_history([])
            st.session_state.pop("selected_history", None)
            st.rerun()

        st.divider()

        for item in history:
            saved_result = item.get("result", {})
            score = safe_score(saved_result.get("score"))
            verdict = str(saved_result.get("verdict", "orange")).lower()
            icon = verdict_icon(verdict)

            product_type = saved_result.get(
                "product_type", "Неизвестный продукт"
            )
            category = saved_result.get("category", "Другое")

            st.markdown(f"**{icon} {product_type}**")
            st.caption(f"{category} · {score}/100")
            st.caption(item.get("date", ""))

            col_open, col_delete = st.columns([3, 1])

            with col_open:
                if st.button(
                    "Открыть",
                    key=f"open_{item['id']}",
                    use_container_width=True
                ):
                    st.session_state.selected_history = item
                    st.rerun()

            with col_delete:
                if st.button(
                    "🗑️",
                    key=f"delete_{item['id']}",
                    use_container_width=True
                ):
                    delete_from_history(item["id"])

                    if (
                        st.session_state.get(
                            "selected_history", {}
                        ).get("id") == item["id"]
                    ):
                        st.session_state.pop(
                            "selected_history", None
                        )

                    st.rerun()

            st.divider()


# ============================================================
# SELECTED HISTORY ANALYSIS
# ============================================================

selected_history = st.session_state.get("selected_history")

if selected_history:
    saved_result = selected_history.get("result", {})

    st.divider()
    st.subheader("📚 Сохранённый анализ")

    score = safe_score(saved_result.get("score"))
    verdict = str(saved_result.get("verdict", "orange")).lower()

    if verdict not in {"green", "orange", "red"}:
        verdict = "orange"

    icon = verdict_icon(verdict)

    category = saved_result.get("category", "Не определено")
    product_type = saved_result.get("product_type", "Не определено")

    st.markdown(f"### {icon} {product_type}")
    st.caption(
        f"{category} · {score}/100 · "
        f"{selected_history.get('date', '')}"
    )

    st.write(
        saved_result.get(
            "summary",
            "Описание отсутствует."
        )
    )

    st.markdown("**Состав:**")
    st.code(selected_history.get("text", ""), language=None)

    ingredients = as_list(
        saved_result.get("ingredients", [])
    )

    if ingredients:
        st.markdown("**Компоненты:**")

        for ingredient in ingredients:
            if not isinstance(ingredient, dict):
                continue

            name = ingredient.get("name", "Ингредиент")
            ingredient_type = ingredient.get(
                "type",
                "Назначение не указано"
            )
            status = str(
                ingredient.get("status", "orange")
            ).lower()

            ingredient_icon = {
                "green": "🟢",
                "orange": "🟠",
                "red": "🔴"
            }.get(status, "🟠")

            st.markdown(
                f"{ingredient_icon} **{name}** — {ingredient_type}"
            )

    st.markdown("### Итог")

    benefits = as_list(saved_result.get("benefits", []))
    risks = as_list(saved_result.get("risks", []))

    if benefits:
        st.markdown("**✅ Положительные стороны**")
        for item in benefits:
            st.markdown(f"• {item}")

    if risks:
        st.markdown("**⚠️ Что требует внимания**")
        for item in risks:
            st.markdown(f"• {item}")

    # ========================================================
    # SAVED ALLERGY ALERTS
    # ========================================================

    allergy_alerts = as_list(
        saved_result.get(
            "allergy_alerts",
            []
        )
    )

    allergy_note = str(
        saved_result.get(
            "allergy_note",
            ""
        )
    ).strip()

    if allergy_alerts or allergy_note:

        st.subheader(
            "⚠️ Аллергены и чувствительность"
        )

        if allergy_alerts:

            for alert in allergy_alerts:

                if not isinstance(
                    alert,
                    dict
                ):
                    continue

                alert_name = str(
                    alert.get(
                        "name",
                        "Компонент"
                    )
                )

                alert_reason = str(
                    alert.get(
                        "reason",
                        "Может требовать внимания "
                        "при индивидуальной чувствительности."
                    )
                )

                alert_level = str(
                    alert.get(
                        "level",
                        "attention"
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
                    st.caption(
                        alert_title
                    )
                    st.write(
                        alert_reason
                    )

        else:

            st.success(
                "✅ По предоставленному составу "
                "явных компонентов, требующих отдельного "
                "внимания с точки зрения аллергии, не обнаружено."
            )

        if allergy_note:
            st.caption(
                f"ℹ️ {allergy_note}"
            )

    st.info(
        saved_result.get(
            "recommendation",
            "Рекомендация отсутствует."
        )
    )

    if st.button("✖️ Закрыть сохранённый анализ"):
        st.session_state.pop("selected_history", None)
        st.rerun()


# ============================================================
# INPUT
# ============================================================

input_col, info_col = st.columns(
    [1, 1],
    gap="large"
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
            "📷 Загрузить фото"
        ],
        horizontal=True,
        label_visibility="collapsed"
    )

    product_text = ""

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
            height=220
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
                "webp"
            ],
            help=(
                "Лучше фотографировать этикетку прямо, "
                "близко и при хорошем освещении."
            )
        )

        if uploaded:

            image_bytes = uploaded.getvalue()

            image_hash = hashlib.md5(
                image_bytes
            ).hexdigest()

            image = Image.open(
                BytesIO(image_bytes)
            ).convert("RGB")

            st.image(
                image,
                caption="Загруженная фотография",
                use_container_width=True
            )

            # ------------------------------------------------
            # НОВАЯ ФОТОГРАФИЯ
            # ------------------------------------------------

            if st.session_state.get(
                "image_hash"
            ) != image_hash:

                st.session_state.image_hash = image_hash
                st.session_state.ocr_text = ""

                with st.spinner(
                    "🔎 Распознаём весь текст..."
                ):

                    raw_text = ocr_image(
                        image
                    )

                if raw_text:

                    # Сначала сохраняем сырой OCR,
                    # чтобы он никогда не потерялся
                    st.session_state.ocr_text = raw_text

                    with st.spinner(
                        "🤖 Проверяем ошибки OCR..."
                    ):

                        corrected_text = correct_ocr(
                            raw_text
                        )

                    if corrected_text.strip():
                        st.session_state.ocr_text = (
                            corrected_text
                        )

                else:

                    st.warning(
                        "⚠️ Не удалось распознать текст. "
                        "Попробуйте сфотографировать "
                        "этикетку ближе и ровнее."
                    )

            # ------------------------------------------------
            # OCR TEXT
            # ------------------------------------------------

            if st.session_state.get(
                "ocr_text"
            ):

                st.caption(
                    "Проверьте распознанный текст. "
                    "При необходимости исправьте его:"
                )

                product_text = st.text_area(
                    "Распознанный состав",
                    key="ocr_text",
                    height=250,
                    label_visibility="collapsed"
                )

                # Показываем нормальный статус
                if len(product_text.strip()) >= 30:

                    st.success(
                        "✅ Текст распознан"
                    )

                else:

                    st.warning(
                        "⚠️ Распознано мало текста. "
                        "Проверьте фотографию перед анализом."
                    )


    # --------------------------------------------------------
    # ANALYZE BUTTON
    # --------------------------------------------------------

    analyze = st.button(
        "🔍 Анализировать состав",
        type="primary",
        use_container_width=True
    )


# ============================================================
# HOW IT WORKS
# ============================================================

with info_col:

    st.subheader("⚙️ Как работает анализ")

    steps = [
        (
            "1️⃣",
            "Получаем состав",
            "Ввод вручную или фотография этикетки."
        ),
        (
            "2️⃣",
            "Распознаём фотографию",
            "OCR извлекает текст с изображения."
        ),
        (
            "3️⃣",
            "Проверяем OCR",
            "ИИ исправляет только очевидные ошибки."
        ),
        (
            "4️⃣",
            "Определяем продукт",
            "Определяются категория и конкретный тип."
        ),
        (
            "5️⃣",
            "Анализируем состав",
            "Компоненты оцениваются с учётом назначения."
        )
    ]

    with st.container(border=True):

        for icon, title, description in steps:

            st.markdown(
                f"**{icon}  {title}**"
            )

            st.caption(
                description
            )


# ============================================================
# ANALYSIS
# ============================================================

if analyze:

    if not product_text.strip():

        st.warning(
            "⚠️ Введите состав или загрузите фотографию."
        )

        st.stop()

    with st.spinner(
        "🤖 Анализируем состав..."
    ):

        result = analyze_product(
            product_text
        )

    if result:

        # Сохраняем результат каждого нажатия кнопки
        # «Анализировать состав».
        add_to_history(
            product_text,
            result
        )

        st.divider()

        st.subheader(
            "📊 Результат анализа"
        )

        # ====================================================
        # BASIC DATA
        # ====================================================

        score = safe_score(
            result.get("score")
        )

        verdict = str(
            result.get(
                "verdict",
                "orange"
            )
        ).lower()

        if verdict not in {
            "green",
            "orange",
            "red"
        }:
            verdict = "orange"

        category = str(
            result.get(
                "category",
                "Не определено"
            )
        )

        product_type = str(
            result.get(
                "product_type",
                "Не определено"
            )
        )

        # Защита от одинаковой категории
        # и типа продукта
        if (
            product_type.strip().lower()
            == category.strip().lower()
        ):
            product_type = (
                "Не удалось точно определить"
            )

        confidence = confidence_label(
            result.get(
                "confidence",
                "medium"
            )
        )

        # ====================================================
        # RESULT CARDS
        # ====================================================

        score_col, verdict_col, scale_col = st.columns(
            [1, 1.7, 1.25],
            gap="medium"
        )

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        with score_col:

            with st.container(border=True):

                st.caption(
                    "ИНДЕКС СОСТАВА"
                )

                st.markdown(
                    f'<div class="score-number">'
                    f'{score}'
                    f'</div>',
                    unsafe_allow_html=True
                )

                st.caption(
                    "/100"
                )

                st.markdown(
                    f"**Категория:** {category}"
                )

                st.markdown(
                    f"**Тип продукта:** {product_type}"
                )

        # ----------------------------------------------------
        # VERDICT
        # ----------------------------------------------------

        with verdict_col:

            with st.container(border=True):

                icon = verdict_icon(
                    verdict
                )

                verdict_text = str(
                    result.get(
                        "verdict_text",
                        "Средний состав"
                    )
                )

                st.markdown(
                    f'<div class="verdict-title">'
                    f'{icon} {verdict_text}'
                    f'</div>',
                    unsafe_allow_html=True
                )

                st.write(
                    result.get(
                        "summary",
                        "Описание отсутствует."
                    )
                )

                st.caption(
                    f"Уверенность анализа: {confidence}"
                )

        # ----------------------------------------------------
        # SCALE
        # ----------------------------------------------------

        with scale_col:

            with st.container(border=True):

                st.markdown(
                    "**Индекс состава**"
                )

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
    0–39 — осторожность<br>
    40–69 — средний<br>
    70–84 — хороший<br>
    85–100 — очень благоприятный
</div>
"""

                st.markdown(
                    scale_html,
                    unsafe_allow_html=True
                )

        # ====================================================
        # INCOMPLETE COMPOSITION
        # ====================================================

        if not result.get(
            "composition_complete",
            True
        ):

            st.warning(
                "⚠️ Состав может быть неполным. "
                "Индекс и вывод могут быть менее точными."
            )

        # ====================================================
        # INGREDIENTS
        # ====================================================

        st.subheader(
            "🧬 Разбор компонентов"
        )

        ingredients = as_list(
            result.get(
                "ingredients",
                []
            )
        )

        if ingredients:

            cols = st.columns(
                4,
                gap="small"
            )

            for i, ingredient in enumerate(
                ingredients
            ):

                if not isinstance(
                    ingredient,
                    dict
                ):
                    continue

                name = str(
                    ingredient.get(
                        "name",
                        "Ингредиент"
                    )
                )

                ingredient_type = str(
                    ingredient.get(
                        "type",
                        "Назначение не указано"
                    )
                )

                status = str(
                    ingredient.get(
                        "status",
                        "orange"
                    )
                ).lower()

                icon = {
                    "green": "🟢",
                    "orange": "🟠",
                    "red": "🔴"
                }.get(
                    status,
                    "🟠"
                )

                with cols[i % 4]:

                    with st.container(
                        border=True
                    ):

                        st.markdown(
                            f"**{icon} {name}**"
                        )

                        st.caption(
                            ingredient_type
                        )

                        explanation = str(
                            ingredient.get(
                                "explanation",
                                ""
                            )
                        ).strip()

                        if explanation:
                            st.write(
                                explanation
                            )

                        attention_reason = str(
                            ingredient.get(
                                "attention_reason",
                                ""
                            )
                        ).strip()

                        if attention_reason:
                            st.warning(
                                f"⚠️ {attention_reason}"
                            )

        else:

            st.info(
                "Подробный разбор компонентов "
                "не получен."
            )

        # ====================================================
        # ALLERGY ALERTS
        # ====================================================

        allergy_alerts = as_list(
            result.get(
                "allergy_alerts",
                []
            )
        )

        allergy_note = str(
            result.get(
                "allergy_note",
                ""
            )
        ).strip()

        if allergy_alerts or allergy_note:

            st.subheader(
                "⚠️ Аллергены и чувствительность"
            )

            if allergy_alerts:

                for alert in allergy_alerts:

                    if not isinstance(
                        alert,
                        dict
                    ):
                        continue

                    alert_name = str(
                        alert.get(
                            "name",
                            "Компонент"
                        )
                    )

                    alert_reason = str(
                        alert.get(
                            "reason",
                            "Может требовать внимания "
                            "при индивидуальной чувствительности."
                        )
                    )

                    alert_level = str(
                        alert.get(
                            "level",
                            "attention"
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
                        st.caption(
                            alert_title
                        )
                        st.write(
                            alert_reason
                        )

            else:

                st.success(
                    "✅ По предоставленному составу "
                    "явных компонентов, требующих отдельного "
                    "внимания с точки зрения аллергии, не обнаружено."
                )

            if allergy_note:
                st.caption(
                    f"ℹ️ {allergy_note}"
                )

        # ====================================================
        # FINAL INFORMATION
        # ====================================================

        st.subheader(
            "📋 Итог"
        )

        benefits_col, risks_col, recommendation_col = st.columns(
            3,
            gap="medium"
        )

        benefits = as_list(
            result.get(
                "benefits",
                []
            )
        )

        risks = as_list(
            result.get(
                "risks",
                []
            )
        )

        # ----------------------------------------------------
        # BENEFITS
        # ----------------------------------------------------

        with benefits_col:

            with st.container(
                border=True
            ):

                st.markdown(
                    "### ✅ Положительные стороны"
                )

                if benefits:

                    for item in benefits:

                        st.markdown(
                            f"• {item}"
                        )

                else:

                    st.caption(
                        "Существенных положительных "
                        "сторон не выделено."
                    )

        # ----------------------------------------------------
        # RISKS
        # ----------------------------------------------------

        with risks_col:

            with st.container(
                border=True
            ):

                st.markdown(
                    "### ⚠️ Что требует внимания"
                )

                if risks:

                    for item in risks:

                        st.markdown(
                            f"• {item}"
                        )

                else:

                    st.caption(
                        "Существенных замечаний "
                        "не выделено."
                    )

        # ----------------------------------------------------
        # RECOMMENDATION
        # ----------------------------------------------------

        with recommendation_col:

            with st.container(
                border=True
            ):

                st.markdown(
                    "### 💡 Рекомендация"
                )

                st.write(
                    result.get(
                        "recommendation",
                        "Рекомендация отсутствует."
                    )
                )

        # ====================================================
        # DISCLAIMER
        # ====================================================

        st.divider()

        st.caption(
            "ℹ️ Индекс состава является информационной "
            "оценкой благоприятности состава с учётом "
            "назначения продукта. Он не гарантирует "
            "абсолютную безопасность и не является "
            "медицинской рекомендацией."
        )
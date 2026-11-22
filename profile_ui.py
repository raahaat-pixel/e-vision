"""Settings UI, additive to the existing E-vision interface."""
import streamlit as st
from evision_extras import save_profile

FOODS = ['Фрукты', 'Овощи', 'Ягоды', 'Мясо', 'Рыба', 'Молочные продукты', 'Злаки', 'Орехи', 'Сладкое / сахар']
ACTIVES = ['AHA-кислоты', 'BHA / салициловая кислота', 'PHA-кислоты', 'Ретиноиды', 'Витамин C', 'Ниацинамид', 'Бензоилпероксид', 'Азелаиновая кислота']

def render_settings(username, profile):
    st.subheader(':material/settings: Настройки')
    st.caption('Все поля необязательны. Имя для отображения не меняет имя входа и историю.')
    st.warning('Вход защищён только именем: любой, кто знает его, может открыть этот профиль. Не указывайте данные, которыми не готовы поделиться. Файлы на сервере Streamlit Cloud могут потеряться при перезапуске или обновлении.')
    with st.form('ev_settings_form'):
        profile_tab, food_tab, cosmetic_tab = st.tabs(['Профиль', 'Питание', 'Косметика'])
        with profile_tab:
            name = st.text_input('Имя для отображения', value=profile.get('display_name', username), max_chars=60)
            age = st.number_input('Возраст (0 — не указывать)', min_value=0, max_value=120, value=int(profile.get('age') or 0), step=1)
            sex_options = ['Не указывать', 'Женский', 'Мужской', 'Другой вариант']
            sex = st.selectbox('Пол', sex_options, index=sex_options.index(profile.get('sex', 'Не указывать')) if profile.get('sex', 'Не указывать') in sex_options else 0)
        with food_tab:
            allergies = st.text_area('Аллергии и непереносимости', value=profile.get('allergies', ''), max_chars=1000, help='Необязательно; например, молоко или орехи.')
            conditions = st.text_area('Заболевания и ограничения', value=profile.get('conditions', ''), max_chars=1000, help='Необязательно; например, диабет.')
            st.markdown('**Что вам нравится**')
            st.caption('Предпочтения не означают, что продукт подходит по состоянию здоровья.')
            food_preferences = []
            cols = st.columns(2)
            for i, food in enumerate(FOODS):
                with cols[i % 2]:
                    if st.checkbox(food, value=food in profile.get('food_preferences', []), key=f'food_{i}'):
                        food_preferences.append(food)
            food_other = st.text_input('Другие пищевые предпочтения', value=profile.get('food_other', ''), max_chars=300)
        with cosmetic_tab:
            skin_options = ['Не указывать', 'Нормальная', 'Сухая', 'Жирная', 'Комбинированная', 'Не знаю']
            skin_type = st.selectbox('Тип кожи', skin_options, index=skin_options.index(profile.get('skin_type', 'Не указывать')) if profile.get('skin_type', 'Не указывать') in skin_options else 0)
            sensitivity_options = ['Не указывать', 'Чувствительная', 'Не чувствительная', 'Не знаю']
            skin_sensitivity = st.selectbox('Чувствительность кожи', sensitivity_options, index=sensitivity_options.index(profile.get('skin_sensitivity', 'Не указывать')) if profile.get('skin_sensitivity', 'Не указывать') in sensitivity_options else 0)
            skin_other = st.text_input('Другие особенности кожи', value=profile.get('skin_other', ''), max_chars=500)
            st.markdown('**Какие активы вы используете?**')
            actives = []
            cols = st.columns(2)
            for i, active in enumerate(ACTIVES):
                with cols[i % 2]:
                    if st.checkbox(active, value=active in profile.get('actives', []), key=f'active_{i}'):
                        actives.append(active)
            other_actives = st.text_input('Другие активы', value=profile.get('other_actives', ''), max_chars=300)
        share = st.checkbox('Разрешаю передавать данные профиля в Gemini для персонализации анализа', value=bool(profile.get('share_with_ai')), help='Выключите, чтобы профиль не отправлялся в Gemini. Данные могут содержать сведения о здоровье.')
        if st.form_submit_button('Сохранить настройки', type='primary', use_container_width=True):
            updated = dict(profile)
            updated.update({'display_name': name.strip(), 'age': int(age) or None, 'sex': '' if sex == 'Не указывать' else sex,
                            'allergies': allergies.strip(), 'conditions': conditions.strip(), 'food_preferences': food_preferences,
                            'food_other': food_other.strip(), 'skin_type': '' if skin_type == 'Не указывать' else skin_type,
                            'skin_sensitivity': '' if skin_sensitivity == 'Не указывать' else skin_sensitivity,
                            'skin_other': skin_other.strip(), 'actives': actives, 'other_actives': other_actives.strip(), 'share_with_ai': share})
            try:
                save_profile(username, updated)
            except (OSError, ValueError) as exc:
                st.error('Не удалось сохранить профиль. Проверьте файл profiles.json и права записи.')
            else:
                st.success('Настройки сохранены.')
                st.rerun()

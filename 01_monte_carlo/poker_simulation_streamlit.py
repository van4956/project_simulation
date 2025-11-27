import streamlit as st
import matplotlib.pyplot as plt
from typing import List, Tuple, Dict
from treys import Card

# Импортируем функцию расчёта из основного модуля
from poker_simulation import monte_carlo, EVALUATOR



# НАСТРОЙКА СТРАНИЦЫ

st.set_page_config(
    page_title="Poker Calculator",
    page_icon="♠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Заголовок
st.title("Monte Carlo Poker Calculator ♠️♥️♣️♦️")
st.markdown("Интерактивный калькулятор для Покера с использованием метода Монте-Карло")
st.markdown("""
Вместо точного перебора всех возможных комбинаций карт (что заняло бы слишком много времени),
метод Монте-Карло случайно симулирует тысячи раздач и подсчитывает статистику побед.

Чем больше симуляций - тем точнее результат. При 10,000 симуляций точность составляет ~99%.
""")
st.markdown("---")


# ГЕНЕРАЦИЯ СПИСКА КАРТ

@st.cache_data
def generate_cards() -> Tuple[List[str], Dict[str, int]]:
    """
    Генерирует список всех карт и mapping для отображения.

    Returns:
        (список карт для отображения, словарь маппинга)
    """
    suits = {'s': '♠', 'h': '♥', 'd': '♦', 'c': '♣'}
    ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']

    all_cards = []
    mapping = {}

    for rank in ranks:
        for suit_short, suit_symbol in suits.items():
            display_name = f"{rank}{suit_symbol}"
            card_code = f"{rank}{suit_short}"
            all_cards.append(display_name)
            mapping[display_name] = Card.new(card_code)

    return all_cards, mapping


ALL_CARDS, CARDS_MAPPING = generate_cards()
EMPTY_CARD = "-- (пусто)"



# БОКОВАЯ ПАНЕЛЬ

# Карты игрока
st.sidebar.subheader("Карты игрока")
col1, col2 = st.sidebar.columns(2)
with col1:
    hero_card1 = st.selectbox("", ALL_CARDS, index=0, key="hero1")
with col2:
    hero_card2 = st.selectbox("", ALL_CARDS, index=1, key="hero2")

# Карты стола
st.sidebar.subheader("Карты на столе")
st.sidebar.caption("Флоп:")
col1, col2, col3 = st.sidebar.columns(3)
with col1:
    board1 = st.selectbox("1", [EMPTY_CARD] + ALL_CARDS, index=0, key="board1", label_visibility="collapsed")
with col2:
    board2 = st.selectbox("2", [EMPTY_CARD] + ALL_CARDS, index=0, key="board2", label_visibility="collapsed")
with col3:
    board3 = st.selectbox("3", [EMPTY_CARD] + ALL_CARDS, index=0, key="board3", label_visibility="collapsed")

st.sidebar.caption("Терн:")
col1, = st.sidebar.columns(1)
with col1:
    board4 = st.selectbox("Терн", [EMPTY_CARD] + ALL_CARDS, index=0, key="board4", label_visibility="collapsed")

st.sidebar.caption("Ривер:")
col1, = st.sidebar.columns(1)
with col1:
    board5 = st.selectbox("Ривер", [EMPTY_CARD] + ALL_CARDS, index=0, key="board5", label_visibility="collapsed")

# Параметры симуляции
st.sidebar.markdown("---")
st.sidebar.subheader("Параметры симуляции")
num_players = st.sidebar.slider(
    "Количество активных игроков:",
    min_value=2,
    max_value=9,
    value=3,
    step=1
)

num_simulations = st.sidebar.slider(
    "Количество симуляций:",
    min_value=1000,
    max_value=100000,
    value=10000,
    step=1000,
    format="%d"
)

# Кнопка расчёта
st.sidebar.markdown("---")
calculate_button = st.sidebar.button("🎲 Рассчитать", type="primary", use_container_width=True)



# ВАЛИДАЦИЯ КАРТ

def validate_selected_cards(hero1: str, hero2: str, board_cards: List[str]) -> Tuple[bool, str]:
    """
    Проверяет, что карты не повторяются.

    Args:
        hero1: Первая карта игрока
        hero2: Вторая карта игрока
        board_cards: Список карт на столе (без пустых)

    Returns:
        (валидность, сообщение об ошибке)
    """
    selected = [hero1, hero2] + [c for c in board_cards if c != EMPTY_CARD]

    if len(selected) != len(set(selected)):
        return False, "❌ Некоторые карты выбраны дважды!"

    return True, ""



# ОСНОВНАЯ ЛОГИКА

if calculate_button:
    # Собираем карты стола
    board_list = [board1, board2, board3, board4, board5]

    # Валидация
    is_valid, error_msg = validate_selected_cards(hero_card1, hero_card2, board_list)

    if not is_valid:
        st.error(error_msg)
    else:
        # Подготовка данных
        hero_cards = [CARDS_MAPPING[hero_card1], CARDS_MAPPING[hero_card2]]
        board_cards = [CARDS_MAPPING[c] for c in board_list if c != EMPTY_CARD]

        # Информация о раздаче
        st.subheader("📋 Информация о раздаче")
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Игроков", num_players)
        with col2:
            st.metric("Симуляций", f"{num_simulations:,}")
        with col3:
            board_phase = "Префлоп" if len(board_cards) == 0 else \
                         "Флоп" if len(board_cards) == 3 else \
                         "Терн" if len(board_cards) == 4 else "Ривер"
            st.metric("Фаза", board_phase)

        st.markdown(f"Карты игрока:        {hero_card1} {hero_card2}")
        if board_cards:
            board_str = " ".join([c for c in board_list if c != EMPTY_CARD])
            st.markdown(f"Карты на столе: {board_str}")

        # Прогресс-бар
        progress_bar = st.progress(0, text="Запуск симуляций...")

        # Расчёт
        wins, ties, losses = monte_carlo(hero_cards, board_cards, num_players, num_simulations)

        progress_bar.progress(100, text="Расчёт завершён!")

        # Результаты
        st.markdown("---")
        st.subheader("📊 Результаты")

        # Метрики
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            win_pct = wins / num_simulations
            st.metric("🏆 Побед", f"{wins:,}", f"{win_pct:.1%}")

        with col2:
            tie_pct = ties / num_simulations
            st.metric("🤝 Ничьих", f"{ties:,}", f"{tie_pct:.1%}")

        with col3:
            loss_pct = losses / num_simulations
            st.metric("❌ Поражений", f"{losses:,}", f"{loss_pct:.1%}")

        # График
        st.markdown("---")

        fig, ax = plt.subplots(figsize=(10, 5))

        categories = ['Победы', 'Ничьи', 'Поражения']
        values = [wins, ties, losses]
        colors = ['#4caf50', '#ffeb3b', '#f44336']

        bars = ax.bar(categories, values, color=colors, alpha=0.85, edgecolor='black', linewidth=2)

        # Отступ сверху для текста
        ax.set_ylim(0, max(values) * 1.15)

        # Значения над столбцами
        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.,
                height,
                f'{val:,} ({val/num_simulations:.1%})',
                ha='center',
                va='bottom',
                fontsize=12,
                weight='bold'
            )

        ax.set_ylabel('Количество симуляций', fontsize=12)
        ax.set_title(f'Результат на {num_simulations:,} симуляций', fontsize=14, weight='bold')
        ax.grid(axis='y', alpha=0.3, linestyle='--')

        plt.tight_layout()
        st.pyplot(fig)

        # Очистка
        progress_bar.empty()

else:
    # Инструкция, если кнопка не нажата
    st.info("Выберите карты и параметры в боковой панели, затем нажмите **🎲 Рассчитать**")



# FOOTER

st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray; font-size: 0.9em;'>
        <a href='https://github.com/van4956/project_simulation/tree/main/01_monte_carlo' target='_blank'>GitHub</a>
    </div>
    """,
    unsafe_allow_html=True
)

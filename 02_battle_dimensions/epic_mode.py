# -*- coding: utf-8 -*-
"""
Симулятор "Битва Измерений" — Epic mode
- базовые правила + эпические механики
- рандомные ходы
- условные вероятности побед (wins[f] / participates[f])

Особенности Epic:
- Красный: Капитан Сила (неуязвим для Чёрной Дыры/Кротовой Норы, даёт +1 к отряду красных; двигать может только владелец)
- Зелёный: мгновенная победа, если в любом одном Измерении >= 5 зелёных карт
- Жёлтый: мгновенная победа, если во всех Измерениях есть >=1 жёлтая и суммарно >=5 жёлтых
- Синий: мгновенная победа, если сумма значений карт синих в любом одном Измерении ровно 42
- Фиолетовый: при победе в атаке преобразует потерю врага в Ауру Тьмы (остаётся на поле);
             Ауры нельзя перемещать/воротить Кротовой Норой; фиолетовый не может атаковать Ауры;
             при конце игры Ауры засчитываются фиолетовым

Примечание по данным:
- Карты синих различимы: значения [2,3,5,7,11,13,17,17,19,23,29] -> в коде как строки 'blue#V'
- Прочие цвета: строки 'red','green','yellow','purple'
- Аномалии: 'anom_*'
- Ауры в сбросе учитываем как спец-метку 'aura_back' (Большой Взрыв их НЕ возвращает)

Порядок фрагментов: импорты -> константы -> типы -> утилиты -> аномалии -> фазы -> проверки побед ->
одна партия -> симуляции.
"""

from __future__ import annotations

import random
from collections import Counter, deque
from typing import List, Tuple, Dict, Optional

# =========================
# Константы
# =========================

FRACTIONS = ["red", "green", "yellow", "blue", "purple"]
BLUE_VALUES = [2, 3, 5, 7, 11, 13, 17, 17, 19, 23, 29]
CNT_PLAYERS = 3
CNT_SIMULATIONS = 1_000_000
RANDOM_SEED = 42

ANOMALIES = [
    "anom_quantum_entanglement",
    "anom_wormhole",
    "anom_black_hole",
    "anom_big_bang",
    "anom_time_loop",
]

TARGET_HAND = 4

# =========================
# Типы / Алиасы
# =========================

Hand = Counter            # счётчик по идентификаторам карт ("red", "blue#17", "anom_*")
AreaCount = Counter       # счётчик видимых карт по цветам (без капитана)
Deck = List[str]

# =========================
# Утилиты и базовые функции
# =========================

def is_anomaly(card: str) -> bool:
    return card.startswith("anom_")


def is_blue(card: str) -> bool:
    return card.startswith("blue#")


def blue_value(card: str) -> int:
    return int(card.split("#", 1)[1])


def card_color(card: str) -> Optional[str]:
    if is_anomaly(card):
        return None
    if is_blue(card):
        return "blue"
    if card in FRACTIONS:
        return card
    if card == "aura_back":
        return None
    return None


def init_deck_epic() -> Deck:
    deck: Deck = []
    # 11 карт каждого цвета, синий — различимые
    for f in FRACTIONS:
        if f == "blue":
            deck.extend([f"blue#{v}" for v in BLUE_VALUES])
        else:
            deck.extend([f] * 11)
    # +1 случайная аномалия
    deck.append(random.choice(ANOMALIES))
    random.shuffle(deck)
    return deck


def random_assign_players(n: int) -> List[str]:
    return random.sample(FRACTIONS, n)


def make_spiral() -> List[str]:
    spiral = FRACTIONS[:]
    random.shuffle(spiral)
    return spiral


def beats(a: str, b: str, spiral: List[str]) -> bool:
    idx = {c: i for i, c in enumerate(spiral)}
    return (idx[a] + 1) % len(spiral) == idx[b]


def deal_cards(deck: Deck, hands: List[Hand], target: int, start_idx: int) -> Optional[int]:
    n = len(hands)
    order = list(range(start_idx, start_idx + n))
    last_card_taker: Optional[int] = None
    for raw_i in order:
        i = raw_i % n
        need = max(0, target - sum(hands[i].values()))
        for _ in range(need):
            if not deck:
                return last_card_taker
            card = deck.pop()
            hands[i][card] += 1
            if not deck:
                return i
    return last_card_taker


def ensure_blue_sync(area_counts: AreaCount, area_blue_values: List[int]) -> None:
    # синхронизировать счётчик синего по количеству значений
    area_counts["blue"] = len(area_blue_values)


def add_card_to_area(area_counts: AreaCount, area_blue_values: List[int], color_or_card: str) -> None:
    c = card_color(color_or_card)
    if c is None:
        return
    if c == "blue":
        area_blue_values.append(blue_value(color_or_card))
        ensure_blue_sync(area_counts, area_blue_values)
    else:
        area_counts[c] += 1


def remove_one_from_area(area_counts: AreaCount, area_blue_values: List[int], color: str) -> Optional[str]:
    """Удалить одну карту указанного цвета из Измерения (и вернуть идентификатор карты, если нужно).
    Для blue снимем одно значение (случайно). Для прочих — просто уменьшаем счётчик.
    """
    if color == "blue":
        if area_blue_values:
            idx = random.randrange(len(area_blue_values))
            val = area_blue_values.pop(idx)
            ensure_blue_sync(area_counts, area_blue_values)
            return f"blue#{val}"
        return None
    if area_counts.get(color, 0) > 0:
        area_counts[color] -= 1
        if area_counts[color] <= 0:
            del area_counts[color]
        return color
    return None


# =========================
# Аномалии
# =========================

def play_anom_quantum_entanglement(spiral: List[str]) -> None:
    if len(spiral) < 2:
        return
    i, j = random.sample(range(len(spiral)), 2)
    spiral[i], spiral[j] = spiral[j], spiral[i]


def play_anom_wormhole(
    areas_counts: List[AreaCount],
    areas_blue: List[List[int]],
    captain_pos: Optional[int]
) -> None:
    # собираем все перемещаемые отряды: цвет != aura, и если red с капитаном — переносим только обычные красные
    squads: List[Tuple[int, str]] = []
    for pi in range(len(areas_counts)):
        for color, cnt in areas_counts[pi].items():
            if cnt <= 0:
                continue
            if color == "blue" and cnt <= 0:
                continue
            if color == "red" and captain_pos == pi and cnt <= 0:
                continue
            squads.append((pi, color))
    # добавить потенциальный перенос для blue только если реально есть карты (cnt>0, уже учтено)
    # Ауры не перемещаем
    if not squads:
        return
    src_idx, color = random.choice(squads)
    dst_candidates = [k for k in range(len(areas_counts)) if k != src_idx]
    if not dst_candidates:
        return
    dst_idx = random.choice(dst_candidates)

    # переносим ВЕСЬ отряд данного цвета (кроме капитана)
    if color == "blue":
        k = len(areas_blue[src_idx])
        if k <= 0:
            return
        vals = areas_blue[src_idx][:]
        areas_blue[src_idx].clear()
        ensure_blue_sync(areas_counts[src_idx], areas_blue[src_idx])
        areas_blue[dst_idx].extend(vals)
        ensure_blue_sync(areas_counts[dst_idx], areas_blue[dst_idx])
    else:
        cnt = areas_counts[src_idx].get(color, 0)
        if color == "red" and captain_pos == src_idx:
            # переносим только обычные карты, капитан остаётся
            move_cnt = cnt
        else:
            move_cnt = cnt
        if move_cnt <= 0:
            return
        areas_counts[src_idx][color] -= move_cnt
        if areas_counts[src_idx][color] <= 0:
            del areas_counts[src_idx][color]
        areas_counts[dst_idx][color] += move_cnt


def play_anom_black_hole(
    areas_counts: List[AreaCount],
    areas_blue: List[List[int]],
    areas_auras: List[int],
    captain_pos: Optional[int],
    delete_pile: List[str]
) -> None:
    # цели: любой отряд цвета или ауры
    options: List[Tuple[str, int]] = []  # (kind, idx) kind in {color,<aura>}
    for pi in range(len(areas_counts)):
        # ауры
        if areas_auras[pi] > 0:
            options.append(("aura", pi))
        # цвета
        for color, cnt in areas_counts[pi].items():
            if cnt > 0:
                options.append((f"color:{color}", pi))
    if not options:
        return

    kind, pi = random.choice(options)
    if kind == "aura":
        # все ауры в сброс (как невозвращаемые)
        k = areas_auras[pi]
        for _ in range(k):
            delete_pile.append("aura_back")
        areas_auras[pi] = 0
        return

    color = kind.split(":", 1)[1]
    if color == "blue":
        # все синие — в сброс
        while areas_blue[pi]:
            val = areas_blue[pi].pop()
            delete_pile.append(f"blue#{val}")
        ensure_blue_sync(areas_counts[pi], areas_blue[pi])
        return

    if color == "red" and captain_pos == pi:
        # капитана нельзя уничтожить: отправляем все обычные красные, капитан остаётся
        k = areas_counts[pi].get("red", 0)
        for _ in range(k):
            delete_pile.append("red")
        if "red" in areas_counts[pi]:
            del areas_counts[pi]["red"]
        return

    # обычные цвета
    k = areas_counts[pi].get(color, 0)
    for _ in range(k):
        delete_pile.append(color)
    if color in areas_counts[pi]:
        del areas_counts[pi][color]


def play_anom_big_bang(deck: Deck, delete_pile: List[str]) -> None:
    # возвращаем из сброса ТОЛЬКО цветные карты ("red","green","yellow","purple","blue#V")
    to_return = [c for c in delete_pile if (c in FRACTIONS) or is_blue(c)]
    if not to_return:
        return
    deck.extend(to_return)
    # очищаем только то, что вернули
    keep = [c for c in delete_pile if c not in to_return]
    delete_pile.clear()
    delete_pile.extend(keep)
    random.shuffle(deck)


def play_anom_time_loop(turn_queue: deque[int], current_player: int) -> None:
    turn_queue.appendleft(current_player)


def try_play_anomaly(
    player_idx: int,
    hands: List[Hand],
    spiral: List[str],
    areas_counts: List[AreaCount],
    areas_blue: List[List[int]],
    areas_auras: List[int],
    captain_pos: Optional[int],
    deck: Deck,
    delete_pile: List[str],
    turn_queue: deque[int]
) -> None:
    hand = hands[player_idx]
    anoms = [k for k in hand if is_anomaly(k) and hand[k] > 0]
    if not anoms:
        return
    chosen = random.choice(anoms)

    if chosen == "anom_quantum_entanglement":
        play_anom_quantum_entanglement(spiral)
    elif chosen == "anom_wormhole":
        play_anom_wormhole(areas_counts, areas_blue, captain_pos)
    elif chosen == "anom_black_hole":
        play_anom_black_hole(areas_counts, areas_blue, areas_auras, captain_pos, delete_pile)
    elif chosen == "anom_big_bang":
        play_anom_big_bang(deck, delete_pile)
    elif chosen == "anom_time_loop":
        play_anom_time_loop(turn_queue, player_idx)

    hand[chosen] -= 1
    if hand[chosen] <= 0:
        del hand[chosen]
    delete_pile.append(chosen)


# =========================
# Фазы
# =========================

def first_wins_among(colors: List[str], spiral: List[str]) -> List[str]:
    unique = set(colors)
    if len(unique) == 1:
        return list(unique)
    winners: List[str] = []
    for c in unique:
        beats_some = any(beats(c, d, spiral) for d in unique if d != c)
        lost_some = any(beats(d, c, spiral) for d in unique if d != c)
        if beats_some and not lost_some:
            winners.append(c)
    return winners


def phase_battle_of_dimensions(
    hands: List[Hand],
    areas_counts: List[AreaCount],
    areas_blue: List[List[int]],
    delete_pile: List[str],
    spiral: List[str]
) -> None:
    n = len(hands)
    plays: List[Tuple[int, Optional[str]]] = []

    for i in range(n):
        opts = [c for c, cnt in hands[i].items() if cnt > 0 and not is_anomaly(c)]
        # допускаем только фракционные карты; если нет — пасует
        opts = [c for c in opts if (card_color(c) in FRACTIONS)]
        if not opts:
            plays.append((i, None))
            continue
        chosen = random.choice(opts)
        hands[i][chosen] -= 1
        if hands[i][chosen] <= 0:
            del hands[i][chosen]
        plays.append((i, chosen))

    colors = [card_color(c) for _, c in plays if c is not None]
    if not colors:
        return

    winners = first_wins_among([c for c in colors if c], spiral)

    if not winners:
        for _, c in plays:
            if c is not None:
                delete_pile.append(c)
        return

    for i, c in plays:
        if c is None:
            continue
        if card_color(c) in winners:
            add_card_to_area(areas_counts[i], areas_blue[i], c)
        else:
            delete_pile.append(c)


def phase_reinforcement(
    current_player: int,
    hands: List[Hand],
    areas_counts: List[AreaCount],
    areas_blue: List[List[int]],
    players_factions: List[str],
    captain_pos: Optional[int]
) -> Optional[int]:
    """Возвращает новый captain_pos, если капитан был выложен."""
    hand = hands[current_player]

    # Возможность выложить капитана вместо обычной карты (если игрок — красный и капитана нет)
    if players_factions[current_player] == "red" and captain_pos is None:
        # С вероятностью 0.3 выкладываем капитана вместо карты (грубо рандомная эвристика)
        if random.random() < 0.3:
            # положим капитана в своё Измерение
            captain_pos = current_player
            # капитан считается как +1 к красным при подсчёте/боях, но отдельной карты нет
            return captain_pos

    # Иначе выкладываем обычную карту в любое Измерение
    opts = [c for c, cnt in hand.items() if cnt > 0 and not is_anomaly(c) and card_color(c) in FRACTIONS]
    if not opts:
        return captain_pos
    chosen = random.choice(opts)
    hand[chosen] -= 1
    if hand[chosen] <= 0:
        del hand[chosen]

    dst = random.randrange(len(areas_counts))
    add_card_to_area(areas_counts[dst], areas_blue[dst], chosen)
    return captain_pos


def phase_movement_or_anomaly(
    current_player: int,
    hands: List[Hand],
    areas_counts: List[AreaCount],
    areas_blue: List[List[int]],
    areas_auras: List[int],
    players_factions: List[str],
    spiral: List[str],
    deck: Deck,
    delete_pile: List[str],
    turn_queue: deque[int],
    captain_pos: Optional[int]
) -> Optional[int]:
    # 50% сыграть аномалию
    if random.random() < 0.5:
        try_play_anomaly(
            player_idx=current_player,
            hands=hands,
            spiral=spiral,
            areas_counts=areas_counts,
            areas_blue=areas_blue,
            areas_auras=areas_auras,
            captain_pos=captain_pos,
            deck=deck,
            delete_pile=delete_pile,
            turn_queue=turn_queue,
        )
        return captain_pos

    # Иначе перемещение одной карты между Измерениями (кроме Аур и Капитана)
    candidates = [i for i, ac in enumerate(areas_counts) if sum(ac.values()) > 0 or len(areas_blue[i]) > 0]
    if not candidates:
        return captain_pos
    src_idx = random.choice(candidates)

    # Выбор цвета источника
    colors = list(areas_counts[src_idx].keys())
    if areas_blue[src_idx]:
        colors.append("blue")
    if not colors:
        return captain_pos

    color = random.choice(colors)
    if color == "red" and captain_pos == src_idx and areas_counts[src_idx].get("red", 0) <= 0:
        return captain_pos  # нельзя переместить капитана

    # Выбор приёмника
    dst_idx = random.randrange(len(areas_counts))
    if dst_idx == src_idx:
        return captain_pos

    # Перенос одной карты
    if color == "blue":
        if areas_blue[src_idx]:
            val = areas_blue[src_idx].pop(random.randrange(len(areas_blue[src_idx])))
            ensure_blue_sync(areas_counts[src_idx], areas_blue[src_idx])
            areas_blue[dst_idx].append(val)
            ensure_blue_sync(areas_counts[dst_idx], areas_blue[dst_idx])
    else:
        if areas_counts[src_idx].get(color, 0) > 0:
            areas_counts[src_idx][color] -= 1
            if areas_counts[src_idx][color] <= 0:
                del areas_counts[src_idx][color]
            areas_counts[dst_idx][color] += 1

    return captain_pos


def phase_attack(
    current_player: int,
    areas_counts: List[AreaCount],
    areas_blue: List[List[int]],
    areas_auras: List[int],
    spiral: List[str],
    captain_pos: Optional[int],
    delete_pile: List[str]
) -> None:
    # доступные атакующие цвета в своём Измерении
    ac = areas_counts[current_player]
    attackers: List[str] = []
    for color in FRACTIONS:
        sz = squad_size_in_area(color, current_player, areas_counts, areas_blue, captain_pos)
        if sz > 0:
            attackers.append(color)
    if not attackers:
        return
    atk_color = random.choice(attackers)

    # цели: в том же Измерении, другого цвета; Ауры — отдельная цель 'aura'
    targets: List[str] = []  # значения: цвета или 'aura'
    # цвета
    for color in FRACTIONS:
        if color != atk_color:
            if squad_size_in_area(color, current_player, areas_counts, areas_blue, captain_pos) > 0:
                targets.append(color)
    # ауры
    if areas_auras[current_player] > 0 and atk_color != "purple":
        targets.append("aura")

    if not targets:
        return
    def_t = random.choice(targets)

    # Размеры отрядов
    atk_sz = squad_size_in_area(atk_color, current_player, areas_counts, areas_blue, captain_pos)
    if def_t == "aura":
        def_sz = areas_auras[current_player]
    else:
        def_sz = squad_size_in_area(def_t, current_player, areas_counts, areas_blue, captain_pos)

    atk_wins = (atk_sz > def_sz) or (def_t != "aura" and beats(atk_color, def_t, spiral))

    if not atk_wins:
        return

    # Применяем потери защитника
    if def_t == "aura":
        # минус 1 аура -> в сброс как aura_back
        if areas_auras[current_player] > 0:
            areas_auras[current_player] -= 1
            delete_pile.append("aura_back")
        return

    # Защитник обычного цвета
    if atk_color == "purple":
        # превращаем потерю в Ауру Тьмы
        # особый случай red с капитаном: сперва пытаемся снять обычную карту
        if def_t == "red" and captain_pos == current_player and areas_counts[current_player].get("red", 0) <= 0:
            return  # снять нечего (капитан неуязвим)
        removed = remove_one_from_area(areas_counts[current_player], areas_blue[current_player], def_t)
        if removed is None:
            return
        areas_auras[current_player] += 1
        # ничего в сброс
    else:
        # обычная потеря: -1 карточка защитника -> в сброс
        if def_t == "red" and captain_pos == current_player and areas_counts[current_player].get("red", 0) <= 0:
            return  # нечего снимать
        removed = remove_one_from_area(areas_counts[current_player], areas_blue[current_player], def_t)
        if removed is not None:
            delete_pile.append(removed)


def squad_size_in_area(color: str, area_idx: int,
                       areas_counts: List[AreaCount],
                       areas_blue: List[List[int]],
                       captain_pos: Optional[int]) -> int:
    sz = 0
    if color == "blue":
        sz += len(areas_blue[area_idx])
    else:
        sz += areas_counts[area_idx].get(color, 0)
    if color == "red" and captain_pos == area_idx:
        sz += 1
    return sz


# =========================
# Проверки досрочных побед
# =========================

def check_green_win(areas_counts: List[AreaCount]) -> bool:
    for ac in areas_counts:
        if ac.get("green", 0) >= 5:
            return True
    return False


def check_yellow_win_global(areas_counts: List[AreaCount]) -> bool:
    # во всех Измерениях >=1 жёлтой и сумма >=5
    if not areas_counts:
        return False
    if any(ac.get("yellow", 0) <= 0 for ac in areas_counts):
        return False
    total = sum(ac.get("yellow", 0) for ac in areas_counts)
    return total >= 5


def check_blue_win_42(areas_blue: List[List[int]]) -> bool:
    for vals in areas_blue:
        if sum(vals) == 42 and len(vals) > 0:
            return True
    return False


def check_epic_early_win(
    areas_counts: List[AreaCount],
    areas_blue: List[List[int]],
    areas_auras: List[int],  # не нужно для проверок, но оставлено для симметрии
    players_factions: List[str],
    spiral: List[str]
) -> Optional[str]:
    # Приоритет: время первого срабатывания. Проверяем в порядке G -> Y -> B
    # (Красный не имеет мгновенной победы; Фиолетовый — только по подсчёту)
    if "green" in players_factions and check_green_win(areas_counts):
        return "green"
    if "yellow" in players_factions and check_yellow_win_global(areas_counts):
        return "yellow"
    if "blue" in players_factions and check_blue_win_42(areas_blue):
        return "blue"
    return None


# =========================
# Подсчёт результата (финал)
# =========================

def score_game_epic(
    areas_counts: List[AreaCount],
    areas_blue: List[List[int]],
    areas_auras: List[int],
    players_factions: List[str],
    spiral: List[str],
    captain_pos: Optional[int]
) -> str:
    total_by_color = Counter()

    for i in range(len(areas_counts)):
        # обычные цвета
        for c, cnt in areas_counts[i].items():
            total_by_color[c] += cnt
        # синие — по количеству карт
        total_by_color["blue"] += len(areas_blue[i])
        # капитан даёт +1 к красным
        if captain_pos == i:
            total_by_color["red"] += 1
        # ауры добавляются к фиолетовым
        total_by_color["purple"] += areas_auras[i]

    contenders = set(players_factions)
    max_cnt = max((total_by_color.get(c, 0) for c in contenders), default=0)
    tied = [c for c in contenders if total_by_color.get(c, 0) == max_cnt]

    if len(tied) == 1:
        return tied[0]

    # тай-брейк по Спирали
    for f in tied:
        if all((f == g) or beats(f, g, spiral) for g in tied):
            return f

    return random.choice(tied)


# =========================
# Одна партия (Epic)
# =========================

def play_one_game_epic(num_players: int) -> Tuple[str, List[str]]:
    players = random_assign_players(num_players)

    deck = init_deck_epic()
    delete_pile: List[str] = []

    # Руки и Измерения
    hands: List[Hand] = [Counter() for _ in range(num_players)]
    areas_counts: List[AreaCount] = [Counter() for _ in range(num_players)]
    areas_blue: List[List[int]] = [[] for _ in range(num_players)]
    areas_auras: List[int] = [0 for _ in range(num_players)]

    spiral = make_spiral()

    # Раздача по 4 карты каждому
    for i in range(num_players):
        for _ in range(TARGET_HAND):
            if not deck:
                break
            card = deck.pop()
            hands[i][card] += 1

    first = random.randrange(num_players)
    turn_queue: deque[int] = deque(range(first, first + num_players))

    # Капитан Сила
    captain_pos: Optional[int] = None

    # Флаги финального хода
    final_turn_player: Optional[int] = None
    final_turn_scheduled = False
    final_turn_active = False

    def schedule_final_if_needed(last_taker: Optional[int]) -> None:
        nonlocal final_turn_player, final_turn_scheduled
        if last_taker is not None and not final_turn_scheduled:
            final_turn_player = last_taker
            final_turn_scheduled = True

    while True:
        current = turn_queue[0] % num_players

        # 1) Битва Измерений
        phase_battle_of_dimensions(hands, areas_counts, areas_blue, delete_pile, spiral)
        w = check_epic_early_win(areas_counts, areas_blue, areas_auras, players, spiral)
        if w is not None:
            return w, players

        # 2) Усиление
        captain_pos = phase_reinforcement(current, hands, areas_counts, areas_blue, players, captain_pos)
        w = check_epic_early_win(areas_counts, areas_blue, areas_auras, players, spiral)
        if w is not None:
            return w, players

        # 3) Перемещение или аномалия
        captain_pos = phase_movement_or_anomaly(
            current_player=current,
            hands=hands,
            areas_counts=areas_counts,
            areas_blue=areas_blue,
            areas_auras=areas_auras,
            players_factions=players,
            spiral=spiral,
            deck=deck,
            delete_pile=delete_pile,
            turn_queue=turn_queue,
            captain_pos=captain_pos,
        )
        w = check_epic_early_win(areas_counts, areas_blue, areas_auras, players, spiral)
        if w is not None:
            return w, players

        # 4) Атака
        phase_attack(current, areas_counts, areas_blue, areas_auras, spiral, captain_pos, delete_pile)
        w = check_epic_early_win(areas_counts, areas_blue, areas_auras, players, spiral)
        if w is not None:
            return w, players

        # 5) Восстановление
        last_taker = deal_cards(deck, hands, TARGET_HAND, start_idx=current)
        schedule_final_if_needed(last_taker)
        w = check_epic_early_win(areas_counts, areas_blue, areas_auras, players, spiral)
        if w is not None:
            return w, players

        # Планирование следующего хода
        if final_turn_scheduled and not final_turn_active:
            # следующим идёт тот, кто взял последнюю карту
            turn_queue = deque([final_turn_player if final_turn_player is not None else current])
            final_turn_active = True
        else:
            turn_queue.rotate(-1)

        # если только что завершили финальный ход — выходим к подсчёту
        if final_turn_active and current == final_turn_player:
            break

    # Подсчёт по Epic
    winner_color = score_game_epic(areas_counts, areas_blue, areas_auras, players, spiral, captain_pos)
    return winner_color, players


# =========================
# Серия симуляций (условные вероятности)
# =========================

def run_simulations_epic(num_players: int, runs: int, seed: int) -> Dict[str, float]:
    random.seed(seed)
    wins = Counter()
    participates = Counter()

    for _ in range(runs):
        w, participants = play_one_game_epic(num_players)
        wins[w] += 1
        for f in participants:
            participates[f] += 1

    probs: Dict[str, float] = {}
    for f in FRACTIONS:
        denom = participates[f]
        probs[f] = (wins[f] / denom) if denom > 0 else 0.0
    return probs


if __name__ == "__main__":
    probs = run_simulations_epic(num_players=CNT_PLAYERS, runs=CNT_SIMULATIONS, seed=RANDOM_SEED)
    print(f"Epic N={CNT_PLAYERS} (условные вероятности) ->", {k: round(v, 4) for k, v in probs.items()})

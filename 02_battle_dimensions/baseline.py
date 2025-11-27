# -*- coding: utf-8 -*-
"""
Симулятор "Битва Измерений"
Режим Baseline
- базовые правила
- рандомные ходы

Изменения:
- Корректно реализован конец игры: игрок, который взял последнюю карту из колоды
  (в фазе Восстановления), получает ровно один дополнительный полный ход, после
  чего партия немедленно завершается, даже если на руках остались карты.
- Переписан подсчёт результата симуляций: считаем УСЛОВНУЮ вероятность победы
  для каждой фракции = победы / число партий, в которых фракция УЧАСТВОВАЛА.
  Для этого play_one_game возвращает также список фракций-участников партии.
"""

from __future__ import annotations

import random
from collections import Counter, deque
from typing import List, Tuple, Dict, Optional

# =========================
# Константы
# =========================

FRACTIONS = ["red", "green", "yellow", "blue", "purple"]
CNT_PLAYERS = 5
CNT_SIMULATIONS = 1_000_000
RANDOM_SEED = 42

# Перечень возможных аномалий (в базовой партии в колоду добавляется РОВНО одна случайная)
ANOMALIES = [
    "anom_quantum_entanglement",  # Квантовая запутанность (перестройка Спирали Сил)
    "anom_wormhole",              # Кротовая нора (перемещение отряда)
    "anom_black_hole",            # Чёрная Дыра (уничтожение отряда)
    "anom_big_bang",              # Большой Взрыв (вернуть сброс в колоду)
    "anom_time_loop"              # Временная Петля (дополнительный ход)
]

# Целевое число карт в руке по правилам
TARGET_HAND = 4

# =========================
# Типы / Алиасы
# =========================

Hand = Counter      # счётчик карт в руке игрока
Area = Counter      # счётчик карт в Измерении игрока
Deck = List[str]    # список карт (простые строки)

# =========================
# Функции
# =========================

def init_deck() -> Deck:
    """
    Сформировать стартовую колоду:
    - по 11 карт каждого цвета,
    - +1 случайная аномалия.
    """
    deck: Deck = []
    for f in FRACTIONS:
        deck.extend([f] * 11)
    deck.append(random.choice(ANOMALIES))
    random.shuffle(deck)
    return deck


def deal_cards(deck: Deck, hands: List[Hand], target: int, start_idx: int) -> Optional[int]:
    """
    Добор карт до target в конце хода:
    - сначала ходящий, затем по часовой стрелке.
    Возвращает индекс игрока, который взял ПОСЛЕДНЮЮ карту из колоды (если таковая была взята
    в процессе добора). Иначе возвращает None.
    """
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
                # Эта раздача исчерпала колоду -> запоминаем игрока
                return i
    return last_card_taker


def random_assign_players(n: int) -> List[str]:
    """Случайное присвоение Сущностей (уникальные фракции на игроков)."""
    return random.sample(FRACTIONS, n)


def make_spiral() -> List[str]:
    """
    Случайная Спираль Сил (циклический порядок 5 фракций).
    Пример: ['green','blue','purple','red','yellow']
    """
    spiral = FRACTIONS[:]
    random.shuffle(spiral)
    return spiral


def beats(a: str, b: str, spiral: List[str]) -> bool:
    """
    Правило доминирования по Спирали Сил:
    a побеждает b, если a стоит НЕПОСРЕДСТВЕННО перед b в цикле.
    """
    idx = {c: i for i, c in enumerate(spiral)}
    return (idx[a] + 1) % len(spiral) == idx[b]


def first_wins_among(colors: List[str], spiral: List[str]) -> List[str]:
    """
    Определить победителей в фазе "Битва Измерений".
      - если все выбрали один цвет -> все победители;
      - иначе победители — те, кто бьёт хоть одного и сам не побеждён никем из присутствующих;
      - если цикл — победителей нет.
    """
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


def pick_random_squad(area: Area, exclude_color: Optional[str]) -> Optional[str]:
    """Выбрать случайный цвет-отряд из данного Измерения, исключая exclude_color."""
    options = [c for c, cnt in area.items() if cnt > 0 and c != exclude_color and c in FRACTIONS]
    return random.choice(options) if options else None


def move_one_card(src: Area, dst: Area, color: str) -> None:
    """Переместить 1 карту указанного цвета из src в dst, если возможно."""
    if color and src.get(color, 0) > 0:
        src[color] -= 1
        if src[color] <= 0:
            del src[color]
        dst[color] += 1


# =========================
# Аномалии
# =========================

def play_anom_quantum_entanglement(spiral: List[str]) -> List[str]:
    if len(spiral) < 2:
        return spiral
    i, j = random.sample(range(len(spiral)), 2)
    spiral[i], spiral[j] = spiral[j], spiral[i]
    return spiral


def play_anom_wormhole(areas: List[Area]) -> None:
    squads = [(pi, c) for pi in range(len(areas)) for c, cnt in areas[pi].items()
              if cnt > 0 and c in FRACTIONS]
    if not squads:
        return
    pi, color = random.choice(squads)
    dsts = [k for k in range(len(areas)) if k != pi]
    if not dsts:
        return
    dst = random.choice(dsts)
    cnt = areas[pi][color]
    areas[pi][color] = 0
    del areas[pi][color]
    areas[dst][color] += cnt


def play_anom_black_hole(areas: List[Area], delete_pile: List[str]) -> None:
    squads = [(pi, c) for pi in range(len(areas)) for c, cnt in areas[pi].items()
              if cnt > 0 and c in FRACTIONS]
    if not squads:
        return
    pi, color = random.choice(squads)
    cnt = areas[pi][color]
    for _ in range(cnt):
        delete_pile.append(color)
    del areas[pi][color]


def play_anom_big_bang(deck: Deck, delete_pile: List[str]) -> None:
    if not delete_pile:
        return
    deck.extend(delete_pile)
    delete_pile.clear()
    random.shuffle(deck)


def play_anom_time_loop(turn_queue: deque[int], current_player: int) -> None:
    turn_queue.appendleft(current_player)


def try_play_anomaly(
    player_hand: Hand,
    spiral: List[str],
    areas: List[Area],
    deck: Deck,
    delete_pile: List[str],
    turn_queue: deque[int],
    current_player: int
) -> None:
    anoms = [k for k in list(player_hand.keys()) if k in ANOMALIES and player_hand[k] > 0]
    if not anoms:
        return
    chosen = random.choice(anoms)

    if chosen == "anom_quantum_entanglement":
        spiral[:] = play_anom_quantum_entanglement(spiral)
    elif chosen == "anom_wormhole":
        play_anom_wormhole(areas)
    elif chosen == "anom_black_hole":
        play_anom_black_hole(areas, delete_pile)
    elif chosen == "anom_big_bang":
        play_anom_big_bang(deck, delete_pile)
    elif chosen == "anom_time_loop":
        play_anom_time_loop(turn_queue, current_player)

    player_hand[chosen] -= 1
    if player_hand[chosen] <= 0:
        del player_hand[chosen]
    delete_pile.append(chosen)


# =========================
# Фазы хода
# =========================

def phase_battle_of_dimensions(
    hands: List[Hand],
    areas: List[Area],
    delete_pile: List[str],
    spiral: List[str]
) -> None:
    n = len(hands)
    plays: List[Tuple[int, Optional[str]]] = []

    for i in range(n):
        opts = [c for c, cnt in hands[i].items() if cnt > 0 and c in FRACTIONS]
        if not opts:
            plays.append((i, None))
            continue
        chosen = random.choice(opts)
        hands[i][chosen] -= 1
        if hands[i][chosen] <= 0:
            del hands[i][chosen]
        plays.append((i, chosen))

    colors = [c for _, c in plays if c is not None]
    if not colors:
        return

    winners = first_wins_among(colors, spiral)

    if not winners:
        for _, c in plays:
            if c is not None:
                delete_pile.append(c)
        return

    for i, c in plays:
        if c is None:
            continue
        if c in winners:
            areas[i][c] += 1
        else:
            delete_pile.append(c)


def phase_reinforcement(
    current_player: int,
    hands: List[Hand],
    areas: List[Area]
) -> None:
    hand = hands[current_player]
    opts = [c for c, cnt in hand.items() if cnt > 0 and c in FRACTIONS]
    if not opts:
        return
    chosen = random.choice(opts)
    hand[chosen] -= 1
    if hand[chosen] <= 0:
        del hand[chosen]

    dst = random.randrange(len(areas))
    areas[dst][chosen] += 1


def phase_movement_or_anomaly(
    current_player: int,
    hands: List[Hand],
    areas: List[Area],
    spiral: List[str],
    deck: Deck,
    delete_pile: List[str],
    turn_queue: deque[int]
) -> None:
    if random.random() < 0.5:
        try_play_anomaly(
            player_hand=hands[current_player],
            spiral=spiral,
            areas=areas,
            deck=deck,
            delete_pile=delete_pile,
            turn_queue=turn_queue,
            current_player=current_player
        )
        return

    candidates = [i for i, a in enumerate(areas) if sum(a.values()) > 0]
    if not candidates:
        return
    src_idx = random.choice(candidates)

    src_area = areas[src_idx]
    color = pick_random_squad(src_area, exclude_color=None)
    if color is None:
        return

    dst_idx = random.randrange(len(areas))
    if dst_idx == src_idx:
        return

    move_one_card(src_area, areas[dst_idx], color)


def phase_attack(
    current_player: int,
    areas: List[Area],
    spiral: List[str],
    delete_pile: List[str]
) -> None:
    area = areas[current_player]
    attackers = [c for c, cnt in area.items() if cnt > 0 and c in FRACTIONS]
    if not attackers:
        return
    atk_color = random.choice(attackers)

    targets = [c for c, cnt in area.items() if cnt > 0 and c in FRACTIONS and c != atk_color]
    if not targets:
        return
    def_color = random.choice(targets)

    atk_cnt = area.get(atk_color, 0)
    def_cnt = area.get(def_color, 0)

    atk_wins = (atk_cnt > def_cnt) or beats(atk_color, def_color, spiral)
    if atk_wins:
        area[def_color] -= 1
        delete_pile.append(def_color)
        if area[def_color] <= 0:
            del area[def_color]


def phase_recover(
    start_player: int,
    hands: List[Hand],
    deck: Deck
) -> Optional[int]:
    """
    5) Восстановление — добор до 4: сначала ходящий, затем по кругу.
    Возвращает индекс игрока, который взял ПОСЛЕДНЮЮ карту из колоды,
    если это произошло в этой фазе. Иначе None.
    """
    return deal_cards(deck, hands, TARGET_HAND, start_idx=start_player)


# =========================
# Подсчёт результата партии
# =========================

def tiebreak_by_spiral(factions: List[str], spiral: List[str]) -> Optional[str]:
    for f in factions:
        if all((f == g) or beats(f, g, spiral) for g in factions):
            return f
    return None


def score_game(areas: List[Area], players_factions: List[str], spiral: List[str]) -> str:
    """
    Победитель партии среди УЧАСТВУЮЩИХ фракций:
    - суммируем по всем Измерениям карты каждого цвета,
    - оставляем только цвета, которые соответствуют Сущностям игроков,
    - берём максимум; при равенстве — tie-break по Спирали, иначе случайно.
    Возвращает цвет-фракцию победителя (из players_factions).
    """
    total_by_color = Counter()
    for area in areas:
        for c, cnt in area.items():
            if c in FRACTIONS:
                total_by_color[c] += cnt

    contenders = set(players_factions)
    if not contenders:
        return random.choice(FRACTIONS)

    max_cnt = max((total_by_color.get(c, 0) for c in contenders), default=0)
    tied = [c for c in contenders if total_by_color.get(c, 0) == max_cnt]

    if len(tied) == 1:
        return tied[0]

    tb = tiebreak_by_spiral(tied, spiral)
    if tb is not None:
        return tb

    return random.choice(tied)


# =========================
# Одна партия
# =========================

def play_one_game(num_players: int) -> Tuple[str, List[str]]:
    """
    Сымитировать одну базовую партию с рандомными решениями.
    Возвращает кортеж: (цвет-фракция победителя, список фракций-участников партии).
    """
    # 1) Раздача Сущностей (уникальные)
    players = random_assign_players(num_players)

    # 2) Колода / Сброс
    deck = init_deck()
    delete_pile: List[str] = []

    # 3) Руки и Измерения
    hands: List[Hand] = [Counter() for _ in range(num_players)]
    areas: List[Area] = [Counter() for _ in range(num_players)]

    # 4) Спираль Сил
    spiral = make_spiral()

    # 5) Раздача по 4 карты каждому
    for i in range(num_players):
        for _ in range(TARGET_HAND):
            if not deck:
                break
            card = deck.pop()
            hands[i][card] += 1

    # 6) Первый игрок (в правилах — КНБ; здесь — случайно)
    first = random.randrange(num_players)

    # Очередь ходов
    turn_queue: deque[int] = deque(range(first, first + num_players))

    # Флаги финального хода
    final_turn_player: Optional[int] = None
    final_turn_scheduled = False
    final_turn_active = False
    final_turn_done = False

    # Главный цикл партии
    while True:
        current = turn_queue[0] % num_players

        # Фаза 1: Битва Измерений (все игроки участвуют)
        phase_battle_of_dimensions(hands, areas, delete_pile, spiral)

        # Фаза 2: Усиление
        phase_reinforcement(current, hands, areas)

        # Фаза 3: Перемещение или аномалия
        phase_movement_or_anomaly(
            current_player=current,
            hands=hands,
            areas=areas,
            spiral=spiral,
            deck=deck,
            delete_pile=delete_pile,
            turn_queue=turn_queue
        )

        # Фаза 4: Атака (из своего Измерения)
        phase_attack(current, areas, spiral, delete_pile)

        # Фаза 5: Восстановление (добор до 4 карт)
        last_taker = phase_recover(current, hands, deck)
        if last_taker is not None and not final_turn_scheduled:
            final_turn_player = last_taker
            final_turn_scheduled = True

        # Завершение текущего хода -> планирование следующего
        if final_turn_scheduled and not final_turn_active:
            # Следующим ходит тот, кто взял последнюю карту
            turn_queue = deque([final_turn_player if final_turn_player is not None else current])
            final_turn_active = True
        else:
            # Обычный переход хода
            turn_queue.rotate(-1)

        # Если только что завершили финальный ход — выходим к подсчёту
        if final_turn_active and current == final_turn_player:
            final_turn_done = True

        if final_turn_done:
            break

        # Страховочная остановка
        if not deck and final_turn_scheduled and final_turn_done:
            break

    # Подсчёт победителя среди УЧАСТНИКОВ
    winner_color = score_game(areas, players, spiral)
    return winner_color, players


# =========================
# Симуляции
# =========================

def run_simulations(num_players: int, runs: int, seed: int) -> Dict[str, float]:
    """
    Возвращает УСЛОВНЫЕ вероятности побед для каждой фракции:
    P(победа | фракция участвует) = wins[f] / participates[f].
    Если фракция не участвовала ни в одной партии — вероятность 0.0.
    """
    random.seed(seed)
    wins = Counter()
    participates = Counter()

    for _ in range(runs):
        winner, participants = play_one_game(num_players)
        wins[winner] += 1
        for f in participants:
            participates[f] += 1

    probs: Dict[str, float] = {}
    for f in FRACTIONS:
        denom = participates[f]
        probs[f] = (wins[f] / denom) if denom > 0 else 0.0

    return probs


if __name__ == "__main__":
    probs = run_simulations(num_players=CNT_PLAYERS, runs=CNT_SIMULATIONS, seed=RANDOM_SEED)
    print(f"N={CNT_PLAYERS} (условные вероятности) ->", {k: round(v, 4) for k, v in probs.items()})

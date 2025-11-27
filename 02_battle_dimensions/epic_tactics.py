# -*- coding: utf-8 -*-
"""
Симулятор "Битва Измерений" — Epic Tactics
- Эпический режим (особые механики фракций)
- Тактические эвристики вместо рандома
- Подсчёт УСЛОВНЫХ вероятностей побед
"""

from __future__ import annotations

import random
from collections import Counter, deque
from typing import List, Dict, Tuple, Optional

# =========================
# Константы / параметры
# =========================

FRACTIONS = ["red", "green", "yellow", "blue", "purple"]
BLUE_VALUES = [2, 3, 5, 7, 11, 13, 17, 17, 19, 23, 29]

ANOMALIES = [
    "anom_quantum_entanglement",  # перестановка спирали
    "anom_wormhole",              # перенос отряда
    "anom_black_hole",            # уничтожение отряда
    "anom_big_bang",              # вернуть сброс в колоду
    "anom_time_loop"              # доп. ход
]

TARGET_HAND = 4
RANDOM_SEED = 42

# Пороги «опасности» для тактики
BLUE_DANGER_RANGE = range(35, 42)  # 35..41
YELLOW_NEED_COVERAGE = True
GREEN_NEAR_WIN = 4

# =========================
# Типы
# =========================

Card = str          # 'red', 'green', 'yellow', 'purple', 'blue#17', 'anom_*'
Deck = List[Card]
Hand = Counter      # Counter[Card, int]

class AreaState:
    """
    Состояние одного Измерения:
    - counts: обычные цвета (кроме blue) -> количество
    - blue_values: список числовых значений синих карт в этом измерении
    - auras: количество аур тьмы (фиолетовые «тени»), не цвет
    """
    __slots__ = ("counts", "blue_values", "auras")

    def __init__(self) -> None:
        self.counts: Counter = Counter()
        self.blue_values: List[int] = []
        self.auras: int = 0


# =========================
# Вспомогательные функции
# =========================

def is_color(card: Card, color: str) -> bool:
    if color == "blue":
        return card.startswith("blue#")
    return card == color


def card_color(card: Card) -> Optional[str]:
    if card in ("red", "green", "yellow", "purple"):
        return card
    if card.startswith("blue#"):
        return "blue"
    if card.startswith("anom_"):
        return None
    return None


def blue_value(card: Card) -> Optional[int]:
    if card.startswith("blue#"):
        return int(card.split("#", 1)[1])
    return None


def make_spiral(rng: random.Random) -> List[str]:
    s = FRACTIONS[:]
    rng.shuffle(s)
    return s


def beats(a: str, b: str, spiral: List[str]) -> bool:
    idx = {c: i for i, c in enumerate(spiral)}
    return (idx[a] + 1) % len(spiral) == idx[b]


def init_deck(rng: random.Random) -> Deck:
    deck: Deck = []
    # red, green, yellow, purple — по 11 неразличимых
    for c in ("red", "green", "yellow", "purple"):
        deck.extend([c] * 11)
    # blue — 11 различимых
    for v in BLUE_VALUES:
        deck.append(f"blue#{v}")
    # +1 случайная аномалия
    deck.append(rng.choice(ANOMALIES))
    rng.shuffle(deck)
    return deck


def random_assign_players(n: int, rng: random.Random) -> List[str]:
    return rng.sample(FRACTIONS, n)


def total_by_color(areas: List[AreaState], captain_loc: Optional[int]) -> Dict[str, int]:
    """Глобальные тоталы по цветам (для тактики атаки лидера)."""
    tot = Counter()
    for i, a in enumerate(areas):
        tot["green"] += a.counts.get("green", 0)
        tot["yellow"] += a.counts.get("yellow", 0)
        tot["red"] += a.counts.get("red", 0)
        tot["purple"] += a.counts.get("purple", 0)
        tot["blue"] += len(a.blue_values)
        # учёт аур к фиолетовым при выборе лидера
        tot["purple_with_auras"] += a.counts.get("purple", 0) + a.auras
        if captain_loc is not None and captain_loc == i:
            tot["red"] += 1
            tot["purple_with_auras"]  # не влияет
    return tot


def check_green_instant(areas: List[AreaState]) -> bool:
    return any(a.counts.get("green", 0) >= 5 for a in areas)


def check_yellow_instant(areas: List[AreaState]) -> bool:
    # во всех Измерениях >=1 жёлтой + суммарно >=5
    if not areas:
        return False
    if any(a.counts.get("yellow", 0) < 1 for a in areas):
        return False
    total_y = sum(a.counts.get("yellow", 0) for a in areas)
    return total_y >= 5


def check_blue_instant(areas: List[AreaState]) -> bool:
    for a in areas:
        if a.blue_values and sum(a.blue_values) == 42:
            return True
    return False


def first_wins_among(colors: List[str], spiral: List[str]) -> List[str]:
    uniq = set(colors)
    if len(uniq) == 1:
        return list(uniq)
    winners = []
    for c in uniq:
        beats_some = any(beats(c, d, spiral) for d in uniq if d != c)
        lost_some = any(beats(d, c, spiral) for d in uniq if d != c)
        if beats_some and not lost_some:
            winners.append(c)
    return winners


def tiebreak_by_spiral(cands: List[str], spiral: List[str]) -> Optional[str]:
    for f in cands:
        if all((f == g) or beats(f, g, spiral) for g in cands):
            return f
    return None


# =========================
# Работа с областями
# =========================

def place_card_in_area(area: AreaState, card: Card) -> None:
    col = card_color(card)
    if col is None:
        return
    if col == "blue":
        area.blue_values.append(blue_value(card))
    else:
        area.counts[col] += 1


def remove_one_from_area(area: AreaState, color: str) -> Optional[Card]:
    """Снять 1 карту цвета из области; вернуть «что сняли» (для сброса)."""
    if color == "blue":
        if area.blue_values:
            val = area.blue_values.pop()
            return f"blue#{val}"
        return None
    cnt = area.counts.get(color, 0)
    if cnt > 0:
        area.counts[color] -= 1
        if area.counts[color] <= 0:
            del area.counts[color]
        return color
    return None


def area_color_size(area: AreaState, color: str, captain_here: bool) -> int:
    if color == "blue":
        return len(area.blue_values)
    if color == "red":
        return area.counts.get("red", 0) + (1 if captain_here else 0)
    return area.counts.get(color, 0)


# =========================
# Аномалии (с учётом Epic)
# =========================

def anom_quantum_entanglement(spiral: List[str], rng: random.Random) -> None:
    i, j = rng.sample(range(len(spiral)), 2)
    spiral[i], spiral[j] = spiral[j], spiral[i]


def anom_wormhole(
    areas: List[AreaState],
    captain_loc: Optional[int],
    rng: random.Random
) -> None:
    # отряды, которые можно переносить: любой цвет, кроме аур, и кроме капитана
    squads: List[Tuple[int, str]] = []
    for i, a in enumerate(areas):
        for c in ("red", "green", "yellow", "purple"):
            if a.counts.get(c, 0) > 0:
                # для red отряд переносим, но капитан остаётся (если он здесь)
                squads.append((i, c))
        if a.blue_values:
            squads.append((i, "blue"))
    if not squads:
        return
    i, color = rng.choice(squads)
    dsts = [k for k in range(len(areas)) if k != i]
    if not dsts:
        return
    dst = rng.choice(dsts)

    # перенести ВСЁ количество карт цвета из i -> dst
    # исключение: капитан не переносится
    if color == "blue":
        values = areas[i].blue_values[:]
        areas[i].blue_values.clear()
        areas[dst].blue_values.extend(values)
        return

    move_cnt = areas[i].counts.get(color, 0)
    if move_cnt <= 0:
        return
    # для red вычесть «обычные», капитан останется
    if color == "red" and captain_loc is not None and captain_loc == i:
        # перенесём только обычные карты
        pass
    # перенос
    areas[i].counts[color] -= move_cnt
    if areas[i].counts[color] <= 0:
        areas[i].counts.pop(color, None)
    areas[dst].counts[color] += move_cnt
    # если капитан был в i — он остаётся


def anom_black_hole(
    areas: List[AreaState],
    delete_pile: List[Card],
    captain_loc: Optional[int],
    rng: random.Random
) -> None:
    # выбрать произвольный отряд и удалить его целиком (ауры можно удалять)
    # но капитан не удаляется
    options: List[Tuple[int, str]] = []
    for i, a in enumerate(areas):
        for c in ("red", "green", "yellow", "purple"):
            if a.counts.get(c, 0) > 0:
                options.append((i, c))
        if a.blue_values:
            options.append((i, "blue"))
        if a.auras > 0:
            options.append((i, "aura"))
    if not options:
        return
    i, color = rng.choice(options)

    if color == "aura":
        # убрать все ауры в сброс
        for _ in range(areas[i].auras):
            delete_pile.append("aura_back")
        areas[i].auras = 0
        return

    if color == "blue":
        while areas[i].blue_values:
            val = areas[i].blue_values.pop()
            delete_pile.append(f"blue#{val}")
        return

    if color == "red":
        # капитан не удаляется
        cap_here = (captain_loc == i)
        cnt = areas[i].counts.get("red", 0)
        # удалить все обычные
        for _ in range(cnt):
            delete_pile.append("red")
        areas[i].counts.pop("red", None)
        # капитан остаётся как +1 к размеру, но физически это флаг
        return

    # обычный цвет: снести все
    cnt = areas[i].counts.get(color, 0)
    for _ in range(cnt):
        delete_pile.append(color)
    areas[i].counts.pop(color, None)


def anom_big_bang(deck: Deck, delete_pile: List[Card], rng: random.Random) -> None:
    # вернуть ТОЛЬКО цветные карты (включая blue#v), ауры не возвращаем
    returned: List[Card] = []
    keep: List[Card] = []
    for c in delete_pile:
        if c.startswith("blue#") or c in ("red", "green", "yellow", "purple"):
            returned.append(c)
        # ауры и аномалии — остаются в сбросе
        elif c.startswith("anom_") or c == "aura_back":
            keep.append(c)
        else:
            keep.append(c)
    deck.extend(returned)
    delete_pile.clear()
    delete_pile.extend(keep)
    rng.shuffle(deck)


def anom_time_loop(turn_q: deque[int], current: int) -> None:
    turn_q.appendleft(current)


# =========================
# Эвристики выбора
# =========================

def find_blue_best_add(target_sum: int, values_in_hand: List[int]) -> Optional[int]:
    """Выбрать значение, максимизирующее сумму <= 42 (или ==42 если возможно)."""
    if not values_in_hand:
        return None
    best = None
    best_sum = -1
    for v in values_in_hand:
        s = target_sum + v
        if s == 42:
            return v
        if s < 42 and s > best_sum:
            best_sum = s
            best = v
    return best


def yellow_coverage_ok(areas: List[AreaState]) -> bool:
    return all(a.counts.get("yellow", 0) >= 1 for a in areas)


def choose_battle_card_tactical(
    player_idx: int,
    hands: List[Hand],
    areas: List[AreaState],
    players: List[str],
    spiral: List[str],
    captain_loc: Optional[int],
    rng: random.Random
) -> Optional[Card]:
    """Выбор карты для Битвы Измерений с простыми приоритетами."""
    hand = hands[player_idx]
    if not hand:
        return None

    # Разложим опции
    blue_vals = []
    options: List[Card] = []
    for c, cnt in hand.items():
        if cnt <= 0:
            continue
        if c.startswith("blue#"):
            blue_vals.extend([blue_value(c)] * cnt)
        elif c in ("red", "green", "yellow", "purple"):
            options.extend([c] * cnt)

    # Приоритеты по сущности игрока
    entity = players[player_idx]

    # Синий: если можем продвинуться к 42 в СВОЁМ измерении — сыграть blue
    if blue_vals:
        cur_sum = sum(areas[player_idx].blue_values)
        v = find_blue_best_add(cur_sum, blue_vals)
        if v is not None:
            return f"blue#{v}"

    # Зелёный: пушим зелёный
    if "green" in options:
        return "green"

    # Жёлтый: если покрытия нет — играем yellow
    if "yellow" in options and not yellow_coverage_ok(areas):
        return "yellow"

    # Фиолетовый: если в своём измерении есть чужие цели — можно purple
    if "purple" in options:
        has_targets = any(
            col != "purple" and (col == "blue" and areas[player_idx].blue_values or
                                 col != "blue" and areas[player_idx].counts.get(col, 0) > 0)
            for col in FRACTIONS if col != "purple"
        )
        if has_targets:
            return "purple"

    # Красный: нейтрально
    if "red" in options:
        return "red"

    # Иначе что есть, но не аномалия
    # (мы сюда не кладём аномалии)
    # Если остались только blue, но не нашли v — возьмём любую
    for c, cnt in hand.items():
        if c.startswith("blue#") and cnt > 0:
            return c
        if c in ("red", "green", "yellow", "purple") and cnt > 0:
            return c
    return None


def choose_reinforcement_tactical(
    current: int,
    hands: List[Hand],
    areas: List[AreaState],
    players: List[str],
    captain_avail_idx: Optional[int],
    captain_loc: Optional[int],
    rng: random.Random
) -> Tuple[Optional[Card], Optional[int], bool]:
    """
    Вернуть (card, dst_area, place_captain)
    - если place_captain=True -> игнорировать card и dst_area для карты
    """
    hand = hands[current]
    if not hand:
        return (None, None, False)

    entity = players[current]

    # Красный: шанс рано выложить капитана, если доступен
    if entity == "red" and captain_avail_idx == current and captain_loc is None:
        if rng.random() < 0.8:
            # кладём капитана в своё измерение с максимальным red
            best_dst = current
            best_sz = -1
            for i, a in enumerate(areas):
                sz = area_color_size(a, "red", captain_here=(captain_loc == i))
                if i == current and sz > best_sz:
                    best_sz = sz
                    best_dst = i
            return (None, best_dst, True)

    # Зелёный: усилять один стек в своём измерении
    if entity == "green" and hand.get("green", 0) > 0:
        return ("green", current, False)

    # Жёлтый: сначала построить покрытие, затем набрать сумму >=5
    if entity == "yellow" and hand.get("yellow", 0) > 0:
        if not yellow_coverage_ok(areas):
            # кинем туда, где нет жёлтой
            for i, a in enumerate(areas):
                if a.counts.get("yellow", 0) < 1:
                    return ("yellow", i, False)
        # покрытие есть — добираем до 5 в любое
        return ("yellow", current, False)

    # Синий: подобрать значение, продвигающее к 42 в ЛЮБОМ измерении (лучше своём)
    blue_vals = []
    for c, cnt in hand.items():
        if c.startswith("blue#") and cnt > 0:
            blue_vals.extend([blue_value(c)] * cnt)
    if entity == "blue" and blue_vals:
        # сначала своё измерение
        cur_sum = sum(areas[current].blue_values)
        v = find_blue_best_add(cur_sum, blue_vals)
        if v is None:
            # попробуем другие измерения
            best = None
            best_dst = None
            for i, a in enumerate(areas):
                s = sum(a.blue_values)
                vv = find_blue_best_add(s, blue_vals)
                if vv is None:
                    continue
                ss = s + vv
                if ss == 42:
                    return (f"blue#{vv}", i, False)
                if best is None or ss > best:
                    best = ss
                    best_dst = i
                    v = vv
            if v is not None and best_dst is not None:
                return (f"blue#{v}", best_dst, False)
        else:
            return (f"blue#{v}", current, False)

    # Фиолетовый: усилим там, где больше целей
    if entity == "purple" and hand.get("purple", 0) > 0:
        best_dst = current
        best_targets = -1
        for i, a in enumerate(areas):
            targets = (a.counts.get("red", 0) + a.counts.get("green", 0) +
                       a.counts.get("yellow", 0) + (len(a.blue_values)))
            if targets > best_targets:
                best_targets = targets
                best_dst = i
        return ("purple", best_dst, False)

    # Иначе — любая цветная карта в своё измерение
    for c in ("green", "yellow", "purple", "red"):
        if hand.get(c, 0) > 0:
            return (c, current, False)
    for c, cnt in hand.items():
        if c.startswith("blue#") and cnt > 0:
            return (c, current, False)

    return (None, None, False)


def choose_anomaly_or_move_tactical(
    current: int,
    hands: List[Hand],
    areas: List[AreaState],
    players: List[str],
    spiral: List[str],
    deck: Deck,
    delete_pile: List[Card],
    turn_q: deque[int],
    captain_loc: Optional[int],
    rng: random.Random
) -> None:
    """
    Сначала пытаемся разыграть «полезную» аномалию (по приоритетам),
    иначе — одно перемещение по целям.
    """
    hand = hands[current]
    # ---- Попытка аномалии
    # Составим список аномалий в руке
    anoms = [k for k, v in hand.items() if k in ANOMALIES and v > 0]

    def play_and_discard(anom: str):
        hand[anom] -= 1
        if hand[anom] <= 0:
            del hand[anom]
        delete_pile.append(anom)

    # Вспомогательные проверки «опасностей»
    # G: стек 4+, Y: покрытие, B: сумма 35..41
    def any_green_ge4() -> Optional[Tuple[int, int]]:
        for i, a in enumerate(areas):
            if a.counts.get("green", 0) >= GREEN_NEAR_WIN:
                return (i, a.counts["green"])
        return None

    def any_blue_danger() -> Optional[int]:
        for i, a in enumerate(areas):
            s = sum(a.blue_values)
            if s in BLUE_DANGER_RANGE:
                return i
        return None

    # BLACK_HOLE приоритеты
    if "anom_black_hole" in anoms:
        # 1) зелёный стек 5+
        for i, a in enumerate(areas):
            if a.counts.get("green", 0) >= 5:
                anom_black_hole(areas, delete_pile, captain_loc, rng)
                play_and_discard("anom_black_hole")
                return
        # 2) зелёный стек 4
        if any_green_ge4():
            anom_black_hole(areas, delete_pile, captain_loc, rng)
            play_and_discard("anom_black_hole")
            return
        # 3) жёлтое покрытие — выбить любую жёлтую
        if yellow_coverage_ok(areas):
            anom_black_hole(areas, delete_pile, captain_loc, rng)
            play_and_discard("anom_black_hole")
            return
        # 4) синий близко к 42
        if any_blue_danger() is not None:
            anom_black_hole(areas, delete_pile, captain_loc, rng)
            play_and_discard("anom_black_hole")
            return

    # WORMHOLE — собрать свои для досрочной / разорвать чужие
    if "anom_wormhole" in anoms:
        # упрощенно: просто применим, шанс 60%, иначе двинем картой
        if random.random() < 0.6:
            anom_wormhole(areas, captain_loc, rng)
            play_and_discard("anom_wormhole")
            return

    # QUANTUM — попробовать улучшить: применим с 50%
    if "anom_quantum_entanglement" in anoms and random.random() < 0.5:
        anom_quantum_entanglement(spiral, rng)
        play_and_discard("anom_quantum_entanglement")
        return

    # BIG_BANG — если в сбросе много наших карт (>=3)
    if "anom_big_bang" in anoms:
        my_col = players[current]
        mine_in_dump = sum(1 for c in delete_pile
                           if (my_col != "blue" and c == my_col) or
                           (my_col == "blue" and c.startswith("blue#")))
        if mine_in_dump >= 3 and len(deck) > 0:
            anom_big_bang(deck, delete_pile, rng)
            play_and_discard("anom_big_bang")
            return

    # TIME_LOOP — всегда хорошо
    if "anom_time_loop" in anoms:
        anom_time_loop(turn_q, current)
        play_and_discard("anom_time_loop")
        return

    # ---- Перемещение (если не аномалия)
    entity = players[current]
    # GREEN: слить в своё измерение
    if entity == "green":
        # найдем измерение с макс. green (целевое — своё)
        src_i = None
        for i, a in enumerate(areas):
            if i != current and a.counts.get("green", 0) > 0:
                src_i = i
                break
        if src_i is not None:
            areas[src_i].counts["green"] -= 1
            if areas[src_i].counts["green"] <= 0:
                areas[src_i].counts.pop("green", None)
            areas[current].counts["green"] += 1
            return

    # YELLOW: если нет покрытия — переместить жёлтую туда, где её нет
    if entity == "yellow" and not yellow_coverage_ok(areas):
        # найдём источник с >=2 yellow и приёмник без yellow
        src = next((i for i, a in enumerate(areas) if a.counts.get("yellow", 0) >= 2), None)
        dst = next((i for i, a in enumerate(areas) if a.counts.get("yellow", 0) < 1), None)
        if src is not None and dst is not None and src != dst:
            areas[src].counts["yellow"] -= 1
            if areas[src].counts["yellow"] <= 0:
                areas[src].counts.pop("yellow", None)
            areas[dst].counts["yellow"] += 1
            return

    # BLUE: перетащить синюю ближе к 42
    if entity == "blue":
        # найдём любое перетаскивание blue между измерениями, улучшающее max(sum)<=42
        best = None
        move = None
        for i, a in enumerate(areas):
            if not a.blue_values:
                continue
            val = a.blue_values[-1]
            for j, b in enumerate(areas):
                if i == j:
                    continue
                si = sum(a.blue_values)
                sj = sum(b.blue_values)
                new_si = si - val
                new_sj = sj + val
                score = (new_sj if new_sj <= 42 else -1)
                if best is None or score > best:
                    best = score
                    move = (i, j, val)
        if move:
            i, j, v = move
            # снять из i
            areas[i].blue_values.remove(v)
            # положить в j
            areas[j].blue_values.append(v)
            return

    # PURPLE: подтянуть к себе цель
    if entity == "purple":
        # перетащим 1 карту цели (не ауры) в своё измерение, если рядом есть
        # упрощённо: сдвинем любую green/yellow/blue из случайного в current
        for color in ("green", "yellow"):
            src = next((i for i, a in enumerate(areas)
                        if i != current and a.counts.get(color, 0) > 0), None)
            if src is not None:
                areas[src].counts[color] -= 1
                if areas[src].counts[color] <= 0:
                    areas[src].counts.pop(color, None)
                areas[current].counts[color] += 1
                return
        # blue
        src = next((i for i, a in enumerate(areas)
                    if i != current and a.blue_values), None)
        if src is not None:
            v = areas[src].blue_values.pop()
            areas[current].blue_values.append(v)
            return

    # иначе — ничего не делаем
    return


def choose_attack_tactical(
    current: int,
    areas: List[AreaState],
    players: List[str],
    spiral: List[str],
    captain_loc: Optional[int],
    rng: random.Random
) -> Optional[Tuple[str, str]]:
    """
    Выбрать (atk_color, def_color) для атаки из своего измерения.
    Приоритет: сорвать чужую досрочную -> бить лидера (кроме своей) -> «не бить своих».
    """
    area = areas[current]
    # Варианты атакующих цветов
    atk_colors = []
    for col in FRACTIONS:
        sz = area_color_size(area, col, captain_here=(captain_loc == current))
        if sz > 0:
            atk_colors.append(col)

    if not atk_colors:
        return None

    # Кандидаты целей (в том же измерении), другой цвет
    candidates = []
    for atk in atk_colors:
        for col in FRACTIONS:
            if col == atk:
                continue
            target_sz = area_color_size(area, col, captain_here=(captain_loc == current))
            if target_sz > 0:
                candidates.append((atk, col))

    if not candidates:
        return None

    # 1) Сорвать досрочные
    # зелёный стек 4
    for atk, col in candidates:
        if col == "green" and areas[current].counts.get("green", 0) >= GREEN_NEAR_WIN:
            if can_win_fight(area, atk, col, spiral, captain_loc == current):
                return (atk, col)
    # жёлтый: если в этом измерении жёлтая одна (чтобы сорвать покрытие)
    for atk, col in candidates:
        if col == "yellow" and areas[current].counts.get("yellow", 0) == 1:
            if can_win_fight(area, atk, col, spiral, captain_loc == current):
                return (atk, col)
    # синий: сумма близка к 42
    s = sum(area.blue_values)
    for atk, col in candidates:
        if col == "blue" and s in BLUE_DANGER_RANGE:
            if can_win_fight(area, atk, col, spiral, captain_loc == current):
                return (atk, col)

    # 2) Бить лидера (кроме своей сущности)
    totals = total_by_color(areas, captain_loc)
    # лидер учитывая ауры у purple
    leader = max(
        [(c, totals["purple_with_auras"] if c == "purple" else totals[c]) for c in FRACTIONS],
        key=lambda x: x[1]
    )[0]
    my_entity = players[current]
    target_pref = leader if leader != my_entity else None

    # Пытаемся выбрать цель с приоритетом на target_pref
    if target_pref:
        for atk, col in candidates:
            if col == target_pref and can_win_fight(area, atk, col, spiral, captain_loc == current):
                return (atk, col)

    # 3) Иначе любую выигрышную с «не бить своих» (если есть альтернатива)
    random.shuffle(candidates)
    # сначала без «своих»
    for atk, col in candidates:
        if col == my_entity:
            continue
        if can_win_fight(area, atk, col, spiral, captain_loc == current):
            return (atk, col)
    # затем любые выигрышные
    for atk, col in candidates:
        if can_win_fight(area, atk, col, spiral, captain_loc == current):
            return (atk, col)

    return None


def can_win_fight(area: AreaState, atk: str, dfn: str, spiral: List[str], captain_here: bool) -> bool:
    asz = area_color_size(area, atk, captain_here)
    dsz = area_color_size(area, dfn, captain_here)
    return (asz > dsz) or beats(atk, dfn, spiral)


# =========================
# Фазы хода
# =========================

def phase_battle(
    hands: List[Hand],
    areas: List[AreaState],
    players: List[str],
    spiral: List[str],
    captain_loc: Optional[int],
    rng: random.Random
) -> None:
    plays: List[Tuple[int, Optional[Card]]] = []
    for i in range(len(hands)):
        c = choose_battle_card_tactical(i, hands, areas, players, spiral, captain_loc, rng)
        if c is not None:
            hands[i][c] -= 1
            if hands[i][c] <= 0:
                del hands[i][c]
        plays.append((i, c))

    colors = [card_color(c) for _, c in plays if c is not None]
    colors = [c for c in colors if c is not None]
    if not colors:
        return
    winners = first_wins_among(colors, spiral)

    if not winners:
        # все сыгранные — в сброс
        return

    # победители — кладут карту в СВОИ Измерения; остальные — в сброс
    for i, c in plays:
        if c is None:
            continue
        col = card_color(c)
        if col in winners:
            place_card_in_area(areas[i], c)
        else:
            # проигравшие — ушли бы в Чёрную Дыру; сброс как факт нам не обязателен хранить
            pass


def phase_reinforcement(
    current: int,
    hands: List[Hand],
    areas: List[AreaState],
    players: List[str],
    captain_avail_idx: Optional[int],
    captain_loc: Optional[int],
    rng: random.Random
) -> Optional[int]:
    """
    Вернёт индекс измерения, куда положили капитана (если выложен), чтобы обновить captain_loc.
    """
    card, dst, place_captain = choose_reinforcement_tactical(
        current, hands, areas, players, captain_avail_idx, captain_loc, rng
    )
    if place_captain and dst is not None:
        return dst
    if card is None or dst is None:
        return None
    # положить карту:
    hands[current][card] -= 1
    if hands[current][card] <= 0:
        del hands[current][card]
    place_card_in_area(areas[dst], card)
    return None


def phase_move_or_anomaly(
    current: int,
    hands: List[Hand],
    areas: List[AreaState],
    players: List[str],
    spiral: List[str],
    deck: Deck,
    delete_pile: List[Card],
    turn_q: deque[int],
    captain_loc: Optional[int],
    rng: random.Random
) -> None:
    choose_anomaly_or_move_tactical(
        current, hands, areas, players, spiral, deck, delete_pile, turn_q, captain_loc, rng
    )


def phase_attack(
    current: int,
    areas: List[AreaState],
    players: List[str],
    spiral: List[str],
    captain_loc: Optional[int],
    delete_pile: List[Card],
    rng: random.Random
) -> None:
    choice = choose_attack_tactical(current, areas, players, spiral, captain_loc, rng)
    if not choice:
        return
    atk, dfn = choice
    a = areas[current]
    cap_here = (captain_loc == current)
    if not can_win_fight(a, atk, dfn, spiral, cap_here):
        return

    # исход боя: защитник теряет 1 карту
    if dfn == "purple":  # защищается фиолетовый обычный отряд
        lost = remove_one_from_area(a, "purple")
        if lost:
            # если атакующий фиолетовый — превращаем в ауру вместо сброса
            if atk == "purple":
                a.auras += 1
            else:
                delete_pile.append(lost)
    elif dfn == "blue":
        if a.blue_values:
            val = a.blue_values.pop()
            # кто атакующий?
            if atk == "purple":
                a.auras += 1
            else:
                delete_pile.append(f"blue#{val}")
    elif dfn == "red":
        # если в отряде есть капитан — теряется обычная red, капитан остаётся
        if a.counts.get("red", 0) > 0:
            a.counts["red"] -= 1
            if a.counts["red"] <= 0:
                a.counts.pop("red", None)
            if atk == "purple":
                a.auras += 1
            else:
                delete_pile.append("red")
        else:
            # одна «карта» — только капитан -> нечего терять
            pass
    else:
        # green/yellow
        if a.counts.get(dfn, 0) > 0:
            a.counts[dfn] -= 1
            if a.counts[dfn] <= 0:
                a.counts.pop(dfn, None)
            if atk == "purple":
                a.auras += 1
            else:
                delete_pile.append(dfn)


def deal_up_to(
    deck: Deck, hands: List[Hand], start_idx: int
) -> Tuple[Optional[int], bool]:
    """
    Добор до 4: сначала ходящий, затем по кругу.
    Возвращает (last_card_taker, deck_emptied_now)
    """
    n = len(hands)
    order = [(start_idx + k) % n for k in range(n)]
    last_taker: Optional[int] = None
    emptied_now = False
    for i in order:
        need = max(0, TARGET_HAND - sum(hands[i].values()))
        for _ in range(need):
            if not deck:
                emptied_now = True
                return (last_taker, emptied_now)
            card = deck.pop()
            last_taker = i
            hands[i][card] += 1
            if not deck:
                emptied_now = True
                return (last_taker, emptied_now)
    return (last_taker, emptied_now)


# =========================
# Подсчёт результата
# =========================

def score_game(
    areas: List[AreaState],
    players: List[str],
    spiral: List[str],
    captain_loc: Optional[int]
) -> str:
    total = Counter()
    for i, a in enumerate(areas):
        total["green"] += a.counts.get("green", 0)
        total["yellow"] += a.counts.get("yellow", 0)
        total["purple"] += a.counts.get("purple", 0) + a.auras
        total["red"] += a.counts.get("red", 0) + (1 if captain_loc == i else 0)
        total["blue"] += len(a.blue_values)

    contenders = set(players)
    max_cnt = max((total.get(c, 0) for c in contenders), default=0)
    tied = [c for c in contenders if total.get(c, 0) == max_cnt]
    if len(tied) == 1:
        return tied[0]
    tb = tiebreak_by_spiral(tied, spiral)
    if tb is not None:
        return tb
    return random.choice(tied)


# =========================
# Одна партия
# =========================

def play_one_game(num_players: int, rng: random.Random) -> Tuple[str, List[str]]:
    # 1) сущности
    players = random_assign_players(num_players, rng)

    # 2) колода/сброс
    deck = init_deck(rng)
    delete_pile: List[Card] = []

    # 3) руки/области
    hands: List[Hand] = [Counter() for _ in range(num_players)]
    areas: List[AreaState] = [AreaState() for _ in range(num_players)]

    # 4) спираль
    spiral = make_spiral(rng)

    # 5) стартовая раздача
    for i in range(num_players):
        need = TARGET_HAND
        for _ in range(need):
            if not deck:
                break
            hands[i][deck.pop()] += 1

    # 6) первый игрок
    first = rng.randrange(num_players)

    # Капитан Сила
    captain_avail_idx: Optional[int] = players.index("red") if "red" in players else None
    captain_loc: Optional[int] = None  # индекс измерения, где стоит капитан

    # Очередь
    turn_q: deque[int] = deque(range(first, first + num_players))

    # Флаг финального хода
    final_enqueued = False
    final_player: Optional[int] = None

    def check_instants() -> Optional[str]:
        # порядок «первое срабатывание по времени»
        if check_green_instant(areas):
            return "green"
        if check_yellow_instant(areas):
            return "yellow"
        if check_blue_instant(areas):
            return "blue"
        return None

    # Игровой цикл
    while True:
        current = turn_q[0] % num_players

        # Ф1: Битва Измерений
        phase_battle(hands, areas, players, spiral, captain_loc, rng)
        w = check_instants()
        if w:
            return (w, players)

        # Ф2: Усиление
        placed_cap_at = phase_reinforcement(
            current, hands, areas, players, captain_avail_idx, captain_loc, rng
        )
        if placed_cap_at is not None:
            captain_loc = placed_cap_at
            captain_avail_idx = None
        w = check_instants()
        if w:
            return (w, players)

        # Ф3: Перемещение/Аномалия
        phase_move_or_anomaly(
            current, hands, areas, players, spiral, deck, delete_pile, turn_q, captain_loc, rng
        )
        w = check_instants()
        if w:
            return (w, players)

        # Ф4: Атака
        phase_attack(current, areas, players, spiral, captain_loc, delete_pile, rng)
        w = check_instants()
        if w:
            return (w, players)

        # Ф5: Восстановление
        last_taker, emptied_now = deal_up_to(deck, hands, current)
        w = check_instants()
        if w:
            return (w, players)

        # Если колода опустела — назначаем один финальный ход last_taker
        if emptied_now and not final_enqueued and last_taker is not None:
            # вставим его следующим ходом
            turn_q.appendleft(last_taker)
            final_enqueued = True
            final_player = last_taker

        # завершение хода
        turn_q.rotate(-1)

        # условие выхода: если финальный ход был сыгран (т.е. следующий раз после него)
        if final_enqueued and (turn_q[0] % num_players) != final_player and not deck:
            # конец партии — подсчёт
            winner = score_game(areas, players, spiral, captain_loc)
            return (winner, players)

        # экстренный выход (пустая динамика)
        if not deck and all(sum(h.values()) == 0 for h in hands):
            winner = score_game(areas, players, spiral, captain_loc)
            return (winner, players)


# =========================
# Многократные симуляции
# =========================

def run_simulations(num_players: int, runs: int, seed: int) -> Dict[str, float]:
    rng = random.Random(seed)
    wins = Counter()
    participates = Counter()
    for _ in range(runs):
        winner, players = play_one_game(num_players, rng)
        wins[winner] += 1
        for f in players:
            participates[f] += 1

    # УСЛОВНЫЕ вероятности: P(win | participate)
    probs = {}
    for f in FRACTIONS:
        denom = participates[f] if participates[f] > 0 else 1
        probs[f] = wins[f] / denom
    return probs


if __name__ == "__main__":
    random.seed(RANDOM_SEED)
    for n in (5, 4, 3):
        probs = run_simulations(num_players=n, runs=1_000_000, seed=RANDOM_SEED)
        print(f"N={n} ->", {k: round(v, 4) for k, v in probs.items()})

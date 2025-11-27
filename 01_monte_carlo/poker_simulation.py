import random
from treys import Evaluator, Deck, Card

# Глобальный evaluator для переиспользования
EVALUATOR = Evaluator()

def monte_carlo(hero_cards: list,
				board_cards: list,
				active: int,
				n_simulations: int) -> list[int]:

    # Создаем одну колоду и убираем из неё известные карты
    remaining_cards = []
    deck = Deck()
    used_cards = set(hero_cards + board_cards)
    remaining_cards = [c for c in deck.cards if c not in used_cards]

    wins = ties = losses = 0

    # Цикл симуляций
    for _ in range(n_simulations):

        # Перемешиваем оставшиеся карты
        random.shuffle(remaining_cards)

        # Раздаём карты противникам
        card_index = 0
        villains = []
        for _ in range(active - 1):
            villain = remaining_cards[card_index:card_index + 2]
            villains.append(villain)
            card_index += 2

        # Добираем доску до 5 карт, если у нас не Ривер
        sim_board = board_cards[:]
        cards_needed = 5 - len(sim_board)
        if cards_needed > 0:
            sim_board.extend(remaining_cards[card_index:card_index + cards_needed])

        # Оценка рук
        hero_score = EVALUATOR.evaluate(sim_board, hero_cards)

        # Находим лучшего противника
        best_villain_score = float('inf')
        for villain in villains:
            villain_score = EVALUATOR.evaluate(sim_board, villain)
            if villain_score < best_villain_score:
                best_villain_score = villain_score

        # Подсчёт результатов (в treys меньше = лучше)
        if hero_score < best_villain_score:
            wins += 1
        elif hero_score == best_villain_score:
            ties += 1
        else:
            losses += 1

    return [wins, ties, losses]

def main():
    hero_cards = [Card.new('5s'), Card.new('6d')]
    board_cards = [Card.new('Qs'), Card.new('Jc'), Card.new('Ts')]
    active = 3
    n_simulations = 10000

    wins, ties, losses = monte_carlo(hero_cards, board_cards, active, n_simulations)
    equity = (wins + 0.5 * ties) / n_simulations

    print(f"Active users: {active}")

    hero_cards = map(lambda x: Card.int_to_pretty_str(x)[1:3], hero_cards)
    board_cards = map(lambda x: Card.int_to_pretty_str(x)[1:3], board_cards)
    print(f"Hero cards:  {list(hero_cards)}")
    print(f"Board cards: {list(board_cards)}")

    print(f"Wins: {wins} Ties: {ties} Losses: {losses}")
    print(f"Equity: {equity}")

if __name__ == "__main__":
    main()

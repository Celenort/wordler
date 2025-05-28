def check_hard_mode_compliance(guesses, feedbacks):
    known_greens = {}
    known_yellows = set()

    for turn in range(len(guesses) - 1):
        guess = guesses[turn]
        feedback = feedbacks[turn]

        for i in range(5):
            if feedback[i] == "green":
                known_greens[i] = guess[i]
            elif feedback[i] == "yellow":
                known_yellows.add(guess[i])

            if turn + 1 >= len(guesses):
                break

        next_guess = guesses[turn + 1]

        for i, ch in known_greens.items():
            if next_guess[i] != ch:
                return False

        for ch in known_yellows:
            if ch not in next_guess:
                return False

    return True


def calculate_score(attempts_left, streak_count, is_hardmode):
    streak_multiplier = min(1.0 + (streak_count / 10.0), 2.0)
    hard_multiplier = 2.0 if is_hardmode else 1.0
    return round(attempts_left * streak_multiplier * hard_multiplier, 1), streak_multiplier, hard_multiplier
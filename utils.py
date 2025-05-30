# Utils

def truncate_name(name: str, limit: int = 14) -> str:
    return name if len(name) <= limit else name[:limit - 1] + "…"

def render_histogram(data: dict):
    # 1. n1~n6 
    keys = ["n1", "n2", "n3", "n4", "n5", "n6"]
    values = [data.get(k, 0) for k in keys]
    
    # 2. find max
    max_val = max(values) if values else 1

    # 3. hist
    output = []
    for idx, val in enumerate(values):
        if max_val == 0:
            bar_count = 0
        else:
            bar_count = int((val / max_val) * 8)

        bar_count = max(bar_count, 1) if val > 0 else 0  # display at least 1 (with nonzero)
        
        output.append(bar_count)
    
    return output, max_val

def get_values(data: dict):
    keys = ["n1", "n2", "n3", "n4", "n5", "n6"]
    values = [str(data.get(k, 0)) for k in keys]  # ✅ 괄호 위치 수정
    return values

def calculate_mean(data: dict):
    keys = ["n1", "n2", "n3", "n4", "n5", "n6"]
    values = [data.get(k, 0) for k in keys]
    if sum(values) == 0 :
        return 0
    rtn = 0.0
    for idx, value in enumerate(values) :
        rtn += (idx+1) * value     
    return rtn / sum(values)

def lettercolor2emoji(letter, color, emojis):
    l = letter.upper()
    c = {'green': 'g', 'black': 'b', 'yellow': 'y', 'white': 'w'}.get(color)
    cl = c.upper()
    if not c:
        print("color not supported")
        return ''
    return f'<:{l}{cl}:{emojis[l+c]}>'

def format_guess_feedback(guess, answer):
    result = ['black'] * 5
    #answer_chars = list(answer)
    guess_used = [False] * 5
    answer_used = [False] * 5

    # Step 1: green 
    for i in range(5):
        if guess[i] == answer[i]:
            result[i] = 'green'
            guess_used[i] = True
            answer_used[i] = True

    # Step 2: yellow 
    for i in range(5):
        if not guess_used[i]:
            for j in range(5):
                if not answer_used[j] and guess[i] == answer[j]:
                    result[i] = 'yellow'
                    answer_used[j] = True
                    break

    return result

def feedback_to_render(feedback, guess, emojis) :
    ret = ""
    for idx, let in enumerate(guess) :
        ret += lettercolor2emoji(let, feedback[idx], emojis)
    return ret

def render_keyboard(status, emojis):
    lines = ["", " ", "  "]
    for c in "qwertyuiopasdfghjklzxcvbnm":
        color = status.get(c, 'white')
        if c in "qwertyuiop":
            lines[0] += lettercolor2emoji(c, color, emojis)
        elif c in "asdfghjkl":
            lines[1] += lettercolor2emoji(c, color, emojis)
        else:
            lines[2] += lettercolor2emoji(c, color, emojis)
    return "\n".join(lines)

def parse_board_colors(board):
    # 1. JSON chars to list
 
    results = []

    # 2. enumerating each row
    for line in board:
        colors = []
        # 3. <:XXX:1234> find patterns like this
        matches = re.findall(r'<:(.*?):\d+>', line)
        for match in matches:
            # 4. get last letter like XXX
            if match:
                colors.append(match[-1])
        results.append(colors)

    return results

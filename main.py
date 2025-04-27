import discord
import csv
import os
import json
import asyncio
import pytz
import requests
from datetime import datetime, timedelta
from fetch import fetch_todays_word


# ========== 기본 설정 ==========
WORD_LIST_URL = "https://gist.githubusercontent.com/dracos/dd0668f281e685bad51479e5acaadb93/raw/"
WORDLE_URL = "https://www.nytimes.com/games/wordle/index.html"
DATA_FOLDER = "wordle_data"
KEYBOARD_LAYOUT = "qwertyuiopasdfghjklzxcvbnm"
VALID_WORDS = set()
TODAYS_WORD = ""

user_data = {}
sessions = {}

# ========== 불러오기 ==========
with open('messages.json', 'r', encoding='utf-8') as f:
    messages = json.load(f)
with open('emoji.json', 'r', encoding='utf-8') as f:
    emojis = json.load(f)

# ========== 디스코드 설정 ==========
intents = discord.Intents.default()
intents.messages = True
intents.members = True
intents.guilds = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client, fallback_to_global=False)

# ========== 유틸 함수 ==========
def render_histogram(data: dict):
    # 1. n1~n6 정렬 순서대로 가져오기
    keys = ["n1", "n2", "n3", "n4", "n5", "n6"]
    values = [data.get(k, 0) for k in keys]
    
    # 2. 최대값 찾기
    max_val = max(values) if values else 1

    # 3. 줄별 히스토그램 만들기
    output = []
    for idx, val in enumerate(values):
        # 비율 계산
        if max_val == 0:
            bar_count = 0
        else:
            bar_count = int((val / max_val) * 8)

        bar_count = max(bar_count, 1) if val > 0 else 0  # 값이 0이 아닌데 최소 1개는 표시
        
        output.append(bar_count)
    
    return output


def lettercolor2emoji(letter, color):
    l = letter.upper()
    c = {'green': 'g', 'black': 'b', 'yellow': 'y', 'white': 'w'}.get(color)
    cl = c.upper()
    if not c:
        print("color not supported")
        return ''
    return f'<:{l}{cl}:{emojis[l+c]}>'

def load_valid_words():
    global VALID_WORDS
    response = requests.get(WORD_LIST_URL)
    if response.status_code == 200:
        VALID_WORDS = set(response.text.strip().split("\n"))
    else:
        print("Failed to load valid words.")

def format_guess_feedback(guess, answer):
    result = []
    answer_chars = list(answer)
    for idx, c in enumerate(guess):
        if c == answer[idx]:
            result.append('green')
            answer_chars[idx] = None
        else:
            result.append(None)
    for idx, c in enumerate(guess):
        if result[idx] is None:
            if c in answer_chars:
                result[idx] = 'yellow'
                answer_chars[answer_chars.index(c)] = None
            else:
                result[idx] = 'black'
    return result

def feedback_to_render(feedback, guess) :
    ret = ""
    for idx, let in enumerate(guess) :
        ret += lettercolor2emoji(let, feedback[idx])
    return ret

def render_keyboard(status):
    lines = ["", " ", "  "]
    for c in KEYBOARD_LAYOUT:
        color = status.get(c, 'white')
        if c in "qwertyuiop":
            lines[0] += lettercolor2emoji(c, color)
        elif c in "asdfghjkl":
            lines[1] += lettercolor2emoji(c, color)
        else:
            lines[2] += lettercolor2emoji(c, color)
    return "\n".join(lines)
import json
import re

def parse_board_colors(board):
    # 1. JSON 문자열을 리스트로 변환
 
    results = []

    # 2. 각 줄을 순회하면서
    for line in board:
        colors = []
        # 3. <:XXX:1234> 이런 패턴 찾기
        matches = re.findall(r'<:(.*?):\d+>', line)
        for match in matches:
            # 4. 이모지 이름(XXX)의 마지막 글자만 따기
            if match:
                colors.append(match[-1])
        results.append(colors)

    return results


def ensure_data_folder():
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)

def load_user_data():
    ensure_data_folder()
    for filename in os.listdir(DATA_FOLDER):
        if filename.endswith(".csv"):
            guild_id = int(filename.replace(".csv", ""))
            with open(os.path.join(DATA_FOLDER, filename), newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    user_data[(guild_id, int(row["user_id"]))] = {
                        "last_play_date": row["last_play_date"],
                        "current_streak": int(row["current_streak"]),
                        "max_streak": int(row["max_streak"]),
                        "games_played": int(row["games_played"]),
                        "wins": int(row["wins"]),
                        "attempts": int(row.get("attempts", 0)),
                        "board": json.loads(row["board"]) if row["board"] else [],
                        "keyboard": json.loads(row["keyboard"]) if row["keyboard"] else {},
                        "done_today": str(row["done_today"]).lower() in ("true", "1", "yes"), 
                        "n1" : int(row["n1"]),
                        "n2" : int(row["n2"]),
                        "n3" : int(row["n3"]),
                        "n4" : int(row["n4"]),
                        "n5" : int(row["n5"]),
                        "n6" : int(row["n6"])
                    }

def save_user_data():
    ensure_data_folder()
    guild_users = {}
    for (guild_id, user_id), data in user_data.items():
        guild_users.setdefault(guild_id, []).append({"user_id": user_id, **data})

    for guild_id, users in guild_users.items():
        with open(os.path.join(DATA_FOLDER, f"{guild_id}.csv"), "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "user_id", "last_play_date", "current_streak", "max_streak", 
                "games_played", "wins", "attempts", "board", "keyboard", "done_today",
                "n1", "n2", "n3", "n4", "n5", "n6"
            ])
            writer.writeheader()
            for user in users:
                # board, keyboard를 JSON 문자열로 변환해서 저장
                row = user.copy()
                row["board"] = json.dumps(user.get("board", []))
                row["keyboard"] = json.dumps(user.get("keyboard", {}))
                writer.writerow(row)

async def start_daily_reset_task():
    global TODAYS_WORD

    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    seconds_until_midnight = (tomorrow - now).total_seconds()

    print(f"[INFO] 자정까지 남은 시간: {seconds_until_midnight:.0f}초")
    await asyncio.sleep(seconds_until_midnight + 10)

    while True:
        global sessions
        print("[INFO] KST 00:00. refresh answer")
        TODAYS_WORD = fetch_todays_word()
        sessions = {} # reset sessions
        await asyncio.sleep(86400)



@tree.command(name="start", description="오늘의 워들을 시작합니다.")
async def start_game(interaction: discord.Interaction):
    key = (interaction.guild_id, interaction.user.id)
    today = str(datetime.today().date())

    if key not in user_data:
        # 유저 초기화
        user_data[key] = {
            "last_play_date": "",
            "current_streak": 0,
            "max_streak": 0,
            "games_played": 0,
            "wins": 0,
            "attempts": 0,
            "board": "",
            "keyboard": "",
            "done_today": False,
            "n1": 0, "n2": 0, "n3": 0, "n4": 0, "n5": 0, "n6": 0
        }

    data = user_data[key]

    if data["last_play_date"] != today:
        # 새로운 날짜면 진행 정보 초기화
        data["attempts"] = 0
        data["board"] = []
        data["keyboard"] = {}
        data["last_play_date"] = today
        data["done_today"] = False

    # sessions 복구
    sessions[key] = {
        "attempts": data.get("attempts", 0),
        "board": data.get("board", ""),
        "keyboard": data.get("keyboard", ""),
        "done": data.get("done_today", False)
    }

    if sessions[key]["done"]:
        await interaction.response.send_message(messages['already_solved'], ephemeral=True)
        return
    
    board_text = ""
    empty_row = "".join([':black_large_square:' for _ in range(5)])

    for row in sessions[key]["board"]:
        board_text += row + "\n"
    for _ in range(6 - len(sessions[key]["board"])):
        board_text += empty_row + "\n"

    keyboard_text = render_keyboard(sessions[key]["keyboard"])
    embed = discord.Embed(title="Wordle", color=0x00ff00)
    embed.add_field(name="📋 진행상황", value=board_text, inline=False)
    embed.add_field(name="⌨️ 키보드 상태", value=keyboard_text, inline=False)
    if board_text :
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    else :
        await interaction.response.send_message(messages["start_game"], ephemeral=True)
        return




@tree.command(name="w", description="단어를 입력합니다.")
async def guess_word(interaction: discord.Interaction, word: str):
    key = (interaction.guild_id, interaction.user.id)

    if key not in sessions:
        await interaction.response.send_message(messages['not_started'], ephemeral=True)
        return
    elif sessions[key]["done"] or user_data[key]["done_today"]:
        await interaction.response.send_message(messages['already_solved'], ephemeral=True)
        return


    word = word.lower()
    if len(word) != 5:
        await interaction.response.send_message(messages["invalid_word"], ephemeral=True)
        return
    elif word not in VALID_WORDS:
        await interaction.response.send_message(messages["not_in_wordle_list"], ephemeral=True)
        return

    session = sessions[key]
    feedback = format_guess_feedback(word, TODAYS_WORD)
    renderboard = feedback_to_render(feedback, word)
    session["board"].append(renderboard)
    session["attempts"] += 1

    # 키보드 업데이트
    for idx, c in enumerate(word):
        if feedback[idx] == 'green':
            session["keyboard"][c] = 'green'
        elif feedback[idx] == 'yellow' and session["keyboard"].get(c) != 'green':
            session["keyboard"][c] = 'yellow'
        elif feedback[idx] == 'black' and session["keyboard"].get(c) not in ('green', 'yellow'):
            session["keyboard"][c] = 'black'

    board_text = ""
    empty_row = "".join([':black_large_square:' for _ in range(5)])

    for row in session["board"]:
        board_text += row + "\n"
    for _ in range(6 - len(session["board"])):
        board_text += empty_row + "\n"

    keyboard_text = render_keyboard(session["keyboard"])

    # 하나의 임베드로 합치기
    embed = discord.Embed(title="Wordle", color=0x00ff00)
    embed.add_field(name="📋 진행상황", value=board_text, inline=False)
    embed.add_field(name="⌨️ 키보드 상태", value=keyboard_text, inline=False)


    if word == TODAYS_WORD:
        user_data[key]["games_played"] += 1
        user_data[key]["wins"] += 1
        user_data[key]["current_streak"] += 1
        user_data[key]["max_streak"] = max(user_data[key]["max_streak"], user_data[key]["current_streak"])
        user_data[key]["done_today"] = True
        sessions[key]["done"] = True
        user_data[key]["n"+str(session["attempts"])] += 1
        save_user_data()
        embed.add_field(name=messages['correct_guess1'],value=messages['correct_guess2'].format(word=TODAYS_WORD),  inline=False)
    elif session["attempts"] >= 6:
        user_data[key]["games_played"] += 1
        user_data[key]["current_streak"] = 0
        user_data[key]["done_today"] = True
        sessions[key]["done"] = True
        save_user_data()
        embed.add_field(name=messages['game_over'].format(word=TODAYS_WORD),value="",  inline=False)
    else:
        embed.add_field(name=':pushpin: ' + messages['remaining_attempts'].format(attempts=6 - session['attempts']),value="",  inline=False)
        user_data[key]["board"] = session["board"]
        user_data[key]["keyboard"] = session["keyboard"]
        save_user_data()
    await interaction.response.send_message(embed=embed, ephemeral=True)
    return

@tree.command(name="share", description="게임 결과를 채팅방에 공유합니다.")
async def share(interaction: discord.Interaction) :
    key = (interaction.guild_id, interaction.user.id)
    member = interaction.guild.get_member(interaction.user.id)
    name = member.display_name if member else "Unknown"
    today = str(datetime.today().date())
    if user_data.get(key, {}).get("last_play_date") != today:
        await interaction.response.send_message(messages['not_started'], ephemeral=True)
        return
    elif key not in sessions and user_data[key]["done_today"] :
        # done today -> so print
        session = user_data[key]
    else :
        session = sessions[key]
    board_text = ""
    empty_row = "".join([':black_large_square:' for _ in range(5)])
    results = parse_board_colors(session["board"])
    length = len(session["board"])
    if length == 6 and user_data[key]["current_streak"] == 0 :
        length = "X"
    cmap = {"Y" : ":yellow_square:", "B" : ":white_large_square:", "G" : ":green_square:"}
    for line in results :
        for it in line :
            board_text += cmap[it]
        board_text +="\n"
    for _ in range(6 - len(session["board"])):
        board_text += empty_row + "\n"

    embed = discord.Embed(title=f"Wordle {today}", color=0x00ff00)
    embed.add_field(name=f"{name} : {length}/6", value=board_text, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=False)

    return

@tree.command(name="status", description="현재 게임 진행상황을 표시합니다.")
async def show_current_progress(interaction: discord.Interaction):
    key = (interaction.guild_id, interaction.user.id)
    today = str(datetime.today().date())
    if user_data.get(key, {}).get("last_play_date") != today:
        await interaction.response.send_message(messages['not_started'], ephemeral=True)
        return
    elif key not in sessions and user_data[key]["done_today"] :
        # done today -> so print
        session = user_data[key]
    else :
        session = sessions[key]

    board_text = ""
    empty_row = "".join([':black_large_square:' for _ in range(5)])

    for row in session["board"]:
        board_text += row + "\n"
    for _ in range(6 - len(session["board"])):
        board_text += empty_row + "\n"

    keyboard_text = render_keyboard(session["keyboard"])

    embed = discord.Embed(title="워들 게임 진행상황", color=0x00ff00)
    embed.add_field(name="📋 진행상황", value=board_text, inline=False)
    embed.add_field(name="⌨️ 키보드 상태", value=keyboard_text, inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="reset", description="Admin만 사용가능, 서버의 기록을 초기화합니다.")
@discord.app_commands.checks.has_permissions(administrator=True)
async def reset(interaction: discord.Interaction):
    guid = interaction.guild_id
    global user_data, sessions
    csvpath = DATA_FOLDER + '/' + str(guid) + '.csv'
    try:
        os.remove(csvpath)
        user_data = {}
        sessions = {}
        await interaction.response.send_message(messages["rmdir"], ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(messages["rmdirfail"], ephemeral=True)

# 권한 없는 사람이 썼을 때 에러 핸들링
@reset.error
async def reset(interaction: discord.Interaction, e):
    if isinstance(e, discord.app_commands.errors.MissingPermissions):
        await interaction.response.send_message(messages["rmdirnoperm"], ephemeral=True)
    else:
        await interaction.response.send_message(messages["rmdirfail"], ephemeral=True)





@tree.command(name="stats", description="자신의 통계 정보를 확인합니다.")
async def show_stats(interaction: discord.Interaction, share : bool = False):
    key = (interaction.guild_id, interaction.user.id)
    data = user_data.get(key)
    eph = not share

    if not data:
        await interaction.response.send_message(messages["no_play_record"], ephemeral=True)
        return
    elif data['games_played'] == 0 :
        await interaction.response.send_message(messages["no_play_record"], ephemeral=True)
        return

    embed = discord.Embed(
        title=f"📊 {interaction.user.display_name} 님의 워들 통계",
        color=discord.Color.green()
    )
    name = "플레이어 통계"
    value = ":video_game: 총 게임 수 : " + str(data['games_played']) + "\n:trophy: 승리 수 : " + str(data['wins']) + "\n:fire: 현재 연속 성공 일수 : " + str(data['current_streak']) + "\n:medal: 최대 연속 성공 일수 : " + str(data['max_streak']) + "\n:chart_with_upwards_trend: 승률 : " + str(round(data['wins'] / data['games_played'] * 100, 2)) + "%"
    embed.add_field(name=name, value=value, inline=False)
    hist_out = render_histogram(user_data[key])
    hist_value = ":one: | " + ":green_square:" * hist_out[0] + "\n" +":two: | " + ":green_square:" * hist_out[1] + "\n"":three: | " + ":green_square:" * hist_out[3] + "\n"":four: | " + ":green_square:" * hist_out[3] + "\n"":five: | " + ":green_square:" * hist_out[4] + "\n"":six: | " + ":green_square:" * hist_out[5] + "\n"
    embed.add_field(name=":bar_chart: Histograms", value=hist_value, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=eph)
    return


@tree.command(name="leaderboard", description="서버 리더보드를 확인합니다.")
async def leaderboard(interaction: discord.Interaction, share : bool = False):
    guild_users = [(uid, data) for (gid, uid), data in user_data.items() if gid == interaction.guild_id]
    if not guild_users:
        await interaction.response.send_message(messages["no_leaderboard_data"], ephemeral=True)
        return

    # 정렬 기준: 승리수 → 연속 성공일수
    guild_users.sort(key=lambda x: (-x[1]["wins"], -x[1]["current_streak"]))

    embed = discord.Embed(
        title="🏆 워들 서버 랭킹 🏆",
        description=f"서버: {interaction.guild.name}",
        color=discord.Color.gold()
    )

    for idx, (uid, data) in enumerate(guild_users[:10], start=1):
        if data['games_played'] == 0 :
            continue
        member = interaction.guild.get_member(uid)
        name = member.display_name if member else "Unknown"
        value = f"🏅 W : {data['wins']} | 🔥 CS : {data['current_streak']} | :chart_with_upwards_trend: WR : {round(data['wins']/data['games_played'] * 100, 2)} %"
        embed.add_field(
            name=f"#{idx} {name}",
            value=value,
            inline=False
        )
    eph = not share
    await interaction.response.send_message(embed=embed, ephemeral=eph)
    return


# ========== 이벤트 ==========
@client.event
async def on_ready():
    global TODAYS_WORD
    print(f"Logged in as {client.user}")
    load_valid_words()
    TODAYS_WORD = fetch_todays_word()
    load_user_data()
    asyncio.create_task(start_daily_reset_task())
    await tree.sync()

# ========== 토큰 실행 (github secrets 등으로 관리) ==========
client.run(os.environ.get("DISCORD_BOT_TOKEN"))


# invitation link : https://discord.com/oauth2/authorize?client_id=1365698732443570267
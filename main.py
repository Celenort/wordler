import discord
import csv
import os
import json
import asyncio
import pytz
import requests
from datetime import datetime, timedelta
from fetch import fetch_todays_word



# ========== Global config ==========
WORD_LIST_URL = "https://gist.githubusercontent.com/dracos/dd0668f281e685bad51479e5acaadb93/raw/"
WORDLE_URL = "https://www.nytimes.com/games/wordle/index.html"
DATA_FOLDER = "wordle_data"
KEYBOARD_LAYOUT = "qwertyuiopasdfghjklzxcvbnm"
VALID_WORDS = set()
TODAYS_WORD = ""

user_data = {}
sessions = {}

# ========== Load json ==========
with open('messages.json', 'r', encoding='utf-8') as f:
    messages = json.load(f)
with open('emoji.json', 'r', encoding='utf-8') as f:
    emojis = json.load(f)

# ========== Discord config ==========
intents = discord.Intents.default()
intents.messages = True
intents.members = True
intents.guilds = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client, fallback_to_global=False)

# ========== Utils ==========
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
    
    return output
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
    result = ['black'] * 5
    answer_chars = list(answer)
    guess_used = [False] * 5
    answer_used = [False] * 5

    # 1단계: green 처리
    for i in range(5):
        if guess[i] == answer[i]:
            result[i] = 'green'
            guess_used[i] = True
            answer_used[i] = True

    # 2단계: yellow 처리
    for i in range(5):
        if not guess_used[i]:
            for j in range(5):
                if not answer_used[j] and guess[i] == answer[j]:
                    result[i] = 'yellow'
                    answer_used[j] = True
                    break

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
                # board, keyboard- > Json parsing
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

    print(f"[INFO] TIME until midnight: {seconds_until_midnight:.0f}초")
    await asyncio.sleep(seconds_until_midnight+10)

    while True:
        global sessions
        print("[INFO] KST 00:00. refresh answer")
        await client.change_presence(
            status=discord.Status.idle,
            activity=discord.Game(name=messages["idle"])
        )
        # calculate yesterday's date
        yesterday = (datetime.now(kst) - timedelta(days=1)).date()

        # CS to 0
        for key, data in user_data.items():
            last_play_date = data.get("last_play_date")
            if not last_play_date or datetime.strptime(last_play_date, "%Y-%m-%d").date() != yesterday:
                if data.get("current_streak", 0) > 0:
                    print(f"[INFO] Resetting streak for user {key}")
                    data["current_streak"] = 0

        save_user_data()

        temp = TODAYS_WORD
        TODAYS_WORD = await asyncio.to_thread(fetch_todays_word)





        sessions = {} # reset sessions
        fetchcount = 0
        if temp == TODAYS_WORD :
            await asyncio.sleep(10)
            TODAYS_WORD = fetch_todays_word()
            fetchcount +=1
        await client.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name=messages["online"])
        )
        await asyncio.sleep(86400-30*fetchcount)
        fetchcount=0



@tree.command(name="start", description=messages["desc_start"])
async def start_game(interaction: discord.Interaction):
    key = (interaction.guild_id, interaction.user.id)
    today = str(datetime.today().date())

    if key not in user_data:
        # reset user
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
        # if new day, reset progress
        data["attempts"] = 0
        data["board"] = []
        data["keyboard"] = {}
        data["last_play_date"] = today
        data["done_today"] = False

    # sessions recovery
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
    embed = discord.Embed(title=messages["wordle"], color=0x00ff00)
    embed.add_field(name=messages["status"], value=board_text, inline=False)
    embed.add_field(name=messages["keyboard_status"], value=keyboard_text, inline=False)
    if board_text :
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    else :
        await interaction.response.send_message(messages["start_game"], ephemeral=True)
        return




@tree.command(name="w", description=messages["desc_write"])
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

    # update_keyboard
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

    # concat with a single embed
    embed = discord.Embed(title=messages["wordle"], color=0x00ff00)
    embed.add_field(name=messages["status"], value=board_text, inline=False)
    embed.add_field(name=messages["keyboard_status"], value=keyboard_text, inline=False)


    if word == TODAYS_WORD:
        user_data[key]["games_played"] += 1
        user_data[key]["wins"] += 1
        user_data[key]["current_streak"] += 1
        user_data[key]["max_streak"] = max(user_data[key]["max_streak"], user_data[key]["current_streak"])
        user_data[key]["done_today"] = True
        sessions[key]["done"] = True
        user_data[key]["n"+str(len(session["board"]))] += 1
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

@tree.command(name="share", description=messages["desc_share"])
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
    # add profile
    avatar_url = interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url

    embed.set_thumbnail(url=avatar_url)
    embed.add_field(name=f"{name} : {length}/6", value=board_text, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=False)

    return

@tree.command(name="status", description=messages["desc_status"])
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

    embed = discord.Embed(title=messages["wordle"], color=0x00ff00)
    embed.add_field(name=messages["status"], value=board_text, inline=False)
    embed.add_field(name=messages["keyboard_status"], value=keyboard_text, inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="reset", description=messages["desc_reset"])
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

# raise error when not permitted
@reset.error
async def reset(interaction: discord.Interaction, e):
    if isinstance(e, discord.app_commands.errors.MissingPermissions):
        await interaction.response.send_message(messages["rmdirnoperm"], ephemeral=True)
    else:
        await interaction.response.send_message(messages["rmdirfail"], ephemeral=True)





@tree.command(name="stats", description=messages["desc_stats"])
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
        title=messages["stats_title"].format(name=interaction.user.display_name),
        color=discord.Color.green()
    )
    # add profile
    avatar_url = interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url

    embed.set_author(name=interaction.user.display_name, icon_url=avatar_url)
    avg_perf = calculate_mean(user_data[key])
    name = messages["player_stats"]
    value = messages["stats"].format(played=str(data['games_played']), wins = str(data['wins']), streak = str(data['current_streak']), max_streak=str(data['max_streak']), wr = str(round(data['wins'] / data['games_played'] * 100, 2)), avg = str(round(avg_perf, 2)))
    embed.add_field(name=name, value=value, inline=False)
    hist_out = render_histogram(user_data[key])
    values = get_values(user_data[key])

    # count failures
    failures = data["games_played"] - sum(int(v) for v in values)

    # print hist
    hist_value = (
        ":one: | " + ":green_square:" * hist_out[0] + f" ({values[0]})\n" +
        ":two: | " + ":green_square:" * hist_out[1] + f" ({values[1]})\n" +
        ":three: | " + ":green_square:" * hist_out[2] + f" ({values[2]})\n" +
        ":four: | " + ":green_square:" * hist_out[3] + f" ({values[3]})\n" +
        ":five: | " + ":green_square:" * hist_out[4] + f" ({values[4]})\n" +
        ":six: | " + ":green_square:" * hist_out[5] + f" ({values[5]})\n" +
        ":regional_indicator_x:     | " + ":yellow_square:" * max(int((failures / max(data["games_played"], 1)) * 8), 0) + f" ({failures})\n"
    )
    embed.add_field(name=":bar_chart: Histograms", value=hist_value, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=eph)
    return


@tree.command(name="leaderboard", description=messages["desc_leaderboard"])
async def leaderboard(interaction: discord.Interaction, share: bool = False):
    guild_users = [
        (uid, data, calculate_mean(data))
        for (gid, uid), data in user_data.items()
        if gid == interaction.guild_id and data["games_played"] > 0
    ]

    if not guild_users:
        await interaction.response.send_message(messages["no_leaderboard_data"], ephemeral=True)
        return

    guild_users.sort(key=lambda x: (-x[1]["wins"], x[2]))

    embed = discord.Embed(
        title=messages["leaderboard_title"],
        color=discord.Color.gold()
    )

    if interaction.guild.icon:
        embed.set_author(
            name=messages["leaderboard_guild_name"].format(name=interaction.guild.name),
            icon_url=interaction.guild.icon.url
        )
    else:
        embed.set_author(name=interaction.guild.name)

    leaderboard_text = (
        "🏅 | 👤 Username    |🏆 W | 🔥CS | 📈 WR | 📌 AVG\n"
        "-----------------------------------------------------\n"
    )

    for idx, (uid, data, avg_perf) in enumerate(guild_users[:10], start=1):
        member = interaction.guild.get_member(uid)
        full_name = str(member) if member else "Unknown"
        full_name = truncate_name(full_name, 14)

        wins = data["wins"]
        cs = data["current_streak"]
        wr = round(wins / data["games_played"] * 100, 1)
        avg = round(avg_perf, 2)

        leaderboard_text += f"{idx:>2} | {full_name:<14} | {wins:>3} | {cs:>4} | {wr:>5.1f}% | {avg:>6.2f}\n"

    embed.description = f"```{leaderboard_text}```"

    eph = not share
    await interaction.response.send_message(embed=embed, ephemeral=eph)



# ========== event ==========
@client.event
async def on_ready():
    global TODAYS_WORD
    print(f"Logged in as {client.user}")
    await client.change_presence(
            status=discord.Status.dnd,
            activity=discord.Game(name=messages["dnd"])
        )

    load_valid_words()
    TODAYS_WORD = await asyncio.to_thread(fetch_todays_word)
    load_user_data()

    await client.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name=messages["online"])
    )

    asyncio.create_task(start_daily_reset_task())
    await tree.sync()

# ========== run bot ==========
client.run(os.environ.get("DISCORD_BOT_TOKEN"))


# invitation link : https://discord.com/oauth2/authorize?client_id=1365698732443570267

import discord
import csv
import os
import json
import asyncio
import pytz
import requests
from datetime import datetime, timedelta
from fetch import fetch_todays_word
import sys
from hardmode import check_hard_mode_compliance, calculate_score
import json
from utils import *
from database import get_db_connection, init_db
from copy import deepcopy

# invitation link : https://discord.com/oauth2/authorize?client_id=1365698732443570267

# ========== Global config ==========
WORD_LIST_URL = "https://gist.githubusercontent.com/dracos/dd0668f281e685bad51479e5acaadb93/raw/"
WORDLE_URL = "https://www.nytimes.com/games/wordle/index.html"
DATA_FOLDER = "wordle_data"
VALID_WORDS = set()
TODAYS_WORD = ""
DEBUG=True
SOFT_DEBUG=False
ISLOADING=True
FIELDS = {
    "user_id": 0,
    "last_play_date": "",
    "current_streak": 0,
    "max_streak": 0,
    "games_played": 0,
    "wins": 0,
    "attempts": 0,
    "board": [],
    "keyboard": {},
    "done_today": False,
    "n1": 0, "n2": 0, "n3": 0, "n4": 0, "n5": 0, "n6": 0,
    "h1": 0, "h2": 0, "h3": 0, "h4": 0, "h5": 0, "h6": 0,
    "score": 0.0,
    "hardmode_successes": 0,
    "hardmode_streak": 0,
    "hardmode_games": 0,
    "hardmode_max_streak": 0
}
DEBUG_WORD='cease'
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

# ========== Check system version ==========

USE_TO_THREAD = False

if sys.version_info >= (3, 9):
    USE_TO_THREAD=True

async def initialize_bot():
    global TODAYS_WORD, ISLOADING
    ISLOADING=True
    await client.change_presence(
        status=discord.Status.dnd,
        activity=discord.Game(name=messages["dnd"])
    )


    if DEBUG or SOFT_DEBUG:
        TODAYS_WORD = DEBUG_WORD
    else:
        TODAYS_WORD = await to_thread_equivalent(fetch_todays_word)
    load_valid_words()
    init_db() 
    load_user_data()

    await client.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name=messages["online"])
    )

    await tree.sync()
    ISLOADING=False

async def to_thread_equivalent(func):
    if USE_TO_THREAD :
        return await asyncio.to_thread(func)
    else :
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func)

# ========== Utils ==========

def load_valid_words():
    global VALID_WORDS
    response = requests.get(WORD_LIST_URL)
    if response.status_code == 200:
        VALID_WORDS = set(response.text.strip().split("\n"))
    else:
        print("Failed to load valid words.")

def load_user_data():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM user_stats")
    rows = cur.fetchall()
    conn.close()

    for row in rows:
        key = (row["guild_id"], row["user_id"])
        record = dict(row)

        for field in ["board", "keyboard"]:
            try:
                if isinstance(record.get(field), str) and record[field]:
                    record[field] = json.loads(record[field])
            except json.JSONDecodeError:
                record[field] = [] if field == "board" else {}

        user_data[key] = record

def save_user_data(key=None):
    if key not in user_data:
        return
    data = user_data[key].copy()

    #  ensure primary keys are included
    guild_id, user_id = key
    data["guild_id"] = guild_id
    data["user_id"] = user_id

    #  serialize complex types
    for field in ["board", "keyboard"]:
        if isinstance(data.get(field), (list, dict)):
            data[field] = json.dumps(data[field])

    conn = get_db_connection()
    c = conn.cursor()

    columns = ', '.join(data.keys())
    placeholders = ', '.join(['?'] * len(data))
    update_clause = ', '.join([f"{k}=excluded.{k}" for k in data.keys()])
    values = list(data.values())

    c.execute(f'''
        INSERT INTO user_stats ({columns})
        VALUES ({placeholders})
        ON CONFLICT(guild_id, user_id)
        DO UPDATE SET {update_clause}
    ''', values)

    conn.commit()
    conn.close()

async def start_daily_reset_task():
    global TODAYS_WORD
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    seconds_until_midnight = (tomorrow - now).total_seconds()

    print(f"[INFO] TIME until midnight: {seconds_until_midnight:.0f}초")
    await asyncio.sleep(seconds_until_midnight+10)

    while True:
        global sessions, ISLOADING
        ISLOADING=True
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
        TODAYS_WORD = await to_thread_equivalent(fetch_todays_word)

        sessions = {} # reset sessions
        ISLOADING=False
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
    if ISLOADING or not TODAYS_WORD:
        await interaction.response.send_message(messages["loading"], ephemeral=True)
        return

    key = (interaction.guild_id, interaction.user.id)
    today = str(datetime.today().date())

    if key not in user_data:
        # reset user
        user_data[key] = deepcopy(FIELDS) 

    data = user_data[key]

    if data["last_play_date"] != today:
        # if new day, reset progress
        data["attempts"] = 0
        data["board"] = []
        data["keyboard"] = {}
        data["last_play_date"] = today
        data["done_today"] = False
    elif DEBUG :
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
        await interaction.response.send_message(messages['already_solved'], ephemeral=False if DEBUG else True)
        return
    
    board_text = ""
    empty_row = "".join([':black_large_square:' for _ in range(5)])

    for row in sessions[key]["board"]:
        board_text += row + "\n"
    for _ in range(6 - len(sessions[key]["board"])):
        board_text += empty_row + "\n"

    keyboard_text = render_keyboard(sessions[key]["keyboard"], emojis)
    embed = discord.Embed(title=messages["wordle"], color=0x00ff00)
    embed.add_field(name=messages["status"], value=board_text, inline=False)
    embed.add_field(name=messages["keyboard_status"], value=keyboard_text, inline=False)
    if board_text :
        await interaction.response.send_message(embed=embed, ephemeral=False if DEBUG else True)
        return
    else :
        await interaction.response.send_message(messages["start_game"], ephemeral=False if DEBUG else True)
        return

@tree.command(name="w", description=messages["desc_write"])
async def guess_word(interaction: discord.Interaction, word: str):
    if ISLOADING or not TODAYS_WORD:
        await interaction.response.send_message(messages["loading"], ephemeral=True)
        return
    key = (interaction.guild_id, interaction.user.id)

    if key not in sessions:
        await interaction.response.send_message(messages['not_started'], ephemeral=False if DEBUG else True)
        return
    elif sessions[key]["done"] or user_data[key]["done_today"]:
        await interaction.response.send_message(messages['already_solved'], ephemeral=False if DEBUG else True)
        return


    word = word.lower()
    if len(word) != 5:
        await interaction.response.send_message(messages["invalid_word"], ephemeral=False if DEBUG else True)
        return
    elif word not in VALID_WORDS:
        await interaction.response.send_message(messages["not_in_wordle_list"], ephemeral=False if DEBUG else True)
        return

    session = sessions[key]
    feedback = format_guess_feedback(word, TODAYS_WORD)
    renderboard = feedback_to_render(feedback, word, emojis)
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

    keyboard_text = render_keyboard(session["keyboard"], emojis)

    # concat with a single embed
    embed = discord.Embed(title=messages["wordle"], color=0x00ff00)
    embed.add_field(name=messages["status"], value=board_text, inline=False)
    embed.add_field(name=messages["keyboard_status"], value=keyboard_text, inline=False)

    # ==== Hard Mode checking logic
    if "board" in session and session["board"]:
        guesses = session.setdefault("raw_guesses", [])
        guesses.append(word)  # applying newly inputed word
        feedbacks = [format_guess_feedback(g, TODAYS_WORD) for g in guesses]
        is_hard = check_hard_mode_compliance(guesses, feedbacks)
        embed.add_field(name=messages["hard_mode_check"] + ":white_check_mark:" if is_hard else messages["hard_mode_check"] + ":negative_squared_cross_mark:", value="", inline=False)



    if word == TODAYS_WORD:
        # save guess information
        session.setdefault("raw_guesses", []).append(word)
        guesses = session["raw_guesses"]
        feedbacks = [format_guess_feedback(g, TODAYS_WORD) for g in guesses]
        
        # Hard Mode determination
        is_hard = check_hard_mode_compliance(guesses, feedbacks)

        if is_hard :
            user_data[key]["hardmode_streak"] += 1
            if user_data[key]["hardmode_max_streak"] < user_data[key]["hardmode_streak"] :
                user_data[key]["hardmode_max_streak"] = user_data[key]["hardmode_streak"]
        else :
            user_data[key]["hardmode_streak"] = 0
        attempts_left = 6 - session["attempts"] + 1
        score_gained, streak_mult, hard_mult = calculate_score(
            attempts_left,
            user_data[key]["current_streak"],
            user_data[key]["hardmode_streak"],
            is_hard
        )

        # Applying score
        user_data[key]["score"] += score_gained
        score = user_data[key]["score"]
        if is_hard:
            user_data[key]["hardmode_successes"] += 1


        user_data[key]["games_played"] += 1
        user_data[key]["wins"] += 1
        user_data[key]["current_streak"] += 1
        user_data[key]["max_streak"] = max(user_data[key]["max_streak"], user_data[key]["current_streak"])
        user_data[key]["done_today"] = False if DEBUG else True
        sessions[key]["done"] = False if DEBUG else True
        user_data[key]["n"+str(len(session["board"]))] += 1
        if is_hard :
            user_data[key]["hardmode_games"] += 1
            user_data[key]["h"+str(len(session["board"]))] += 1

        save_user_data(key)
        embed.add_field(name=messages['correct_guess1'],value=messages['correct_guess2'].format(word=TODAYS_WORD),  inline=False)
        #embed.add_field(name=messages["hard_mode_check"] + ":white_check_mark:" if is_hard else messages["hard_mode_check"]  + ":negative_squared_cross_mark:", value="", inline=False)
        embed.add_field(
            name=messages["earned_points"],
            value=messages["earned_desc"].format(attempts_left=attempts_left, streak_mult=streak_mult, hard_mult=hard_mult, score_gained=score_gained),
            inline=False
        )
        embed.add_field(
            name=messages["total_points"].format(score=score),
            value="",
            inline=False
        )

    elif session["attempts"] >= 6:
        user_data[key]["games_played"] += 1
        user_data[key]["current_streak"] = 0
        if not is_hard :
            user_data[key]["hardmode_streak"] = 0
        user_data[key]["done_today"] = False if DEBUG else True
        sessions[key]["done"] = False if DEBUG else True
        save_user_data(key)
        if is_hard :
            user_data[key]["hardmode_games"] += 1

        embed.add_field(name=messages['game_over'].format(word=TODAYS_WORD),value="",  inline=False)
    else:
        embed.add_field(name=':pushpin: ' + messages['remaining_attempts'].format(attempts=6 - session['attempts']),value="",  inline=False)
        user_data[key]["board"] = session["board"]
        user_data[key]["keyboard"] = session["keyboard"]
        save_user_data(key)
    await interaction.response.send_message(embed=embed, ephemeral=False if DEBUG else True)
    return

@tree.command(name="share", description=messages["desc_share"])
async def share(interaction: discord.Interaction) :
    key = (interaction.guild_id, interaction.user.id)
    member = interaction.guild.get_member(interaction.user.id)
    name = member.display_name if member else "Unknown"
    today = str(datetime.today().date())
    if user_data.get(key, {}).get("last_play_date") != today:
        await interaction.response.send_message(messages['not_started'], ephemeral=False if DEBUG else True)
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
    plus = "" if user_data[key]["done_today"] else " (Playing)" 
    embed.add_field(name=f"{name} : {length}/6" + plus, value=board_text, inline=False)
    # === Hard Mode check logic ===
    guesses = session.get("raw_guesses", [])
    if guesses:
        feedbacks = [format_guess_feedback(g, TODAYS_WORD) for g in guesses]
        is_hard= check_hard_mode_compliance(guesses, feedbacks)
        embed.add_field(name=messages["hard_mode_check"] + ":white_check_mark:" if is_hard else messages["hard_mode_check"] + ":negative_squared_cross_mark:", value="", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=False)

    return

@tree.command(name="status", description=messages["desc_status"])
async def show_current_progress(interaction: discord.Interaction):
    key = (interaction.guild_id, interaction.user.id)
    today = str(datetime.today().date())
    if user_data.get(key, {}).get("last_play_date") != today:
        await interaction.response.send_message(messages['not_started'], ephemeral=False if DEBUG else True)
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

    keyboard_text = render_keyboard(session["keyboard"], emojis)
    plus = " (Result)" if user_data[key]["done_today"] else " (Playing)" 

    embed = discord.Embed(title=messages["wordle"], color=0x00ff00)
    embed.add_field(name=messages["status"] + plus, value=board_text, inline=False)
    embed.add_field(name=messages["keyboard_status"], value=keyboard_text, inline=False)
    

    await interaction.response.send_message(embed=embed, ephemeral=False if DEBUG else True)

@tree.command(name="reset", description=messages["desc_reset"])
@discord.app_commands.checks.has_permissions(administrator=True)
async def reset(interaction: discord.Interaction):
    try :
        guid = interaction.guild_id
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DELETE FROM user_stats WHERE guild_id = ?", (guid,))
        conn.commit()
        conn.close()
        await interaction.response.send_message(messages["rmdir"], ephemeral=False if DEBUG else True)
    except Exception as e:
        await interaction.response.send_message(messages["rmdirfail"], ephemeral=False if DEBUG else True)
# raise error when not permitted
@reset.error
async def reset(interaction: discord.Interaction, e):
    if isinstance(e, discord.app_commands.errors.MissingPermissions):
        await interaction.response.send_message(messages["rmdirnoperm"], ephemeral=False if DEBUG else True)
    else:
        await interaction.response.send_message(messages["rmdirfail"], ephemeral=False if DEBUG else True)

@tree.command(name="stats", description=messages["desc_stats"])
async def show_stats(interaction: discord.Interaction, share : bool = False, hard : bool = False):
    key = (interaction.guild_id, interaction.user.id)
    data = user_data.get(key)
    eph = not share

    if not data:
        await interaction.response.send_message(messages["no_play_record"], ephemeral=False if DEBUG else True)
        return
    elif data['games_played'] == 0 :
        await interaction.response.send_message(messages["no_play_record"], ephemeral=False if DEBUG else True)
        return
    if hard and data['hardmode_games'] == 0 :
        await interaction.response.send_message(messages["no_hard_play_record"], ephemeral=False if DEBUG else True)
        return
    if not hard :
        embed = discord.Embed(
            title=messages["stats_title"].format(name=interaction.user.display_name),
            color=discord.Color.green()
        )
        # add profile
        avatar_url = interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url

        embed.set_author(name=interaction.user.display_name, icon_url=avatar_url)
        avg_perf = calculate_mean(user_data[key])
        name = messages["player_stats"]
        value = messages["stats"].format(score=data['score'], played=str(data['games_played']), wins = str(data['wins']), streak = str(data['current_streak']), max_streak=str(data['max_streak']), wr = str(round(data['wins'] / data['games_played'] * 100, 2)), avg = str(round(avg_perf, 2)))
        embed.add_field(name=name, value=value, inline=False)
        hist_out, max_val = render_histogram(user_data[key])
        values = get_values(user_data[key])

        # count failures
        failures = data["games_played"] - sum(int(v) for v in values)

        fail_bar = None
        if max_val == 0:
            fail_bar = 0
        else:
            fail_bar = int((failures / max_val) * 8)
            fail_bar = max(fail_bar, 1) if failures > 0 else 0  # display at least 1 (with nonzero)
        # print hist
        hist_value = (
            ":one: | " + ":green_square:" * hist_out[0] + f" ({values[0]})\n" +
            ":two: | " + ":green_square:" * hist_out[1] + f" ({values[1]})\n" +
            ":three: | " + ":green_square:" * hist_out[2] + f" ({values[2]})\n" +
            ":four: | " + ":green_square:" * hist_out[3] + f" ({values[3]})\n" +
            ":five: | " + ":green_square:" * hist_out[4] + f" ({values[4]})\n" +
            ":six: | " + ":green_square:" * hist_out[5] + f" ({values[5]})\n" +
            ":regional_indicator_x: | " + ":yellow_square:" * fail_bar + f" ({failures})\n"
        )
        embed.add_field(name=messages["histograms"], value=hist_value, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=False if DEBUG else eph)
        return
    else :
        embed = discord.Embed(
            title=messages["stats_hard_title"].format(name=interaction.user.display_name),
            color=discord.Color.yellow()
        )
        # add profile
        avatar_url = interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url

        embed.set_author(name=interaction.user.display_name, icon_url=avatar_url)
        avg_perf = calculate_mean(user_data[key],hard=True)
        name = messages["player_hard_stats"]
        value = messages["stats_hard"].format(score=data['score'], played=str(data['hardmode_games']), wins = str(data['hardmode_successes']), streak = str(data['hardmode_streak']), max_streak=str(data['hardmode_max_streak']), wr = str(round(data['hardmode_successes'] / data['hardmode_games'] * 100, 2)), avg = str(round(avg_perf, 2)))
        embed.add_field(name=name, value=value, inline=False)
        hist_out, max_val = render_histogram(user_data[key], hard=True)
        values = get_values(user_data[key], hard=True)

        # count failures
        failures = data["hardmode_games"] - sum(int(v) for v in values)

        fail_bar = None
        if max_val == 0:
            fail_bar = 0
        else:
            fail_bar = int((failures / max_val) * 8)
            fail_bar = max(fail_bar, 1) if failures > 0 else 0  # display at least 1 (with nonzero)
        # print hist
        hist_value = (
            ":one: | " + ":red_square:" * hist_out[0] + f" ({values[0]})\n" +
            ":two: | " + ":red_square:" * hist_out[1] + f" ({values[1]})\n" +
            ":three: | " + ":red_square:" * hist_out[2] + f" ({values[2]})\n" +
            ":four: | " + ":red_square:" * hist_out[3] + f" ({values[3]})\n" +
            ":five: | " + ":red_square:" * hist_out[4] + f" ({values[4]})\n" +
            ":six: | " + ":red_square:" * hist_out[5] + f" ({values[5]})\n" +
            ":regional_indicator_x: | " + ":yellow_square:" * fail_bar + f" ({failures})\n"
        )
        embed.add_field(name=messages["histograms"], value=hist_value, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=False if DEBUG else eph)
        return

@tree.command(name="leaderboard", description=messages["desc_leaderboard"])
async def leaderboard(interaction: discord.Interaction, share: bool = False):
    guild_users = [
        (uid, data, calculate_mean(data))
        for (gid, uid), data in user_data.items()
        if gid == interaction.guild_id and data["games_played"] > 0
    ]

    if not guild_users:
        await interaction.response.send_message(messages["no_leaderboard_data"], ephemeral=False if DEBUG else True)
        return

    guild_users.sort(key=lambda x: (-x[1]["score"], x[2]))

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
        "🏅 | 👤 User     | 🪙 SCORE | 💪 HMR | 📈 WR  | 📌 AVG\n"
        "------------------------------------------------------\n"
    )

    for idx, (uid, data, avg_perf) in enumerate(guild_users[:10], start=1):
        member = interaction.guild.get_member(uid)
        full_name = str(member) if member else "Unknown"
        full_name = truncate_name(full_name, 11)

        wins = data["wins"]
        wr = round(wins / data["games_played"] * 100, 1)
        avg = round(avg_perf, 2)
        score = data.get("score", 0)
        hmode = data.get("hardmode_successes", 0)
        hmr = round(hmode/wins * 100, 1)
        leaderboard_text += messages["leaderboard_rank"][idx]
        leaderboard_text += f" | {full_name:<11} | {score:>8.1f} | {hmr:>5.1f}% | {wr:>5.1f}% | {avg:>6.2f}\n"

    embed.description = f"```{leaderboard_text}```"

    eph = not share
    await interaction.response.send_message(embed=embed, ephemeral=False if DEBUG else eph)


@tree.command(name="reload", description=messages["desc_reload"])
@discord.app_commands.checks.has_permissions(administrator=True)
async def reload(interaction: discord.Interaction):
    try:
        await initialize_bot()
        await interaction.response.send_message(messages["reload_success"], ephemeral=True)
    except Exception as e:
        print(f"[ERROR] reload 실패: {e}")
        await interaction.response.send_message(messages["reload_error"], ephemeral=True)

@reload.error
async def reload_error(interaction: discord.Interaction, e):
    if isinstance(e, discord.app_commands.errors.MissingPermissions):
        await interaction.response.send_message(messages["rmdirnoperm"], ephemeral=True)
    else:
        await interaction.response.send_message(messages["reload_error"], ephemeral=True)

@tree.command(name="help", description=messages["desc_help"])
async def help(interaction: discord.Interaction):
    embed = discord.Embed(
        title=messages["embed_help"],
        color=discord.Color.blue()
    )
    embed.add_field(name="", value=messages["list_help"], inline=False)


    await interaction.response.send_message(embed=embed, ephemeral=True)

# ========== event ==========
@client.event
async def on_ready():
    print(f"Logged in as {client.user}") 
    await initialize_bot()
    asyncio.create_task(start_daily_reset_task())

# ========== run bot ==========
client.run(os.environ.get("DISCORD_BOT_TOKEN"))

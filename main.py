import os
import discord
from discord.ext import commands
from discord.ui import View, Button
import requests
from datetime import datetime, timedelta
from collections import defaultdict
from flask import Flask
from threading import Thread
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TEAMUP_API_KEY = os.getenv("TEAMUP_API_KEY")
CALENDAR_ID = os.getenv("CALENDAR_ID")
SUBCALENDAR_ID = None  # ou int si besoin

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

def get_week_range(offset=0):
    today = datetime.utcnow()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
    sunday = monday + timedelta(days=6)
    return monday, sunday

def fetch_subcalendars():
    url = f"https://api.teamup.com/{CALENDAR_ID}/subcalendars"
    headers = {"Teamup-Token": TEAMUP_API_KEY}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json().get("subcalendars", [])

def fetch_events(start_date, end_date):
    url = f"https://api.teamup.com/{CALENDAR_ID}/events"
    headers = {"Teamup-Token": TEAMUP_API_KEY}
    params = {
        "startDate": start_date.strftime('%Y-%m-%d'),
        "endDate": end_date.strftime('%Y-%m-%d')
    }
    if SUBCALENDAR_ID:
        params['subcalendarId'] = SUBCALENDAR_ID

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json().get("events", [])

def create_events_embed(events, start_date, end_date, week_offset, subcalendars):
    embed = discord.Embed(
        title=f"📅 Events from {start_date.strftime('%d %B')} to {end_date.strftime('%d %B %Y')}",
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Week starting the {start_date.strftime('%d/%m')} • Offset: {week_offset}")

    if not events:
        embed.description = "Nothing this week"
        return embed

    sub_dict = {sub["id"]: sub["name"] for sub in subcalendars}
    events.sort(key=lambda ev: ev.get("start_dt", ""))
    daily_events = defaultdict(list)

    for ev in events:
        start_str = ev.get("start_dt", "")
        if not start_str:
            continue
        date_obj = datetime.strptime(start_str[:10], "%Y-%m-%d")
        weekday = date_obj.strftime("%A")
        daily_events[weekday].append(ev)

    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
        if day in daily_events:
            embed.add_field(name=f"📅 {day}", value="‎", inline=False)
            for ev in daily_events[day]:
                title = ev.get("title", "Untitled")
                start = ev.get("start_dt", "??")[:16].replace("T", " ")
                location = ev.get("location", "")
                notes = ev.get("notes", "")
                sub_id = ev.get("subcalendar_id")
                calendar = sub_dict.get(sub_id, "Unknown category")

                value = f"📍 {start}\n🏷️ Catégorie : `{calendar}`"
                if location:
                    value += f"\n📌 Location : {location}"
                if notes:
                    value += f"\n📝 {notes[:100]}{'...' if len(notes) > 100 else ''}"

                embed.add_field(name=title, value=value, inline=False)

    return embed

class WeekView(View):
    def __init__(self, week_offset: int):
        super().__init__(timeout=None)
        self.week_offset = week_offset

    @discord.ui.button(label="◀️ Last week", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: Button):
        self.week_offset -= 1
        await self.update(interaction)

    @discord.ui.button(label="🔄 Current week", style=discord.ButtonStyle.success)
    async def this_week(self, interaction: discord.Interaction, button: Button):
        self.week_offset = 0
        await self.update(interaction)

    @discord.ui.button(label="▶️ Next week", style=discord.ButtonStyle.primary)
    async def next(self, interaction: discord.Interaction, button: Button):
        self.week_offset += 1
        await self.update(interaction)

    async def update(self, interaction: discord.Interaction):
        start_date, end_date = get_week_range(self.week_offset)
        try:
            events = fetch_events(start_date, end_date)
            subcalendars = fetch_subcalendars()
            embed = create_events_embed(events, start_date, end_date, self.week_offset, subcalendars)
            await interaction.response.edit_message(embed=embed, view=WeekView(self.week_offset))
        except Exception as e:
            await interaction.response.send_message(f"❌ Erreur : {str(e)}", ephemeral=True)

@bot.command()
async def week(ctx):
    week_offset = 0
    start_date, end_date = get_week_range(week_offset)
    try:
        events = fetch_events(start_date, end_date)
        subcalendars = fetch_subcalendars()
        embed = create_events_embed(events, start_date, end_date, week_offset, subcalendars)
        await ctx.send(embed=embed, view=WeekView(week_offset))
    except Exception as e:
        await ctx.send(f"❌ Échec : {e}")

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user.name}")
    await bot.change_presence(activity=discord.Streaming(name="ExO Schedule", url="https://www.tiktok.com/@ExOblivioneOW"))

# Petit serveur Flask pour garder en vie
app = Flask('')
@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()
bot.run(DISCORD_TOKEN)
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
# bot.py
import os
import json
import random
import asyncio
import discord
from discord.ext import commands

# ---------- CONFIG ----------
TOKEN = os.getenv("DISCORD_TOKEN")
MOD_ROLE_NAME = os.getenv("MOD_ROLE_NAME")  # optional role name, e.g. "Moderator"
MOD_IDS_RAW = os.getenv("MOD_IDS")          # optional: comma-separated user IDs
MOD_IDS = [int(x) for x in MOD_IDS_RAW.split(",")] if MOD_IDS_RAW else []

XP_FILE = "xp.json"
PREFIX = "!"

# ---------- INTENTS ----------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# ---------- XP STORAGE ----------
def load_xp():
    try:
        with open(XP_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_xp(data):
    with open(XP_FILE, "w") as f:
        json.dump(data, f)

xp_data = load_xp()

def add_xp(user_id: int, amount: int):
    key = str(user_id)
    xp_data[key] = xp_data.get(key, 0) + amount
    save_xp(xp_data)
    return xp_data[key]

def get_xp(user_id: int):
    return xp_data.get(str(user_id), 0)

# ---------- MOD CHECK ----------
def is_mod(member: discord.Member):
    # 1) owner-like permissions
    if member.guild_permissions.manage_guild or member.guild_permissions.administrator:
        return True
    # 2) role name match
    if MOD_ROLE_NAME:
        for r in member.roles:
            if r.name == MOD_ROLE_NAME:
                return True
    # 3) explicit ID list
    if member.id in MOD_IDS:
        return True
    return False

# ---------- BOT EVENTS ----------
@bot.event
async def on_ready():
    print(f"Bot ready: {bot.user} (guilds: {len(bot.guilds)})")

# ---------- COMMANDS ----------
@bot.command(name="xp")
async def xp_cmd(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"**{member.display_name}** has **{get_xp(member.id)} XP**.")

@bot.command(name="leaderboard", aliases=["lb"])
async def leaderboard(ctx):
    items = sorted(xp_data.items(), key=lambda kv: kv[1], reverse=True)
    if not items:
        await ctx.send("No XP yet.")
        return
    text = "**🏆 Leaderboard**\n"
    medals = ["🥇","🥈","🥉"]
    for i, (uid, xp) in enumerate(items[:10], start=1):
        user = ctx.guild.get_member(int(uid))
        name = user.display_name if user else uid
        medal = medals[i-1] if i <=3 else f"{i}."
        text += f"{medal} **{name}** — {xp} XP\n"
    await ctx.send(text)

@bot.command(name="award")
async def award(ctx, member: discord.Member, amount: int):
    if not is_mod(ctx.author):
        await ctx.send("⛔ You must be a mod to award XP.")
        return
    new = add_xp(member.id, amount)
    await ctx.send(f"✅ Awarded **{amount} XP** to **{member.display_name}**. New total: **{new} XP**")

# ---------- GAMES (button menu) ----------
class GamesView(discord.ui.View):
    def __init__(self, timeout=60):
        super().__init__(timeout=timeout)

    @discord.ui.button(label="Trivia 🤔", style=discord.ButtonStyle.primary)
    async def trivia_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        questions = [
            ("What is the capital of France?", "paris"),
            ("2 + 2 * 2 = ?", "6"),
            ("Which planet is known as the Red Planet?", "mars"),
        ]
        q, a = random.choice(questions)
        await interaction.followup.send(f"**Trivia:** {q}\n(First correct answer gets **10 XP**.)")
        def check(m):
            return m.channel.id == interaction.channel_id and m.content.lower().strip() == a and not m.author.bot
        try:
            msg = await bot.wait_for("message", timeout=20.0, check=check)
            new = add_xp(msg.author.id, 10)
            await interaction.followup.send(f"🎉 {msg.author.mention} answered correctly and gets **10 XP**! Total: **{new} XP**")
        except asyncio.TimeoutError:
            await interaction.followup.send("⏱️ Time's up — no correct answers.")

    @discord.ui.button(label="Typing 📝", style=discord.ButtonStyle.secondary)
    async def typing_button(self, button, interaction):
        await interaction.response.defer()
        phrase = random.choice(["pineapple", "fastcar", "hello world", "discord bot"])
        await interaction.followup.send(f"Type exactly: **{phrase}**\n(First correct typer gets **8 XP**.)")
        def check(m):
            return m.channel.id == interaction.channel_id and m.content.strip() == phrase and not m.author.bot
        try:
            msg = await bot.wait_for("message", timeout=15.0, check=check)
            new = add_xp(msg.author.id, 8)
            await interaction.followup.send(f"✅ {msg.author.mention} typed it first and gets **8 XP**! Total: **{new} XP**")
        except asyncio.TimeoutError:
            await interaction.followup.send("⏱️ No one typed it in time.")

    @discord.ui.button(label="Dice 🎲", style=discord.ButtonStyle.success)
    async def dice_button(self, button, interaction):
        await interaction.response.defer()
        roll = random.randint(1, 6)
        new = add_xp(interaction.user.id, roll)  # award XP equal to roll
        await interaction.followup.send(f"{interaction.user.mention} rolled a **{roll}** and received **{roll} XP**. Total: **{new} XP**")

@bot.command(name="games")
async def games(ctx):
    """Show games menu"""
    view = GamesView()
    await ctx.send("Choose a game — anyone can click a button to play:", view=view)

# ---------- SAFETY: command to reset or show xp file (mods only) ----------
@bot.command(name="xp_reset")
async def xp_reset(ctx):
    if not is_mod(ctx.author):
        await ctx.send("⛔ Only mods.")
        return
    global xp_data
    xp_data = {}
    save_xp(xp_data)
    await ctx.send("✅ XP data reset.")

# ---------- RUN ----------
if __name__ == "__main__":
    if not TOKEN:
        print("Missing DISCORD_TOKEN env var")
    else:
        bot.run(TOKEN)

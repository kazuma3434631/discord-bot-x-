import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import re
import aiohttp
import json # データを保存するために使うよ
from keep_alive import keep_alive

# --- 1. 初期設定とデータ管理 ---
intents = discord.Intents.default()
intents.message_content = True 

DATA_FILE = "data.json"

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

class XSpecificBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
        # 起動時にファイルを読み込むわにゃ
        self.target_accounts = load_data() 
        self.target_channel_id = 1475873866093170749
        self.boot_msg_channel_id = 1475867868724854814
        self.booted = False
        self.sent_urls = []

    async def setup_hook(self):
        self.check_x_task.start()
        await self.tree.sync()

    # --- 2. X（ミラーサイトRSS）監視ロジック ---
    @tasks.loop(minutes=3) 
    async def check_x_task(self):
        if not self.target_accounts or not self.target_channel_id:
            return

        instances = [
            "nitter.net", "nitter.cz", "nitter.privacydev.net", 
            "nitter.no-logs.com", "nitter.perennialte.ch", "nitter.ca"
        ]
        
        async with aiohttp.ClientSession() as session:
            for x_id, last_id in self.target_accounts.items():
                success = False
                for instance in instances:
                    rss_url = f"https://{instance}/{x_id}/rss?include_replies=on"
                    try:
                        headers = {"User-Agent": "Mozilla/5.0"}
                        async with session.get(rss_url, timeout=10, headers=headers) as resp:
                            if resp.status == 200:
                                content = await resp.text()
                                match = re.search(r'status/(\d+)', content)
                                if match:
                                    current_id = match.group(1)
                                    
                                    if last_id is None:
                                        self.target_accounts[x_id] = current_id
                                        save_data(self.target_accounts) # IDを覚えたら保存
                                        success = True
                                        break
                                    
                                    if current_id != last_id:
                                        tweet_url = f"https://x.com/{x_id}/status/{current_id}"
                                        if tweet_url not in self.sent_urls:
                                            channel = self.get_channel(self.target_channel_id)
                                            if channel:
                                                await channel.send(tweet_url)
                                            self.sent_urls.append(tweet_url)
                                            if len(self.sent_urls) > 20: self.sent_urls.pop(0)
                                        
                                        self.target_accounts[x_id] = current_id
                                        save_data(self.target_accounts) # 更新したら保存
                                    success = True
                                break 
                    except:
                        continue

# --- 3. 管理用コマンド（管理者限定・保存機能付き） ---

bot = XSpecificBot()

@bot.tree.command(name="x_add", description="【管理者限定】監視するアカウントを追加するよ")
@app_commands.describe(user_id="追加したいXのID（@なし）")
@app_commands.checks.has_permissions(administrator=True)
async def x_add(it: discord.Interaction, user_id: str):
    await it.response.defer(ephemeral=True)
    target_id = user_id.lower()
    if target_id not in bot.target_accounts:
        bot.target_accounts[target_id] = None
        save_data(bot.target_accounts) # 追加時に保存わにゃ！
        msg = f"✅ わにゃっ！ **@{target_id}** さんをリストに入れたよ！"
        
        count = len(bot.target_accounts)
        activity = discord.Activity(type=discord.ActivityType.watching, name=f"{count}人の最新ニュース")
        await bot.change_presence(activity=activity)
    else:
        msg = f"⚠️ @{target_id} はもうリストに入っているよ！"
    await it.followup.send(msg, ephemeral=True)

@bot.tree.command(name="x_list", description="【管理者限定】今監視しているアカウントを表示するよ")
@app_commands.checks.has_permissions(administrator=True)
async def x_list(it: discord.Interaction):
    if not bot.target_accounts:
        return await it.response.send_message("❌ 監視中のアカウントはないわにゃ。", ephemeral=True)
    account_list = "\n".join([f"・@{uid}" for uid in bot.target_accounts.keys()])
    await it.response.send_message(f"📋 **現在監視中のリストわにゃ:**\n{account_list}", ephemeral=True)

@bot.tree.command(name="x_clear", description="【管理者限定】監視リストを空にするよ")
@app_commands.checks.has_permissions(administrator=True)
async def x_clear(it: discord.Interaction):
    bot.target_accounts = {}
    save_data(bot.target_accounts) # 空にした状態を保存
    bot.sent_urls = []
    await it.response.send_message("🧹 監視リストをきれいにしたよ！", ephemeral=True)

@bot.event
async def on_ready():
    print(f"Logged in: {bot.user.name}")
    if not bot.booted:
        channel = bot.get_channel(bot.boot_msg_channel_id)
        if channel:
            await channel.send("📢 **お知らせワドルディ、起動したわにゃ！**")
        bot.booted = True

    # 起動時に保存データから人数を計算してステータスを出すよ
    count = len(bot.target_accounts)
    activity = discord.Activity(type=discord.ActivityType.watching, name=f"{count}人の最新ニュース")
    await bot.change_presence(activity=activity)

# --- 4. 実行 ---
keep_alive() 
try:
    bot.run(os.getenv('DISCORD_TOKEN'))
except Exception as e:
    print(f"Error: {e}")

import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import re
import aiohttp
import datetime
from datetime import timezone, timedelta
from keep_alive import keep_alive

# --- 1. 初期設定 ---
intents = discord.Intents.default()
intents.message_content = True 

class XSpecificBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
        # 監視情報を保持する変数
        self.target_x_id = None
        self.target_channel_id = None
        self.last_status_id = None

    async def setup_hook(self):
        # ここで self. をつけて呼び出すので、下の関数もクラスの中に必要
        self.check_x_task.start()
        await self.tree.sync()

    # --- 2. X（ミラーサイトRSS）監視ロジック ---
    # クラスの中に入れたので、第一引数に「self」を追加するよ
    @tasks.loop(minutes=3) 
    async def check_x_task(self): # ← self を追加
        if not self.target_x_id or not self.target_channel_id:
            return

        instances = ["nitter.net", "nitter.cz", "nitter.privacydev.net"]
        
        async with aiohttp.ClientSession() as session:
            for instance in instances:
                rss_url = f"https://{instance}/{self.target_x_id}/rss"
                try:
                    async with session.get(rss_url, timeout=10) as resp:
                        if resp.status == 200:
                            content = await resp.text()
                            match = re.search(r'status/(\d+)', content)
                            if match:
                                current_id = match.group(1)
                                
                                if self.last_status_id is None:
                                    self.last_status_id = current_id
                                    break
                                
                                if current_id != self.last_status_id:
                                    channel = self.get_channel(self.target_channel_id)
                                    if channel:
                                        tweet_url = f"https://x.com/{self.target_x_id}/status/{current_id}"
                                        await channel.send(f"🌟 **@{self.target_x_id} さんの新しい投稿！**\n{tweet_url}")
                                    self.last_status_id = current_id
                            break 
                except:
                    continue 

# クラスの外でBotを起動
bot = XSpecificBot()

# --- 3. 管理用コマンド ---
@bot.tree.command(name="x_setup", description="監視するアカウントとチャンネルをセットするよ")
@app_commands.describe(user_id="監視したいXのID（@なし）", channel="通知を送るチャンネル")
@app_commands.checks.has_permissions(administrator=True)
async def x_setup(it: discord.Interaction, user_id: str, channel: discord.TextChannel):
    # bot経由でクラス内の変数にアクセス
    bot.target_x_id = user_id
    bot.target_channel_id = channel.id
    bot.last_status_id = None 
    
    await it.response.send_message(
        f"✅ 設定したよ！\nこれからは {channel.mention} で **@{user_id}** さんを監視するね！",
        ephemeral=True
    )

@bot.event
async def on_ready():
    print(f"Logged in: {bot.user.name}")
    activity = discord.Activity(type=discord.ActivityType.watching, name="X (Twitter)")
    await bot.change_presence(activity=activity)

# --- 4. 実行 ---
keep_alive() 
try:
    bot.run(os.getenv('DISCORD_TOKEN'))
except Exception as e:
    print(f"Error: {e}")

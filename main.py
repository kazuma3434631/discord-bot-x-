import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import re
import aiohttp
import asyncio
from keep_alive import keep_alive

# --- 1. 初期設定 ---
intents = discord.Intents.default()
intents.message_content = True 

class XSpecificBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
        self.target_accounts = {} 
        self.target_channel_id = None
        self.booted = False # 起動メッセージを1回だけ送るためのフラグ

    async def setup_hook(self):
        self.check_x_task.start()
        await self.tree.sync()

    # --- 2. X（ミラーサイトRSS）監視ロジック ---
    @tasks.loop(minutes=3) 
    async def check_x_task(self):
        if not self.target_accounts or not self.target_channel_id:
            return

        instances = [
            "nitter.net", 
            "nitter.cz",
            "nitter.privacydev.net", 
            "nitter.no-logs.com",
            "nitter.perennialte.ch",
            "nitter.ca"
        ]
        
        async with aiohttp.ClientSession() as session:
            for x_id, last_id in self.target_accounts.items():
                success = False
                for instance in instances:
                    rss_url = f"https://{instance}/{x_id}/rss"
                    try:
                        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
                        async with session.get(rss_url, timeout=10, headers=headers) as resp:
                            if resp.status == 200:
                                content = await resp.text()
                                match = re.search(r'status/(\d+)', content)
                                if match:
                                    current_id = match.group(1)
                                    
                                    if last_id is None:
                                        print(f"📦 @{x_id} の初期IDを確認したわにゃ！")
                                        self.target_accounts[x_id] = current_id
                                        success = True
                                        break
                                    
                                    if current_id != last_id:
                                        channel = self.get_channel(self.target_channel_id)
                                        if channel:
                                            tweet_url = f"https://x.com/{x_id}/status/{current_id}"
                                            await channel.send(f"📢 **お知らせわにゃ！**\n**@{x_id}** さんが新しくポストしたよ！\n{tweet_url}")
                                        self.target_accounts[x_id] = current_id
                                    success = True
                                break 
                    except:
                        continue
                if not success:
                    print(f"⚠️ @{x_id} の情報が取得できなかったわにゃ。")

# クラスの外でBotを起動
bot = XSpecificBot()

# --- 3. 管理用コマンド ---

@bot.tree.command(name="x_add", description="監視するアカウントを追加するよ")
@app_commands.describe(user_id="追加したいXのID（@なし）", channel="通知を送るチャンネル")
@app_commands.checks.has_permissions(administrator=True)
async def x_add(it: discord.Interaction, user_id: str, channel: discord.TextChannel):
    # 待ち時間を回避する defer を追加！
    await it.response.defer(ephemeral=True)
    
    bot.target_channel_id = channel.id
    if user_id not in bot.target_accounts:
        bot.target_accounts[user_id] = None
        msg = f"✅ わにゃっ！ **@{user_id}** さんのお知らせを届ける準備ができたよ！"
        
        count = len(bot.target_accounts)
        activity = discord.Activity(type=discord.ActivityType.watching, name=f"{count}人の最新ニュース")
        await bot.change_presence(activity=activity)
    else:
        msg = f"⚠️ @{user_id} はもうリストに入っているよ！"
    
    await it.followup.send(msg, ephemeral=True)

@bot.event
async def on_ready():
    print(f"Logged in: {bot.user.name}")
    
    # --- 起動メッセージ機能 ---
    if not bot.booted:
        # 最後に登録されたチャンネルがあれば、そこに挨拶を送るわにゃ
        if bot.target_channel_id:
            channel = bot.get_channel(bot.target_channel_id)
            if channel:
                await channel.send("📢 **お知らせワドルディ、起動したわにゃ！**\nパトロールを始めるよ。よろしくね！")
        
        bot.booted = True # 重複送信防止

    count = len(bot.target_accounts)
    activity = discord.Activity(type=discord.ActivityType.watching, name=f"{count}人の最新ニュース")
    await bot.change_presence(activity=activity)

# --- 4. 実行 ---
keep_alive() 
try:
    bot.run(os.getenv('DISCORD_TOKEN'))
except Exception as e:
    print(f"Error: {e}")

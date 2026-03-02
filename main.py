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
        # 監視情報を辞書で管理 { "ユーザーID": "最新投稿ID" }
        self.target_accounts = {} 
        self.target_channel_id = None

    async def setup_hook(self):
        # 監視タスクを開始
        self.check_x_task.start()
        # スラッシュコマンドを同期
        await self.tree.sync()

    # --- 2. X（ミラーサイトRSS）監視ロジック ---
    @tasks.loop(minutes=3) 
    async def check_x_task(self):
        if not self.target_accounts or not self.target_channel_id:
            return

        # ミラーサイトのリスト（安定性を高めるために複数用意）
        instances = ["nitter.net", "nitter.cz", "nitter.privacydev.net"]
        
        async with aiohttp.ClientSession() as session:
            # 登録されているすべてのアカウントをループで確認
            for x_id, last_id in self.target_accounts.items():
                success = False
                for instance in instances:
                    rss_url = f"https://{instance}/{x_id}/rss"
                    try:
                        async with session.get(rss_url, timeout=10) as resp:
                            if resp.status == 200:
                                content = await resp.text()
                                # 最新の投稿ID（status/数字）を抽出
                                match = re.search(r'status/(\d+)', content)
                                if match:
                                    current_id = match.group(1)
                                    
                                    # 初回取得時は保存のみ（過去分の一斉通知防止）
                                    if last_id is None:
                                        self.target_accounts[x_id] = current_id
                                        success = True
                                        break
                                    
                                    # 新しい投稿（リポスト含む）が見つかった場合
                                    if current_id != last_id:
                                        channel = self.get_channel(self.target_channel_id)
                                        if channel:
                                            tweet_url = f"https://x.com/{x_id}/status/{current_id}"
                                            # お知らせワドルディのメッセージ！
                                            await channel.send(f"📢 **お知らせわにゃ！**\n**@{x_id}** さんが新しくポストしたよ！\n{tweet_url}")
                                        self.target_accounts[x_id] = current_id
                                    success = True
                                break 
                    except:
                        continue
                if not success:
                    print(f"Failed to fetch updates for @{x_id}")

# クラスの外でBotを起動
bot = XSpecificBot()

# --- 3. 管理用コマンド ---

@bot.tree.command(name="x_add", description="監視するアカウントを追加するよ")
@app_commands.describe(user_id="追加したいXのID（@なし）", channel="通知を送るチャンネル")
@app_commands.checks.has_permissions(administrator=True)
async def x_add(it: discord.Interaction, user_id: str, channel: discord.TextChannel):
    bot.target_channel_id = channel.id
    
    if user_id not in bot.target_accounts:
        bot.target_accounts[user_id] = None
        msg = f"✅ わにゃっ！ **@{user_id}** さんのお知らせを届ける準備ができたよ！"
        
        # ステータスをお知らせ活動風に更新
        count = len(bot.target_accounts)
        activity = discord.Activity(type=discord.ActivityType.watching, name=f"{count}人の最新ニュース")
        await bot.change_presence(activity=activity)
    else:
        msg = f"⚠️ @{user_id} はもうリストに入っているよ！"
    
    await it.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="x_list", description="今監視しているアカウントを表示するよ")
async def x_list(it: discord.Interaction):
    if not bot.target_accounts:
        return await it.response.send_message("❌ 監視中のアカウントはないわにゃ。", ephemeral=True)
    
    account_list = "\n".join([f"・@{uid}" for uid in bot.target_accounts.keys()])
    await it.response.send_message(f"📋 **現在監視中のリストわにゃ:**\n{account_list}", ephemeral=True)

@bot.tree.command(name="x_clear", description="監視リストを空にするよ")
@app_commands.checks.has_permissions(administrator=True)
async def x_clear(it: discord.Interaction):
    bot.target_accounts = {}
    await it.response.send_message("🧹 監視リストをきれいにしたよ！また教えてね。", ephemeral=True)

@bot.event
async def on_ready():
    print(f"Logged in: {bot.user.name} (お知らせワドルディ起動！)")
    count = len(bot.target_accounts)
    activity = discord.Activity(type=discord.ActivityType.watching, name=f"{count}人の最新ニュース")
    await bot.change_presence(activity=activity)

# --- 4. 実行 ---
keep_alive() 
try:
    bot.run(os.getenv('DISCORD_TOKEN'))
except Exception as e:
    print(f"Error: {e}")

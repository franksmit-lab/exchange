# -*- coding: utf-8 -*-
"""
Discord 匯率小助手（Slash Commands + Gemini 分析）
使用免費 exchangerate.host API Key
"""

import discord
from discord import app_commands
from discord.ext import commands
import requests
import pandas as pd
import matplotlib.pyplot as plt
import io
import google.generativeai as genai
from datetime import datetime, timedelta
import os


# -----------------------
# 本地測試用 Key
# -----------------------
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
EXCHANGE_API_KEY = os.environ["EXCHANGE_API_KEY"]


# 初始化 Gemini
genai.configure(api_key=GEMINI_API_KEY)

# 建立 Bot
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree  # 用來建立 Slash Commands

# -----------------------
# /rate 即時匯率
# -----------------------
@tree.command(name="rate", description="查即時匯率")
@app_commands.describe(base="基準貨幣", target="目標貨幣")
async def rate(interaction: discord.Interaction, base: str = "USD", target: str = "TWD"):
    base = base.upper()
    target = target.upper()
    fx_url = f"https://api.exchangerate.host/convert?from={base}&to={target}&amount=1&access_key={EXCHANGE_API_KEY}"
    try:
        res = requests.get(fx_url).json()
        result = res.get("result")
        if result is not None:
            await interaction.response.send_message(f"1 {base} ≈ **{result:.4f} {target}**")
        else:
            await interaction.response.send_message(f"取得匯率失敗，API 回傳：{res}")
    except Exception as e:
        await interaction.response.send_message(f"取得匯率失敗：{e}")

# -----------------------
# /history 歷史匯率圖表（用 /convert 迴圈抓最近 N 天）
# -----------------------
@tree.command(name="history", description="查指定日期的匯率")
@app_commands.describe(base="基準貨幣", target="目標貨幣", date="日期 (YYYY-MM-DD)")
async def history(interaction: discord.Interaction, base: str = "USD", target: str = "TWD", date: str = None):
    base = base.upper()
    target = target.upper()
    
    # 如果沒輸入日期，預設今天
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    try:
        # 呼叫 exchangerate.host /convert API
        url = f"https://api.exchangerate.host/convert?from={base}&to={target}&amount=1&date={date}&access_key={EXCHANGE_API_KEY}"
        res = requests.get(url).json()
        rate = res.get("result")
        
        if rate is not None:
            await interaction.response.send_message(f"{base} → {target} 匯率 ({date}) ：{rate:.4f}")
        else:
            await interaction.response.send_message(f"{date} 沒有取得匯率資料")
            
    except Exception as e:
        await interaction.response.send_message(f"取得匯率失敗：{e}")

# -----------------------
# /advice Gemini 分析
# -----------------------
@tree.command(name="advice", description="Gemini 分析是否適合現在買")
@app_commands.describe(base="基準貨幣", target="目標貨幣", days="參考天數 (最大30天)")
async def advice(interaction: discord.Interaction, base: str = "USD", target: str = "TWD", days: int = 7):
    await interaction.response.defer()  # 延遲回覆，給 Gemini API 時間
    base = base.upper()
    target = target.upper()
    days = min(days, 30)
    end_date = datetime.now()
    rates = {}

    try:
        # 迴圈抓最近 N 天的即時匯率
        for i in range(days):
            date = (end_date - timedelta(days=i)).strftime("%Y-%m-%d")
            url = f"https://api.exchangerate.host/convert?from={base}&to={target}&amount=1&date={date}&access_key={EXCHANGE_API_KEY}"
            res = requests.get(url).json()
            rate = res.get("result")
            if rate:
                rates[date] = rate

        if not rates:
            await interaction.followup.send("取得歷史匯率失敗")
            return

        df = pd.DataFrame(list(rates.items()), columns=["date", "rate"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        # Gemini prompt
        prompt = f"""
你是一個溫柔且具有金融常識的小助手。
請分析以下匯率資訊，並用親切、簡單的語氣回答：
1. 匯率是否上升或下降趨勢
2. 現在匯率偏高還是偏低
3. 是否適合現在買
4. 一句貼心建議

即時匯率：1 {base} = {rates[max(rates.keys())]:.4f} {target}
過去 {days} 天匯率：
{df.tail(days).to_string(index=False)}
"""
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        await interaction.followup.send(response.text)

    except Exception as e:
        await interaction.followup.send(f"Gemini 分析失敗: {e}")

# -----------------------
# 啟動 Bot 並同步 Slash Commands
# -----------------------
@bot.event
async def on_ready():
    print(f"Bot 已上線：{bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"已同步 {len(synced)} 個 slash commands")
    except Exception as e:
        print(e)

bot.run(DISCORD_TOKEN)

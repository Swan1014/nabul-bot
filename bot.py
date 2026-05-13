import discord
from discord.ext import tasks, commands
from discord import app_commands
import os
from dotenv import load_dotenv
import datetime
from keep_alive import keep_alive

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

bot = commands.Bot(command_prefix='!', intents=intents)

# 오늘 워들을 한 사람의 ID를 저장할 바구니
done_today = set()

# 채널 ID
TARGET_CHANNEL_ID = 1412657432664215602

# 한국 시간(KST) 밤 11시(23시 0분)로 알림 시간 설정
KST = datetime.timezone(datetime.timedelta(hours=9))
alert_time = datetime.time(hour=23, minute=00, tzinfo=KST)

@bot.event
async def on_ready():
    print(f'짜잔! {bot.user} 봇이 온라인 상태가 되었습니다!')

    try:
        synced = await bot.tree.sync()
        print(f"슬래시 명령어 {len(synced)}개 동기화 완료!")
    except Exception as e:
        print(f"명령어 동기화 실패... {e}")

    check_wordle.start() # 봇이 켜지면 타이머도 시작

@bot.event
async def on_message(message):
    if message.author.bot:
        if message.author.name == "Wordle" and "was playing" in message.content:
            nickname = message.content.replace(" was playing", "").strip()
            
            found_user = None
            for member in message.guild.members:
                if member.display_name == nickname or member.name == nickname:
                    found_user = member
                    break
            
            if found_user:
                done_today.add(found_user.id)
                await message.channel.send(f"오! {found_user.display_name}님 워들 완료! (현재 {len(done_today)}명 완료)")
        return

    if "Wordle" in message.content and "🟩" in message.content:
        done_today.add(message.author.id)
        await message.channel.send(f"{message.author.display_name}님, 수동으로 워들 완료 확인! (현재 {len(done_today)}명 완료)")

    await bot.process_commands(message)

@bot.tree.command(name="나불이", description="나불이가 일하고 있는지 확인합니다.")
async def check_status(interaction: discord.Interaction):
    await interaction.response.send_messasge("네에~ 나불이 일하고 있어요😆")

# 지정된 시간(11시)에 실행되는 잔소리 기능
@tasks.loop(time=alert_time)
async def check_wordle():
# 1. 먼저 위에서 설정한 TARGET_CHANNEL_ID로 채널을 찾아봄
    target_channel = bot.get_channel(TARGET_CHANNEL_ID)
    
    # 알림을 보낼 '서버'와 '채널'의 짝을 담아둘 리스트를 만듦
    notify_list = []
    
    if target_channel:
        # 채널이 존재하면 원래 계획대로 그 채널 하나만 리스트에 넣음
        notify_list.append((target_channel.guild, target_channel))
    else:
        # 지정된 채널이 없다면? 봇이 들어가 있는 모든 서버를 순회함.
        print("경고: 설정된 채널을 찾을 수 없어 시스템 메시지 채널로 우회합니다.")
        for guild in bot.guilds:
            # 해당 서버에 시스템 메시지 채널이 켜져 있다면 리스트에 넣습니다
            if guild.system_channel: 
                notify_list.append((guild, guild.system_channel))
                
    # 2. 결정된 알림 채널들에 각각 메시지를 보냄
    for guild, channel in notify_list:
        lazy_people = []
        for member in guild.members:
            if not member.bot and member.id not in done_today:
                lazy_people.append(member)
        
        if lazy_people:
            mentions = ", ".join([member.mention for member in lazy_people])
            await channel.send(f"{mentions}! You didn't play Wordle!")
        else:
            await channel.send("오늘은 우리 서버 모두 워들을 완료했네!")
        
    # 알림을 보냈으면 바구니를 깨끗하게 비움
    done_today.clear()

keep_alive()
bot.run(TOKEN)
import discord
from discord.ext import tasks, commands
from discord import app_commands
import os
from dotenv import load_dotenv
import datetime

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

# 메시지가 수정(Edit)되었을 때 발동하는 이벤트!
@bot.event
async def on_message_edit(before, after):
    # before는 수정 전 메시지, after는 수정 후 메시지
    if after.author.bot:
        # 워들 봇이 메시지를 수정했고, 수정된 내용에 "was playing"이 있다면
        if after.author.name == "Wordle" and "was playing" in after.content:
            nickname = after.content.replace(" was playing", "").strip()
            
            found_user = None
            for member in after.guild.members:
                if member.display_name == nickname or member.name == nickname:
                    found_user = member
                    break
            
            if found_user:
                # 이미 완료 처리된 사람인지 한 번 더 확인 (중복 알림 방지)
                if found_user.id not in done_today:
                    done_today.add(found_user.id)
                    await after.channel.send(f"오! {found_user.display_name}님 워들 완료! (수정된 메시지 감지, 현재 {len(done_today)}명 완료)")

@bot.tree.command(name="나불이", description="나불이가 일하고 있는지 확인합니다.")
async def check_status(interaction: discord.Interaction):
    await interaction.response.send_message("네에~ 나불이 일하고 있어요😆")

@bot.tree.command(name="워들", description="오늘 워들을 완료한 사람과 아직 안 한 사람을 확인합니다.")
async def check_wordle_status(interaction: discord.Interaction):
    # 완료한 사람과 안 한 사람의 이름을 담을 빈 리스트 준비
    completed = []
    not_completed = []

    # 명령어를 친 서버(길드)의 모든 멤버를 한 명씩 확인
    for member in interaction.guild.members:
        if member.bot: # 나불이 같은 봇들은 검사할 필요 없으니 패스!
            continue
        
        # 바구니에 아이디가 있으면 완료 리스트로, 없으면 안 한 리스트로
        if member.id in done_today:
            completed.append(member.display_name)
        else:
            not_completed.append(member.display_name)
    
    # 디스코드에 보낼 메시지를 꾸미기
    msg = "📊 **오늘의 워들 현황** 📊\n\n"
    
    msg += f"🟩 **완료한 사람 ({len(completed)}명)**\n"
    if completed:
        msg += ", ".join(completed) + "\n"
    else:
        msg += "아직 아무도 안 했어! 다들 분발하자! 🏃‍♂️\n"
        
    msg += "\n🟥 **아직 안 한 사람**\n"
    if not_completed:
        msg += ", ".join(not_completed)
    else:
        msg += "전원 완료!"
        
    # 최종적으로 완성된 메시지를 전송
    await interaction.response.send_message(msg)

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

bot.run(TOKEN)
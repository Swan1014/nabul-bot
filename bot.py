import discord
from discord.ext import tasks, commands
from discord import app_commands
import os
from dotenv import load_dotenv
import datetime
import random
import requests
import csv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
KMA_API_KEY = os.getenv('KMA_API_KEY')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

bot = commands.Bot(command_prefix='!', intents=intents)

# 채널 ID
TARGET_CHANNEL_ID = 1412657432664215602

# 한국 시간(KST) 밤 11시(23시 0분)로 알림 시간 설정
KST = datetime.timezone(datetime.timedelta(hours=9))
alert_time = datetime.time(hour=23, minute=00, tzinfo=KST)
reset_time = datetime.time(hour=0, minute=0, tzinfo=KST)

# ==========================================
# 여기서부터 시작
# ==========================================
@bot.event
async def on_ready():
    print(f'짜잔! {bot.user} 봇이 온라인 상태가 되었습니다!')

    load_weather_area() # 날씨를 위한 지역 데이터 가져옴
    print(f"전국 날씨 좌표 {len(area_data)}개 로딩 완료!")

    try:
        synced = await bot.tree.sync()
        print(f"슬래시 명령어 {len(synced)}개 동기화 완료!")
    except Exception as e:
        print(f"명령어 동기화 실패... {e}")

    check_wordle.start() # 11시
    reset_wordle.start()

# ==========================================
# 편의성 명령어
# ==========================================
@bot.tree.command(name="나불이", description="나불이가 일하고 있는지 확인합니다.")
async def check_status(interaction: discord.Interaction):
    await interaction.response.send_message("나 불렀어? 나불이 열심히 일하고 있어 😆")

@bot.tree.command(name="핑", description="나불이의 현재 핑을 보여줍니다.")
async def check_ping(interaction: discord.Interaction):
    ping_ms = round(bot.latency * 1000) # 1000을 곱하는 이유는 초에서 밀리초 변환
    await interaction.response.send_message(f"🏓 퐁!\n`나불이의 반응 속도: {ping_ms}ms`")

@bot.tree.command(name="골라", description="선택지를 띄어쓰기로 구분하여 입력하면 나불이가 하나를 골라줍니다.")
@app_commands.describe(선택지="선택지를 띄어쓰기로 구분하여 입력하세요.")
async def choose_for_me(interaction: discord.Interaction, 선택지: str):
    # 1. 사용자가 입력한 문자열을 띄어쓰기 기준으로 잘라서 리스트로 만듦
    options = 선택지.split()

    # 2. 선택지가 1개밖에 없거나 안 적었다면 경고
    if len(options) < 2:
        await interaction.response.send_message("선택지를 2개 이상 입력해야 골라줄 수 있어!\n(예: /골라 짜장면 짬뽕)")
        return
    
    # 3. random.choice()로 리스트 안의 항목 중 하나를 무작위로 뽑음
    picked = random.choice(options)

    # 4. 결과 출력
    msg = f"나불이의 선택은... {picked}! 🎉"
    await interaction.response.send_message(msg)

# ==========================================
# 워들 명령어
# ==========================================
done_today = set() # 오늘 워들을 한 사람의 ID를 저장할 바구니

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
                await message.channel.send(f"{found_user.display_name}, 워들 완료 확인! (현재 {len(done_today)}명 완료)")
        return

    if "Wordle" in message.content and "🟩" in message.content:
        done_today.add(message.author.id)
        await message.channel.send(f"{message.author.display_name}, 수동으로 워들 완료 확인! (현재 {len(done_today)}명 완료)")

    await bot.process_commands(message)

# 메시지가 수정(Edit)되었을 때 발동하는 이벤트
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

@bot.tree.command(name="워들", description="오늘 워들을 완료한 사람과 아직 안 한 사람을 확인합니다.")
async def check_wordle_status(interaction: discord.Interaction):
    # 완료한 사람과 안 한 사람의 이름을 담을 빈 리스트 준비
    completed = []
    not_completed = []

    # 명령어를 친 서버(길드)의 모든 멤버를 한 명씩 확인
    for member in interaction.guild.members:
        if member.bot: # 나불이 같은 봇들은 검사할 필요 없으니 패스
            continue
        
        # 바구니에 아이디가 있으면 완료 리스트로, 없으면 안 한 리스트로
        if member.id in done_today:
            completed.append(member.display_name)
        else:
            not_completed.append(member.display_name)
    
    # 디스코드에 보낼 메시지를 꾸미기
    embed = discord.Embed(title="📊 오늘의 워들 현황 📊", color=0x4CE2EC)
    
    # 🟩 완료한 사람 텍스트 정리
    if completed:
        completed_text = ", ".join(completed)
    else:
        completed_text = "아직 아무도 안 했어! 다들 분발하자! 🏃‍♂️"
        
    # 🟥 아직 안 한 사람 텍스트 정리
    if not_completed:
        not_completed_text = ", ".join(not_completed)
    else:
        not_completed_text = "오늘은 모두 워들 완료!"
        
    # 상자 안에 내용(필드) 채워 넣기
    # name: 필드 소제목 / value: 실제 내용 / inline=False: 세로로 한 줄씩 차지하게 설정
    embed.add_field(name=f"🟩 완료한 사람 ({len(completed)}명)", value=completed_text, inline=False)
    embed.add_field(name=f"🟥 아직 안 한 사람 ({len(not_completed)}명)", value=not_completed_text, inline=False)
    
    # 임베드로 보낼 때는 인자 이름을 'embed'로 지정해 줘야 함
    await interaction.response.send_message(embed=embed)

# 워들 재촉 메시지 보내는 함수
def get_wordle_reminder_message(guild):
    lazy_people = []
    # 서버 멤버들을 쭉 돌면서 안 한 사람을 찾음
    for member in guild.members:
        if not member.bot and member.id not in done_today:
            lazy_people.append(member)
    
    # 안 한 사람이 있다면 멘션 텍스트 생성
    if lazy_people:
        mentions = ", ".join([member.mention for member in lazy_people])
        return f"{mentions}! You didn't play Wordle!"
    else:
        return "오늘은 모두 워들을 완료했네!"

@bot.tree.command(name="워들재촉", description="아직 워들을 안 한 사람을 멘션해서 재촉합니다.")
async def urge_wordle(interaction: discord.Interaction):
    # 위 함수를 불러와서 보낼 메시지를 받아옴
    msg = get_wordle_reminder_message(interaction.guild)
    
    # "색출 중..." 문구 없이, 바로 완성된 멘션 메시지를 한 번에 쾅! 출력
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
        msg = get_wordle_reminder_message(guild)
        await channel.send(msg)

@tasks.loop(time=reset_time)
async def reset_wordle():
    done_today.clear()
    print("자정이 되어서 워들 완료 기록을 초기화했어!")

# ==========================================
# 날씨 명령어
# ==========================================
area_data = [] # 봇이 켜질 때 전국 지역 좌표를 담아둘 바구니

# CSV 파일을 읽어서 메모리에 장전하는 함수
def load_weather_area():
    global area_data
    area_data = [] 
    
    with open('weather_area.csv', 'r', encoding='cp949') as f:
        reader = csv.reader(f)
        next(reader) 
        
        for row in reader:
            area_1 = row[2] if row[2] else ""
            area_2 = row[3] if row[3] else ""
            area_3 = row[4] if row[4] else ""
            
            # CSV 파일에 '용인시수지구' 처럼 붙어있는 문제 해결
            if "시" in area_2 and area_2.endswith("구") and " " not in area_2:
                area_2 = area_2.replace("시", "시 ")
            
            areas = [a for a in [area_1, area_2, area_3] if a]
            full_name = " ".join(areas)
            depth = len(areas) # 행정구역 깊이 저장 (1단계, 2단계, 3단계)
            
            nx = row[5]
            ny = row[6]
            
            if full_name:
                # 쪼개진 데이터(a1, a2, a3)와 깊이(depth)도 메모리에 같이 저장
                area_data.append({
                    "name": full_name, 
                    "a1": area_1, "a2": area_2, "a3": area_3, 
                    "depth": depth, "nx": nx, "ny": ny
                })

def search_coordinates(query):
    # 축약어를 정식 명칭으로 번역
    query = query.replace("경북", "경상북도").replace("경남", "경상남도")
    query = query.replace("충북", "충청북도").replace("충남", "충청남도")
    query = query.replace("전남", "전라남도")
    # 전북과 제주는 해당 글자로 시작하기 때문에 굳이 안 바꿈

    keywords = query.split() 
    query_no_space = query.replace(" ", "") 
    
    matches = []
    
    for area in area_data:
        match_all = True
        # 각 구역이 해당 단어로 '시작'하는지 검사
        for kw in keywords:
            if not (area['a1'].startswith(kw) or area['a2'].startswith(kw) or area['a3'].startswith(kw)):
                match_all = False
                break
                
        if match_all:
            matches.append(area)
            
    # Track 2: 띄어쓰기 무시 모드 (위에서 못 찾았을 때만 가동)
    if not matches:
        for area in area_data:
            area_name_no_space = area['name'].replace(" ", "")
            # startswith로 엄격하게 검사해서 '지구'가 '수지구'를 못 잡게 함
            if area_name_no_space.startswith(query_no_space):
                matches.append(area)
                
    if not matches:
        return None, None, None, "not_found"

    # 중복 결과 처리
    # 1. 뎁스가 얕은 순서대로 정렬
    matches.sort(key=lambda x: x['depth'])
    
    # 2. 1등과 뎁스가 똑같은 후보들을 모음
    best_depth = matches[0]['depth']
    top_candidates = [m for m in matches if m['depth'] == best_depth]
    
    # 3. 1등 후보가 여러 개라면?
    if len(top_candidates) > 1:
        # 중복된 이름을 제거하고 리스트로 만듦
        candidate_names = list(dict.fromkeys([c['name'] for c in top_candidates]))
        if len(candidate_names) > 1:
            # 좌표 대신 '중복'이라는 상태와 예시 리스트를 반환
            return None, None, None, candidate_names[:25] 

    best = matches[0]
    return best['nx'], best['ny'], best['name'], "success"

def get_weather(nx, ny):
    url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
    
    # 시간 계산 로직 (현재 시간이 40분 이전이면 한 시간 전 데이터 요청)
    now = datetime.datetime.now(KST)
    if now.minute < 40:
        now = now - datetime.timedelta(hours=1)
        
    base_date = now.strftime('%Y%m%d') # 예: 20240514
    base_time = now.strftime('%H00')   # 예: 0900
    
    params = {
        'serviceKey': KMA_API_KEY,
        'pageNo': '1',
        'numOfRows': '1000',
        'dataType': 'JSON',
        'base_date': base_date,
        'base_time': base_time,
        'nx': nx,
        'ny': ny
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json() # 결과를 JSON(딕셔너리) 형태로 변환
        
        # 데이터 속에서 기온(T1H) 찾기
        items = data['response']['body']['items']['item']

        weather_info = {}
        for item in items:
            cat = item['category']
            val = item['obsrValue']
            
            if cat == 'T1H':
                weather_info['temp'] = val # 기온
            elif cat == 'REH':
                weather_info['humidity'] = val # 습도
            elif cat == 'RN1':
                weather_info['rain'] = val # 강수량
            elif cat == 'WSD':
                weather_info['wind'] = val # 풍속
            elif cat == 'VEC':
                weather_info['wind_dir'] = val # 풍향
            elif cat == 'PTY':
                # PTY 코드를 텍스트와 이모지로 변환
                pty_code = val
                if pty_code == '0':
                    weather_info['status'] = "☁️ 강수 없음"
                elif pty_code == '1':
                    weather_info['status'] = "🌧️ 비"
                elif pty_code == '2':
                    weather_info['status'] = "🌨️ 비/눈"
                elif pty_code == '3':
                    weather_info['status'] = "❄️ 눈"
                elif pty_code in ['5', '6']:
                    weather_info['status'] = "💧 빗방울"
                elif pty_code == '7':
                    weather_info['status'] = "❄️ 눈날림"
                else:
                    weather_info['status'] = "🤔 알 수 없음"
            
        # 각도로 주어지는 풍향을 문자로 변환
        if 'wind_dir' in weather_info:
            vec_val = float(weather_info['wind_dir'])
            directions = ["북", "북북동", "북동", "동북동", "동", "동남동", "남동", "남남동", "남", "남남서", "남서", "서남서", "서", "서북서", "북서", "북북서"]
            idx = int((vec_val + 11.25) / 22.5) % 16
            weather_info['wind_dir_text'] = directions[idx]
            
        return weather_info
        
    except Exception as e:
        print(f"날씨 API 에러: {e}")
        return None
    
def get_forecast(nx, ny):
    url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
    
    now = datetime.datetime.now(KST)
    
    # 단기예보 발표시간: 02, 05, 08, 11, 14, 17, 20, 23 (업데이트 지연을 고려해 15분 전 시간을 기준으로 계산)
    target_time = now - datetime.timedelta(minutes=15) 
    base_times = [2, 5, 8, 11, 14, 17, 20, 23]
    
    valid_times = [t for t in base_times if target_time.hour >= t]
    
    # 자정~새벽 2시 사이면 전날 23시 데이터를 가져옴
    if not valid_times:
        target_time = target_time - datetime.timedelta(days=1)
        base_date = target_time.strftime('%Y%m%d')
        base_time = '2300'
    else:
        base_date = target_time.strftime('%Y%m%d')
        base_time = f"{valid_times[-1]:02d}00"
        
    params = {
        'serviceKey': KMA_API_KEY,
        'pageNo': '1',
        'numOfRows': '300', # 시간별 데이터를 넉넉히 가져옴 (약 하루치 이상)
        'dataType': 'JSON',
        'base_date': base_date,
        'base_time': base_time,
        'nx': nx,
        'ny': ny
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        items = data['response']['body']['items']['item']
        
        # 데이터를 [날짜_시간] 별로 예쁘게 분류할 바구니
        fcst_data = {}
        today = now.strftime('%Y%m%d')
        current_hour = now.strftime('%H00')
        
        for item in items:
            f_date = item['fcstDate']
            f_time = item['fcstTime']
            cat = item['category']
            val = item['fcstValue']
            
            key = f"{f_date}_{f_time}" # 예: "20240514_1500"
            if key not in fcst_data:
                fcst_data[key] = {}
            fcst_data[key][cat] = val
            
        return fcst_data, today, current_hour
    except Exception as e:
        print(f"예보 API 에러: {e}")
        return None, None, None
    
def create_weather_embed(full_name, weather_info, fcst_data, today_date, current_hour):
    today_tmps = []
    for key, data in fcst_data.items():
        if key.startswith(today_date) and 'TMP' in data:
            today_tmps.append(int(data['TMP']))
            
    min_t = min(today_tmps) if today_tmps else "-"
    max_t = max(today_tmps) if today_tmps else "-"

    hourly_texts = []
    sorted_keys = sorted(fcst_data.keys()) 
    
    for key in sorted_keys:
        date, time = key.split('_')
        data = fcst_data[key]
        
        if date == today_date and int(time) > int(current_hour):
            if 'TMP' in data:
                tmp = data['TMP']
                pop = data.get('POP', '0')
                sky = data.get('SKY', '1')
                pty = data.get('PTY', '0')
                
                icon = "☀️"
                if pty == '0':
                    if sky == '3': icon = "⛅"
                    elif sky == '4': icon = "☁️"
                else:
                    if pty == '1': icon = "🌧️"
                    elif pty in ['2', '3']: icon = "❄️"
                    elif pty == '4': icon = "☔"
                    
                hour_str = f"{time[:2]}시"
                hourly_texts.append(f"`{hour_str}` {icon} **{tmp}℃** (☔ {pop}%)")
                
    hourly_result = "\n".join(hourly_texts) if hourly_texts else "오늘의 남은 예보가 없습니다. 🌙"

    embed = discord.Embed(
        title=f"📍 {full_name} 날씨 정보", 
        color=0x4CE2EC,
        timestamp=datetime.datetime.now(KST)
    )
    
    embed.add_field(name="🌡️ 현재 기온", value=f"**{weather_info['temp']}℃**", inline=True)
    embed.add_field(name="💧 상태", value=f"**{weather_info['status']}**", inline=True)
    embed.add_field(name="💦 습도", value=f"**{weather_info['humidity']}%**", inline=True)
    
    embed.add_field(name="🌬️ 바람", value=f"**{weather_info['wind_dir_text']}풍 {weather_info['wind']}m/s**", inline=True)
    
    rain_val = weather_info.get('rain', '0')
    embed.add_field(name="☔ 1시간 강수량", value=f"**{rain_val}mm**", inline=True)
        
    embed.add_field(name="📊 오늘의 기온", value=f"최저 **{min_t}℃** / 최고 **{max_t}℃**", inline=False)
    embed.add_field(name="🕒 오늘 시간별 예보", value=hourly_result, inline=False)
    embed.set_footer(text="제공: 대한민국 기상청")
    
    return embed

class RegionSelect(discord.ui.Select):
    def __init__(self, candidates):
        # 후보 리스트를 받아서 드롭다운 옵션으로 만듦
        options = []
        for name in candidates:
            options.append(discord.SelectOption(label=name))
            
        super().__init__(placeholder="정확한 지역을 선택해주세요!", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer() # 클릭하자마자 생각 중 띄우기
        
        selected_name = self.values[0] # 사용자가 클릭한 지역명
        
        # 1. 엑셀 데이터에서 선택한 지역의 좌표 다시 찾기
        nx, ny = None, None
        for area in area_data:
            if area['name'] == selected_name:
                nx, ny = area['nx'], area['ny']
                break
                
        # 2. 기상청 통신
        weather_info = get_weather(nx, ny)
        fcst_data, today_date, current_hour = get_forecast(nx, ny)
        
        if not weather_info or not fcst_data:
            await interaction.followup.send("기상청 서버와 통신하는 중 문제가 발생했어. 다시 시도해 봐!")
            return
            
        # 3. 임베드 만들고, 원본 메시지(드롭다운)를 임베드로 교체
        embed = create_weather_embed(selected_name, weather_info, fcst_data, today_date, current_hour)
        await interaction.edit_original_response(content=None, embed=embed, view=None)

class RegionSelectView(discord.ui.View):
    def __init__(self, candidates):
        super().__init__(timeout=60) # 60초 지나면 메뉴 만료되도록 설정
        self.add_item(RegionSelect(candidates))

# 임베드 출력 명령어
@bot.tree.command(name="날씨", description="원하는 지역의 현재 상세 날씨와 시간별 예보를 확인합니다")
@app_commands.describe(지역명="지역명을 입력하세요. 동의 경우 행정동으로 입력하세요.")
async def check_weather(interaction: discord.Interaction, 지역명: str):
    await interaction.response.defer()

    nx, ny, full_name, status = search_coordinates(지역명)
    
    if status == "not_found":
        await interaction.followup.send(f"**'{지역명}'**에 해당하는 지역을 찾을 수 없어! 😭\n오타가 없는지, 행정동으로 입력했는지 확인해봐!")
        return
    
    # 중복일 경우
    elif status != "success":
        view = RegionSelectView(status)
        await interaction.followup.send(f"**'{지역명}'**(으)로 검색된 지역이 여러 개야! 🤔\n아래 메뉴에서 원하는 곳을 정확히 선택해줘!", view=view)
        return
        
    # 단일 지역으로 검색 성공했을 때
    weather_info = get_weather(nx, ny)
    fcst_data, today_date, current_hour = get_forecast(nx, ny)
    
    if not weather_info or not fcst_data:
        await interaction.followup.send("기상청 서버와 통신하는 중 문제가 발생했어. 다시 시도해 봐!")
        return

    # 임베드 공장에서 상자 받아와서 바로 출력
    embed = create_weather_embed(full_name, weather_info, fcst_data, today_date, current_hour)
    await interaction.followup.send(embed=embed)

bot.run(TOKEN)
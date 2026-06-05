import discord
from discord.ext import tasks, commands
from discord import app_commands
import os
from dotenv import load_dotenv
import datetime
import random
import requests
import csv
import re
import io
from PIL import Image, ImageDraw, ImageFont
import aiohttp

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
KMA_API_KEY = os.getenv('KMA_API_KEY')
AIR_API_KEY = os.getenv('AIR_API_KEY')

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

    load_air_stations() # 미세먼지 측정소도 같이 외워둠
    print(f"전국 미세먼지 측정소 {len(air_stations)}개 로딩 완료!")

    try:
        synced = await bot.tree.sync()
        print(f"슬래시 명령어 {len(synced)}개 동기화 완료!")
    except Exception as e:
        print(f"명령어 동기화 실패... {e}")

    check_wordle.start() # 11시
    reset_wordle.start()

    print("나불이 준비 완료!")

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

def extract_wordle_players(content):
    # 1. is, are, was, were playing 뒤에 붙는 말들을 통째로 날려버림
    clean_str = re.sub(r'\s+(is|are|was|were)\s+playing.*', '', content)
    
    # 2. 여러 명일 때 붙는 'and'를 쉼표(',')로 바꿈
    clean_str = clean_str.replace("and", ",")
    
    # 3. 쉼표를 기준으로 조각조각 낸 다음, 양옆 띄어쓰기를 없애고 빈칸이 아닌 것만 모음
    nicknames = [name.strip() for name in clean_str.split(",") if name.strip()]
    return nicknames

@bot.event
async def on_message(message):
    if message.author.bot:
        if message.author.name == "Wordle" and ("was playing" in message.content or "were playing" in message.content):
            nicknames = extract_wordle_players(message.content)
            
            found_users = []
            for nickname in nicknames:
                # 쪼개진 닉네임들을 하나씩 서버 멤버와 대조
                for member in message.guild.members:
                    if member.display_name == nickname or member.name == nickname:
                        if member.id not in done_today: # 중복 방지
                            done_today.add(member.id)
                            found_users.append(member.display_name)
                        break # 찾았으면 다음 사람 찾으러 이동!
            
            # 새롭게 워들을 완료한 사람이 한 명이라도 있다면 알림 띄우기
            if found_users:
                users_str = ", ".join(found_users) # "홍길동, 김철수" 형태로 묶기
                await message.channel.send(f"오! {users_str}이/가 워들을 완료했어!\n(현재 {len(done_today)}명 완료)")
        return

    if "Wordle" in message.content and "🟩" in message.content:
        print(f"👀 {message.author.display_name}님의 워들 수동 결과 감지!")
        if message.author.id not in done_today:
            done_today.add(message.author.id)
            await message.channel.send(f"오! {message.author.display_name}, 수동으로 워들 완료 확인!\n(현재 {len(done_today)}명 완료)")
        else:
            print("❌ 근데 이미 done_today에 등록된 사람이라 무시함!")

    await bot.process_commands(message)

# 메시지가 수정(Edit)되었을 때 발동하는 이벤트
@bot.event
async def on_message_edit(before, after):
    if after.author.bot:
        if after.author.name == "Wordle" and ("was playing" in after.content or "were playing" in after.content):
            nicknames = extract_wordle_players(after.content)
            
            found_users = []
            for nickname in nicknames:
                for member in after.guild.members:
                    if member.display_name == nickname or member.name == nickname:
                        if member.id not in done_today:
                            done_today.add(member.id)
                            found_users.append(member.display_name)
                        break
            
            if found_users:
                users_str = ", ".join(found_users)
                await after.channel.send(f"오! {users_str}이/가 워들을 완료했어!\n(현재 {len(done_today)}명 완료)")

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

            try:
                lon = float(row[13]) # 경도
                lat = float(row[14]) # 위도
            except:
                lon, lat = 0.0, 0.0
            
            if full_name:
                area_data.append({
                    "name": full_name, 
                    "a1": area_1, "a2": area_2, "a3": area_3, 
                    "depth": depth, "nx": nx, "ny": ny,
                    "lon": lon, "lat": lat #  메모리에 위경도도 같이 저장!
                })

def load_air_stations():
    global air_stations
    air_stations = []
    
    # 17개 광역시도의 측정소 리스트를 모두 가져옴
    sidos = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주", "세종"]
    url = "http://apis.data.go.kr/B552584/MsrstnInfoInqireSvc/getMsrstnList"
    
    for sido in sidos:
        params = {
            'serviceKey': AIR_API_KEY,
            'returnType': 'json',
            'numOfRows': '300', # 경기도는 100개가 넘으므로 넉넉하게 300개
            'pageNo': '1',
            'addr': sido,
            'ver': '1.1' # dmX, dmY 가져오기 위해 필수
        }
        try:
            res = requests.get(url, params=params)
            data = res.json()
            items = data.get('response', {}).get('body', {}).get('items', [])
            
            for st in items:
                try:
                    lon = float(st['dmX'])
                    lat = float(st['dmY'])
                    name = st['stationName']
                    air_stations.append({'name': name, 'sido': sido, 'lon': lon, 'lat': lat})
                except:
                    continue
        except Exception as e:
            print(f"{sido} 측정소 로딩 실패: {e}")                

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

def get_lon_lat(target_name):
    for area in area_data:
        if area['name'] == target_name:
            return area['lon'], area['lat']
    return 0.0, 0.0

def get_pm_grade(value, is_pm10=True):
    # 측정소가 점검 중이거나 값이 비어있을 때의 방어 로직
    if value in ['-', '', None] or not str(value).isdigit():
        return f"{value} (정보 없음 ⚪)"
        
    val = int(value)
    
    if is_pm10: # 미세먼지 기준
        if val <= 30: return f"{val} (🔵좋음)"
        elif val <= 80: return f"{val} (🟢보통)"
        elif val <= 150: return f"{val} (🟠나쁨)"
        else: return f"{val} (🔴매우나쁨)"
    else: # 초미세먼지 기준
        if val <= 15: return f"{val} (🔵좋음)"
        elif val <= 35: return f"{val} (🟢보통)"
        elif val <= 75: return f"{val} (🟠나쁨)"
        else: return f"{val} (🔴매우나쁨)"
    
def get_air_quality(my_lon, my_lat):
    if not air_stations: return None
    
    # 1. 전국 600개 측정소 중에서 피타고라스로 가장 가까운 곳 찾기
    min_dist = float('inf')
    best_station = None
    
    for st in air_stations:
        dist = (my_lon - st['lon'])**2 + (my_lat - st['lat'])**2
        if dist < min_dist:
            min_dist = dist
            best_station = st # 가장 가까운 측정소 정보(이름, 속한 시/도) 통째로 저장
            
    if not best_station: return None

    # 2. 찾은 측정소가 속한 시/도(sido)의 실시간 데이터 가져오기
    url_air = "http://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty"
    params_air = {
        'serviceKey': AIR_API_KEY,
        'returnType': 'json',
        'numOfRows': '300', 
        'pageNo': '1',
        'sidoName': best_station['sido'], # 사용자가 입력한 지역이 아니라, 찾은 측정소의 시/도를 넣음
        'ver': '1.0'
    }
    
    try:
        res = requests.get(url_air, params_air)
        data = res.json()
        items = data['response']['body']['items']
        
        for item in items:
            if item['stationName'] == best_station['name']:
                pm10_raw = item.get('pm10Value', '-')
                pm25_raw = item.get('pm25Value', '-')
                
                pm10_str = get_pm_grade(pm10_raw, is_pm10=True)
                pm25_str = get_pm_grade(pm25_raw, is_pm10=False)
                
                return {"pm10": pm10_str, "pm25": pm25_str, "station": best_station['name']}
    except Exception as e:
        print(f"미세먼지 실시간 API 에러: {e}")
    return None
    
def create_weather_embed(full_name, weather_info, fcst_data, today_date, current_hour, air_info):
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

    if air_info and air_info['pm10'] != '-':
        embed.add_field(
            name=f"😷 미세먼지 ({air_info['station']} 측정소)", 
            value=f"미세먼지: **{air_info['pm10']}**\n초미세먼지: **{air_info['pm25']}**", 
            inline=False
        )
        
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

        my_lon, my_lat = get_lon_lat(selected_name)
        air_info = get_air_quality(my_lon, my_lat)
        
        if not weather_info or not fcst_data:
            await interaction.followup.send("기상청 서버와 통신하는 중 문제가 발생했어. 다시 시도해 봐!")
            return
            
        # 3. 임베드 만들고, 원본 메시지(드롭다운)를 임베드로 교체
        embed = create_weather_embed(selected_name, weather_info, fcst_data, today_date, current_hour, air_info)
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
    
    my_lon, my_lat = get_lon_lat(full_name)
    air_info = get_air_quality(my_lon, my_lat)
    
    if not weather_info or not fcst_data:
        await interaction.followup.send("기상청 서버와 통신하는 중 문제가 발생했어. 다시 시도해 봐!")
        return

    # 임베드 공장에서 상자 받아와서 바로 출력
    embed = create_weather_embed(full_name, weather_info, fcst_data, today_date, current_hour, air_info)
    await interaction.followup.send(embed=embed)

# ==========================================
# 윷놀이 명령어
# ==========================================
YUT_SKILLS = ["개와 돼지의 시간", "100 마력", "후진 기어", "디스 이즈 더블더블", "모 아니면 도", "마이더스의 손", "테이크 아웃", "백스텝"]
BOARD_SKILLS = ["강제 귀가", "업고 가실게요", "자리 좀 바꿔주세요", "제 앞에 놔주세요", "백허그", "밥상 뒤집기", "결승점이 코앞이네", "폭발물 주의"]

# 1. 플레이어의 상태를 저장하는 데이터 클래스
class YutPlayer:
    def __init__(self, member: discord.Member, is_p1: bool):
        self.member = member
        self.emoji = "🔴" if is_p1 else "🔵"
        self.horses = [-1, -1, -1, -1]
        self.score = 0
        self.move_list = []
        self.throw_count = 1
        self.used_skill = False
        self.has_thrown = False
        self.is_resolving_skill = False

        #  초능력 시스템용 특수 변수들
        self.yut_skill = ""
        self.board_skill = ""
        self.yut_skill_used = False   
        self.board_skill_used = False 
        self.takeout_storage = []     
        self.active_buff = None

# 2. 게임판 UI (버튼과 드롭다운을 관리하는 View)
class HorseSelect(discord.ui.Select):
    def __init__(self, player):
        options = []
        # 현재 플레이어의 말 4개 중 골인(99)하지 않은 말들을 그룹화해서 보여줌
        unique_positions = set(pos for pos in player.horses if pos != 99)
        
        for pos in unique_positions:
            count = player.horses.count(pos) # 업힌 말 개수 파악
            
            if pos == -1:
                label = f"대기실에 있는 말 ({count}개)"
                desc = "아직 출발하지 않은 말이야."
            else:
                label = f"윷판 {pos}번 칸에 있는 말 ({count}개)"
                desc = "클릭해서 이동 가능한 칸을 확인할 수 있어."
                
            options.append(discord.SelectOption(label=label, description=desc, value=str(pos)))
            
        super().__init__(placeholder="🔽 움직일 말을 선택해줘!", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        view: YutGameView = self.view
        # 선택한 말의 현재 위치를 View에 저장하고 화면을 업데이트(버튼 생성)함
        view.selected_horse_pos = int(self.values[0])
        await view.update_ui(interaction)

class SkillSelectView(discord.ui.View):
    def __init__(self, game_view, player):
        super().__init__(timeout=60)
        self.game_view = game_view
        self.player = player
        
        #  이 메뉴가 열렸을 당시의 턴 번호를 도장 쾅!
        self.opened_turn = game_view.turn_count 

        # 윷 스킬 버튼
        btn_yut = discord.ui.Button(
            label=f"윷 스킬: {player.yut_skill}",
            style=discord.ButtonStyle.primary if not player.yut_skill_used else discord.ButtonStyle.secondary,
            disabled=player.yut_skill_used
        )
        btn_yut.callback = self.use_yut_skill
        self.add_item(btn_yut)

        # 말 스킬 버튼
        btn_board = discord.ui.Button(
            label=f"말 스킬: {player.board_skill}",
            style=discord.ButtonStyle.success if not player.board_skill_used else discord.ButtonStyle.secondary,
            disabled=player.board_skill_used
        )
        btn_board.callback = self.use_board_skill
        self.add_item(btn_board)

    async def use_yut_skill(self, interaction: discord.Interaction):
        if self.opened_turn != self.game_view.turn_count:
            return await interaction.response.send_message("❌ 이 메뉴는 지난 턴에 열린 거야! 윷판 아래의 버튼을 눌러 새로 열어줘.", ephemeral=True)
            
        if self.game_view.current_player.member.id != self.player.member.id:
            return await interaction.response.send_message("❌ 이미 너의 턴이 지났어!", ephemeral=True)
        if self.player.is_resolving_skill:
            return await interaction.response.send_message("❌ 이미 다른 초능력을 진행 중이야!", ephemeral=True)
        if self.player.has_thrown:
            return await interaction.response.send_message("❌ 이미 윷을 던진 후에는 초능력을 사용할 수 없어!", ephemeral=True)
        if self.player.used_skill:
            return await interaction.response.send_message("❌ 이번 턴에는 이미 다른 초능력을 사용했어!", ephemeral=True)

        #  1. 누른 비밀 버튼 메뉴를 "발동 완료" 상태로 변경하여 없앰
        await interaction.response.edit_message(content=f"🔮 **[{self.player.yut_skill}]** 스킬 발동 완료! 윷판을 확인해줘!", view=None)

        #  2. 플레이어 상태 변경 (게임당 1회 스킬 소진 & 이번 턴 스킬 사용 완료)
        self.player.yut_skill_used = True
        self.player.used_skill = True
        
        msg = ""

        # ==========================================
        # 🐶🐷 스킬 1: 개와 돼지의 시간
        # ==========================================
        if self.player.yut_skill == "개와 돼지의 시간":
            self.player.throw_count = 0 # 윷 던지기 기회 박탈!
            self.player.move_list.extend(["도", "개"]) # 리스트에 강제 주입!
            msg = f"🐶🐷 **{self.player.member.display_name}**이/가 **[개와 돼지의 시간]**을 발동했어!\n(이번 턴에는 윷을 던지지 않고 '도'와 '개'를 획득해!)"

        # ==========================================
        # 🐎 스킬 2: 100 마력
        # ==========================================
        elif self.player.yut_skill == "100 마력":
            self.player.active_buff = "100 마력" #  주사위 조작 버프 장전!
            msg = f"🐎 **{self.player.member.display_name}**이/가 **[100 마력]**을 발동했어!\n(이번 윷 던지기에서 무조건 '걸'이 나와!)"

        # ==========================================
        # ⏪ 스킬 3: 후진 기어
        # ==========================================
        elif self.player.yut_skill == "후진 기어":
            self.player.active_buff = "후진 기어" #  주사위 조작 버프 장전!
            msg = f"⏪ **{self.player.member.display_name}**이/가 **[후진 기어]**를 발동했어!\n(이번 윷 던지기에서 무조건 '빽도'가 나와!)"

        # ==========================================
        # ✌️ 스킬 4: 디스 이즈 더블더블
        # ==========================================
        elif self.player.yut_skill == "디스 이즈 더블더블":
            self.player.active_buff = "디스 이즈 더블더블" #  더블더블 버프 장전!
            msg = f"✌️ **{self.player.member.display_name}**이/가 **[디스 이즈 더블더블]**을 발동했어!\n(이번에 던지는 윷의 결과가 2배로 적용돼!)"
        
        # ==========================================
        # 🌗 스킬 5: 모 아니면 도
        # ==========================================
        elif self.player.yut_skill == "모 아니면 도":
            self.player.active_buff = "모 아니면 도" 
            msg = f"🌗 **{self.player.member.display_name}**이/가 **[모 아니면 도]**를 발동했어!\n(이번 윷 던지기에서 50% 확률로 '모', 50% 확률로 '도'가 나와!)"

        # ==========================================
        # ✨ 스킬 6: 마이더스의 손
        # ==========================================
        elif self.player.yut_skill == "마이더스의 손":
            self.player.active_buff = "마이더스의 손"
            msg = f"✨ **{self.player.member.display_name}**이/가 **[마이더스의 손]**을 발동했어!\n(이번 윷 던지기에서 50% 확률로 '윷', 50% 확률로 '모'가 나와!)"

        # ==========================================
        # ☕ 스킬 7: 테이크 아웃
        # ==========================================
        elif self.player.yut_skill == "테이크 아웃":
            self.player.active_buff = "테이크 아웃"
            msg = f"☕ **{self.player.member.display_name}**이/가 **[테이크 아웃]**을 발동했어!\n(이번 턴의 윷 결과를 보관해 두었다가 다음 턴에 같이 사용하게 돼!)"

        # ==========================================
        # ⏪ 스킬 8: 백스텝
        # ==========================================
        elif self.player.yut_skill == "백스텝":
            self.player.active_buff = "백스텝"
            msg = f"⏪ **{self.player.member.display_name}**이/가 **[백스텝]**을 발동했어!\n(윷 결과 중 하나를 선택해서 뒤로 이동할 수 있어!)"

        #  메인 게임판(본체) 업데이트 명령을 내림!
        await self.game_view.update_ui(message_text=msg)

    async def use_board_skill(self, interaction: discord.Interaction):
        #  [유통기한 검사] 여기도 차단!
        if self.opened_turn != self.game_view.turn_count:
            return await interaction.response.send_message("❌ 이 메뉴는 지난 턴에 열린 거야! 윷판 아래의 버튼을 눌러 새로 열어줘.", ephemeral=True)
        if self.game_view.current_player.member.id != self.player.member.id:
            return await interaction.response.send_message("❌ 이미 너의 턴이 지났어!", ephemeral=True)
        if self.player.has_thrown:
            return await interaction.response.send_message("❌ 이미 윷을 던진 후에는 초능력을 사용할 수 없어!", ephemeral=True)
        if self.player.used_skill:
            return await interaction.response.send_message("❌ 이번 턴에는 이미 다른 초능력을 사용했어!", ephemeral=True)

        # 상대방 플레이어 찾기
        enemy = self.game_view.player2 if self.player == self.game_view.player1 else self.game_view.player1

        # ==========================================
        # 🌪️ 스킬 1: 강제 귀가
        # ==========================================
        if self.player.board_skill == "강제 귀가":
            active_enemy_horses = set(h for h in enemy.horses if 0 <= h < 30)
            
            if not active_enemy_horses:
                return await interaction.response.send_message("❌ 윷판 위에 쫓아낼 상대방의 말이 없어!", ephemeral=True)
                
            #  대상을 고르기 전까지 윷판을 조작할 수 없게 자물쇠 찰칵! (물리기 불가)
            self.player.is_resolving_skill = True
                
            options = []
            for pos in active_enemy_horses:
                count = enemy.horses.count(pos)
                options.append(discord.SelectOption(
                    label=f"📍 {pos}번 칸의 말", 
                    description=f"{count}개가 뭉쳐있어.", 
                    value=str(pos)
                ))
                
            select = discord.ui.Select(placeholder="🔽 쫓아낼 상대방의 말을 선택해줘!", options=options)
            
            async def select_callback(inter: discord.Interaction):
                if self.player.used_skill:
                    return await inter.response.send_message("❌ 이미 스킬 처리가 완료됐어!", ephemeral=True)
                
                target_pos = int(select.values[0])
                
                catch_count = 0
                for i in range(4):
                    if enemy.horses[i] == target_pos:
                        enemy.horses[i] = -1
                        catch_count += 1
                        
                #  대상 선택 완료! 자물쇠 해제 및 스킬 소모 처리
                self.player.is_resolving_skill = False
                self.player.board_skill_used = True
                self.player.used_skill = True
                
                msg = f"🌪️ **{self.player.member.display_name}**이/가 **[강제 귀가]**를 발동했어!\n(상대방의 {target_pos}번 칸 말 {catch_count}개가 대기실로 쫓겨났어!)"
                
                #  네가 요청한 깔끔한 완료 메시지로 교체!
                await inter.response.edit_message(content=f"🔮 **[{self.player.board_skill}]** 스킬 발동 완료! 윷판을 확인해줘!", view=None)
                await self.game_view.update_ui(message_text=msg)
                
            select.callback = select_callback
            view = discord.ui.View()
            view.add_item(select)
            
            await interaction.response.edit_message(content="👇 강제 귀가시킬 상대방의 말을 골라줘!", view=view)

        # ==========================================
        # 🎒 스킬 2: 업고 가실게요
        # ==========================================
        elif self.player.board_skill == "업고 가실게요":
            # 1. 윷판 위(0~29)에 있는 내 말 위치 모으기
            active_my_horses = set(h for h in self.player.horses if 0 <= h < 30)
            # 2. 대기실(-1)에 있는 내 말 개수 확인
            waiting_horses = self.player.horses.count(-1)
            
            #  예외 처리: 판 위에 내 말이 없거나, 대기실에 남은 말이 없으면 차단!
            if not active_my_horses:
                return await interaction.response.send_message("❌ 윷판 위에 내 말이 없어서 업을 수 없어!", ephemeral=True)
            if waiting_horses == 0:
                return await interaction.response.send_message("❌ 대기실에 남아있는 말이 없어서 업힐 수 없어!", ephemeral=True)
                
            #  대상을 고르기 전까지 자물쇠 찰칵!
            self.player.is_resolving_skill = True
                
            options = []
            for pos in active_my_horses:
                count = self.player.horses.count(pos)
                options.append(discord.SelectOption(
                    label=f"📍 {pos}번 칸의 내 말", 
                    description=f"현재 {count}개가 뭉쳐있어.", 
                    value=str(pos)
                ))
                
            select = discord.ui.Select(placeholder="🔽 대기실의 말을 업을 내 말을 선택해줘!", options=options)
            
            async def select_callback(inter: discord.Interaction):
                if self.player.used_skill:
                    return await inter.response.send_message("❌ 이미 스킬 처리가 완료됐어!", ephemeral=True)
                
                target_pos = int(select.values[0])
                
                #  대기실(-1)에 있는 말 딱 '하나'를 찾아서 target_pos로 이동!
                for i in range(4):
                    if self.player.horses[i] == -1:
                        self.player.horses[i] = target_pos
                        break # 하나만 업어야 하니까 무조건 break!
                        
                # 자물쇠 해제 및 스킬 소모 처리
                self.player.is_resolving_skill = False
                self.player.board_skill_used = True
                self.player.used_skill = True
                
                msg = f"🎒 **{self.player.member.display_name}**이/가 **[업고 가실게요]**를 발동했어!\n(대기실의 말 1개가 {target_pos}번 칸의 말에 업혔어!)"
                
                # 완료 메시지 띄우고 본체 새로고침!
                await inter.response.edit_message(content=f"🔮 **[{self.player.board_skill}]** 스킬 발동 완료! 윷판을 확인해줘!", view=None)
                await self.game_view.update_ui(message_text=msg)
                
            select.callback = select_callback
            view = discord.ui.View()
            view.add_item(select)
            
            await interaction.response.edit_message(content="👇 업을 내 말을 선택해줘!", view=view)

        # ==========================================
        # 🔄 스킬 3: 자리 좀 바꿔주세요
        # ==========================================
        elif self.player.board_skill == "자리 좀 바꿔주세요":
            # 1. 윷판 위(0~29)에 있는 양쪽 플레이어의 말 위치 모으기
            active_my_horses = set(h for h in self.player.horses if 0 <= h < 30)
            active_enemy_horses = set(h for h in enemy.horses if 0 <= h < 30)
            
            #  예외 처리: 교체할 말이 윷판 위에 하나라도 없으면 스킬 차단!
            if not active_my_horses or not active_enemy_horses:
                return await interaction.response.send_message("❌ 윷판 위에 내 말과 상대방 말이 모두 있어야 해!", ephemeral=True)
                
            #  자물쇠 찰칵!
            self.player.is_resolving_skill = True
            
            # 2. 드롭다운 메뉴 2개 만들기 (내 말 선택용, 상대 말 선택용)
            my_options = [discord.SelectOption(label=f"📍 {pos}번 칸의 내 말", description=f"{self.player.horses.count(pos)}개가 뭉쳐있어.", value=str(pos)) for pos in active_my_horses]
            select_mine = discord.ui.Select(placeholder="1️⃣ 위치를 바꿀 '내 말'을 선택해줘!", options=my_options)
            
            enemy_options = [discord.SelectOption(label=f"📍 {pos}번 칸의 상대 말", description=f"{enemy.horses.count(pos)}개가 뭉쳐있어.", value=str(pos)) for pos in active_enemy_horses]
            select_enemy = discord.ui.Select(placeholder="2️⃣ 위치를 바꿀 '상대방 말'을 선택해줘!", options=enemy_options)
            
            # 3. 최종 확인 버튼 만들기
            btn_confirm = discord.ui.Button(label="🔄 자리 바꾸기!", style=discord.ButtonStyle.primary, row=2)
            
            # 유저가 선택한 값을 임시로 저장해둘 공간 (딕셔너리 활용)
            selections = {"mine": None, "enemy": None}
            
            # 각각의 드롭다운을 눌렀을 때 값을 저장하는 콜백
            async def mine_callback(inter: discord.Interaction):
                selections["mine"] = int(select_mine.values[0])
                await inter.response.defer() # 조용히 값만 저장하고 넘김
                
            async def enemy_callback(inter: discord.Interaction):
                selections["enemy"] = int(select_enemy.values[0])
                await inter.response.defer()
                
            # 최종 확인 버튼을 눌렀을 때 작동하는 진짜 스킬 콜백!
            async def confirm_callback(inter: discord.Interaction):
                #  [중복 실행 방어턱] 다중창 꼼수 차단
                if self.player.used_skill:
                    return await inter.response.send_message("❌ 이미 스킬 처리가 완료됐어!", ephemeral=True)
                
                #  둘 중 하나라도 선택 안 하고 버튼부터 누르면 경고!
                if selections["mine"] is None or selections["enemy"] is None:
                    return await inter.response.send_message("❌ 내 말과 상대방 말을 모두 선택한 후 실행 버튼을 눌러야 해!", ephemeral=True)
                    
                my_pos = selections["mine"]
                enemy_pos = selections["enemy"]
                
                #  덩어리째 교체하는 핵심 로직!
                # 각 위치에 해당하는 말들의 인덱스를 싹 긁어옴
                my_indices = [i for i, pos in enumerate(self.player.horses) if pos == my_pos]
                enemy_indices = [i for i, pos in enumerate(enemy.horses) if pos == enemy_pos]
                
                # 위치 스왑 적용! (업혀 있는 말들도 한 번에 싹 다 바뀜)
                for i in my_indices:
                    self.player.horses[i] = enemy_pos
                for i in enemy_indices:
                    enemy.horses[i] = my_pos
                    
                # 락 해제 및 스킬 소모
                self.player.is_resolving_skill = False
                self.player.board_skill_used = True
                self.player.used_skill = True
                
                my_count = len(my_indices)
                enemy_count = len(enemy_indices)
                msg = f"🔄 **{self.player.member.display_name}**이/가 **[자리 좀 바꿔주세요]**를 발동했어!\n(내 말 {my_count}개와 상대방 말 {enemy_count}개가 서로 위치를 바꿨어!)"
                
                await inter.response.edit_message(content=f"🔮 **[{self.player.board_skill}]** 스킬 발동 완료! 윷판을 확인해줘!", view=None)
                await self.game_view.update_ui(message_text=msg)
                
            # 부품들 조립!
            select_mine.callback = mine_callback
            select_enemy.callback = enemy_callback
            btn_confirm.callback = confirm_callback
            
            view = discord.ui.View()
            view.add_item(select_mine)
            view.add_item(select_enemy)
            view.add_item(btn_confirm) # 확인 버튼 장착!
            
            await interaction.response.edit_message(content="👇 위치를 교체할 내 말과 상대방 말을 모두 선택한 후 실행 버튼을 눌러줘!", view=view)   

        # ==========================================
        # 🧲 스킬 4: 제 앞에 놔주세요
        # ==========================================
        elif self.player.board_skill == "제 앞에 놔주세요":
            active_my_horses = set(h for h in self.player.horses if 0 <= h < 30)
            active_enemy_horses = set(h for h in enemy.horses if 0 <= h < 30)
            
            #  예외 처리 1: 윷판 위에 양쪽 말이 모두 있어야 함!
            if not active_my_horses or not active_enemy_horses:
                return await interaction.response.send_message("❌ 윷판 위에 내 말과 상대방 말이 모두 있어야 해!", ephemeral=True)
                
            #  내 말들 기준으로 앞 1~3칸의 유효한 목적지(칸 번호) 모두 계산하기!
            valid_destinations = set()
            for pos in active_my_horses:
                for step in [1, 2, 3]: # 1칸, 2칸, 3칸 앞 탐색
                    dests = calculate_arrival(pos, step)
                    for d in dests:
                        if 0 <= d < 30 and d not in active_my_horses:
                            valid_destinations.add(d)
                            
            #  예외 처리 2: 내 말이 결승점 코앞이라 1~3칸 앞이 모두 골인(99)인 경우 차단!
            if not valid_destinations:
                return await interaction.response.send_message("❌ 소환할 수 있는 유효한 위치가 없어! (내 말이 결승점에 너무 가까워.)", ephemeral=True)

            #  자물쇠 찰칵!
            self.player.is_resolving_skill = True
            
            # 1. 적 말 선택용 드롭다운
            enemy_options = [discord.SelectOption(label=f"📍 {pos}번 칸의 상대 말", description=f"{enemy.horses.count(pos)}개가 뭉쳐있어.", value=str(pos)) for pos in active_enemy_horses]
            select_enemy = discord.ui.Select(placeholder="1️⃣ 끌고 올 '상대방 말'을 선택해줘!", options=enemy_options)
            
            # 2. 목적지 선택용 드롭다운 (오름차순으로 깔끔하게 정렬!)
            dest_options = [discord.SelectOption(label=f"🎯 {dest}번 칸으로 소환", value=str(dest)) for dest in sorted(list(valid_destinations))]
            select_dest = discord.ui.Select(placeholder="2️⃣ 소환할 '목적지'를 선택해줘!", options=dest_options)
            
            # 3. 최종 확인 버튼
            btn_confirm = discord.ui.Button(label="🧲 소환!", style=discord.ButtonStyle.primary, row=2)
            
            selections = {"enemy": None, "dest": None}
            
            async def enemy_callback(inter: discord.Interaction):
                selections["enemy"] = int(select_enemy.values[0])
                await inter.response.defer()
                
            async def dest_callback(inter: discord.Interaction):
                selections["dest"] = int(select_dest.values[0])
                await inter.response.defer()
                
            # 실행 버튼 콜백
            async def confirm_callback(inter: discord.Interaction):
                #  [중복 실행 방어턱] 꼼수 완벽 차단!
                if self.player.used_skill:
                    return await inter.response.send_message("❌ 이미 스킬 처리가 완료됐어!", ephemeral=True)
                
                if selections["enemy"] is None or selections["dest"] is None:
                    return await inter.response.send_message("❌ 상대방 말과 목적지를 모두 선택한 후 실행 버튼을 눌러줘!", ephemeral=True)
                    
                enemy_pos = selections["enemy"]
                target_dest = selections["dest"]
                
                #  타겟 위치에 있는 상대방 말을 덩어리째 목적지로 텔레포트!
                enemy_indices = [i for i, pos in enumerate(enemy.horses) if pos == enemy_pos]
                for i in enemy_indices:
                    enemy.horses[i] = target_dest
                    
                # 락 해제 및 스킬 소모
                self.player.is_resolving_skill = False
                self.player.board_skill_used = True
                self.player.used_skill = True
                
                enemy_count = len(enemy_indices)
                msg = f"🧲 **{self.player.member.display_name}**이/가 **[제 앞에 놔주세요]**를 발동했어!\n(상대방 말 {enemy_count}개를 내 말 앞의 {target_dest}번 칸으로 강제 소환했어!)"
                
                await inter.response.edit_message(content=f"🔮 **[{self.player.board_skill}]** 스킬 발동 완료! 윷판을 확인해줘!", view=None)
                await self.game_view.update_ui(message_text=msg)
                
            select_enemy.callback = enemy_callback
            select_dest.callback = dest_callback
            btn_confirm.callback = confirm_callback
            
            view = discord.ui.View()
            view.add_item(select_enemy)
            view.add_item(select_dest)
            view.add_item(btn_confirm)
            
            await interaction.response.edit_message(content="👇 끌고 올 상대방 말과 소환할 위치를 선택한 후 실행 버튼을 눌러줘!", view=view)
        
        # ==========================================
        # 🫂 스킬 5: 백허그
        # ==========================================
        elif self.player.board_skill == "백허그":
            active_my_horses = set(h for h in self.player.horses if 0 <= h < 30)
            active_enemy_horses = set(h for h in enemy.horses if 0 <= h < 30)
            
            if not active_my_horses or not active_enemy_horses:
                return await interaction.response.send_message("❌ 윷판 위에 내 말과 상대방 말이 모두 있어야 해!", ephemeral=True)
                
            #  자물쇠 찰칵!
            self.player.is_resolving_skill = True
            
            # 1. 적 말 선택용 드롭다운 (기준점)
            enemy_options = [discord.SelectOption(label=f"📍 {pos}번 칸의 상대 말", description=f"이 말의 1칸 뒤로 이동하기!", value=str(pos)) for pos in active_enemy_horses]
            select_enemy = discord.ui.Select(placeholder="1️⃣ 타겟할 '상대방 말'을 선택해줘!", options=enemy_options)
            
            # 2. 내 말 선택용 드롭다운 (이동할 녀석)
            my_options = [discord.SelectOption(label=f"📍 {pos}번 칸의 내 말", description=f"{self.player.horses.count(pos)}개가 뭉쳐있어.", value=str(pos)) for pos in active_my_horses]
            select_mine = discord.ui.Select(placeholder="2️⃣ 이동할 '내 말'을 선택해줘!", options=my_options)
            
            # 3. 최종 확인 버튼
            btn_confirm = discord.ui.Button(label="🫂 백허그 하기!", style=discord.ButtonStyle.primary, row=2)
            
            selections = {"enemy": None, "mine": None}
            
            async def enemy_callback(inter: discord.Interaction):
                selections["enemy"] = int(select_enemy.values[0])
                await inter.response.defer()
                
            async def mine_callback(inter: discord.Interaction):
                selections["mine"] = int(select_mine.values[0])
                await inter.response.defer()
                
            async def confirm_callback(inter: discord.Interaction):
                if self.player.used_skill:
                    return await inter.response.send_message("❌ 이미 스킬 처리가 완료됐어!", ephemeral=True)
                
                if selections["enemy"] is None or selections["mine"] is None:
                    return await inter.response.send_message("❌ 타겟할 적의 말과 이동할 내 말을 모두 선택해줘!", ephemeral=True)
                    
                enemy_pos = selections["enemy"]
                my_pos = selections["mine"]
                
                #  [핵심] 적의 1칸 뒤 위치(목적지) 계산!
                target_dest = calculate_arrival(enemy_pos, -1)[0]
                
                # 💥 목적지에 적의 '다른 말'이 있다면 잡아버리기! (연쇄 암살)
                enemy_catch_indices = [i for i, pos in enumerate(enemy.horses) if pos == target_dest]
                catch_count = len(enemy_catch_indices)
                for i in enemy_catch_indices:
                    enemy.horses[i] = -1
                    
                # 🎒 내 말을 덩어리째 목적지로 텔레포트!
                my_indices = [i for i, pos in enumerate(self.player.horses) if pos == my_pos]
                for i in my_indices:
                    self.player.horses[i] = target_dest
                    
                # 락 해제 및 스킬 소모
                self.player.is_resolving_skill = False
                self.player.board_skill_used = True
                self.player.used_skill = True
                
                my_count = len(my_indices)
                msg = f"🫂 **{self.player.member.display_name}**이/가 **[백허그]**를 발동했어!\n(내 말 {my_count}개가 상대방 말({enemy_pos}번)의 1칸 뒤인 {target_dest}번 칸으로 이동했어!)"
                
                #  잡기 또는 업기 발생 시 추가 메시지 출력!
                if catch_count > 0:
                    msg += f"\n💥 그 자리에 있던 적 말 {catch_count}개를 잡고 대기실로 쫓아냈어!"
                else:
                    # 목적지에 내 말이 이미 있었다면 자연스럽게 업힘
                    my_existing_count = self.player.horses.count(target_dest) - my_count
                    if my_existing_count > 0:
                        msg += f"\n🎒 목적지에 있던 내 말 {my_existing_count}개와 업혔어!"
                
                await inter.response.edit_message(content=f"🔮 **[{self.player.board_skill}]** 스킬 발동 완료! 윷판을 확인해줘!", view=None)
                await self.game_view.update_ui(message_text=msg)
                
            select_enemy.callback = enemy_callback
            select_mine.callback = mine_callback
            btn_confirm.callback = confirm_callback
            
            view = discord.ui.View()
            view.add_item(select_enemy)
            view.add_item(select_mine)
            view.add_item(btn_confirm)
            
            await interaction.response.edit_message(content="👇 타겟할 적의 말과 이동시킬 내 말을 선택한 후 실행 버튼을 눌러줘!", view=view)

        # ==========================================
        # 🍲 스킬 6: 밥상 뒤집기
        # ==========================================
        elif self.player.board_skill == "밥상 뒤집기":
            import random
            
            # 1. 윷판 위(0~29)에 있는 모든 '말의 위치(덩어리)' 수집
            # set()을 사용하면 같은 칸에 있는 말들은 1개의 위치로 합쳐짐(덩어리 단위 인식)
            active_positions = set()
            for h in self.player.horses:
                if 0 <= h < 30: active_positions.add(h)
            for h in enemy.horses:
                if 0 <= h < 30: active_positions.add(h)
                
            #  예외 처리: 판 위에 말이 하나도 없으면 엎을 밥상이 없음!
            if not active_positions:
                return await interaction.response.send_message("❌ 윷판 위에 말이 없으면 사용할 수 없어!", ephemeral=True)
                
            # 2. 겹치지 않는 새로운 무작위 위치 뽑기! (0번 칸 포함, 0~29번)
            # random.sample은 절대로 중복된 값을 뽑지 않으므로, 겹치는 상황 원천 차단!
            chunk_count = len(active_positions)
            new_positions = random.sample(range(30), chunk_count)
            
            # 3. 기존 위치 -> 새로운 위치 연결 지어주기 (매핑)
            mapping = {old: new for old, new in zip(active_positions, new_positions)}
            
            # 4. 양쪽 플레이어의 말 위치 일괄 변경! (업혀있던 애들도 mapping을 따라 같이 이동)
            for i in range(4):
                if self.player.horses[i] in mapping:
                    self.player.horses[i] = mapping[self.player.horses[i]]
                if enemy.horses[i] in mapping:
                    enemy.horses[i] = mapping[enemy.horses[i]]
                    
            # 5. 스킬 소모 처리 (이 스킬은 드롭다운이 필요 없으므로 즉시 발동!)
            self.player.board_skill_used = True
            self.player.used_skill = True
            
            msg = f"🍲 **{self.player.member.display_name}**이/가 **[밥상 뒤집기]**를 발동했어!\n(윷판 위의 모든 말이 무작위 위치로 강제 재배치됐어!)"
            
            # 비밀 메뉴를 완료 메시지로 교체하고 윷판 본체 새로고침!
            await interaction.response.edit_message(content=f"🔮 **[{self.player.board_skill}]** 스킬 발동 완료! 윷판을 확인해줘!", view=None)
            await self.game_view.update_ui(message_text=msg)

        # ==========================================
        # 🌀💣 스킬 7 & 8: 결승점이 코앞이네 / 폭발물 주의
        # ==========================================
        elif self.player.board_skill in ["결승점이 코앞이네", "폭발물 주의"]:
            trap_type = "포탈" if self.player.board_skill == "결승점이 코앞이네" else "폭탄"
            trap_emoji = "🌀" if trap_type == "포탈" else "💣"
            
            active_positions = set(h for h in self.player.horses + enemy.horses if 0 <= h < 30)
            empty_positions = [pos for pos in range(30) if pos not in active_positions]
            
            if not empty_positions:
                return await interaction.response.send_message("❌ 윷판에 빈 칸이 없어서 설치할 수 없어!", ephemeral=True)
                
            self.player.is_resolving_skill = True
            
            #  모든 옵션을 미리 만들어둠
            options_all = [discord.SelectOption(label=f"📍 {pos}번 칸에 설치", value=str(pos)) for pos in empty_positions]
            
            # 페이지 상태 저장용
            state = {"page": 0}
            selections = {"target": None}
            
            #  현재 페이지에 맞는 25개의 항목을 잘라서 가져오는 함수
            def get_options_for_page(page):
                start = page * 24
                end = start + 24
                current_options = options_all[start:end]
                
                # 다음 페이지가 필요하면 맨 뒤에 '다음' 추가
                if end < len(options_all):
                    current_options.append(discord.SelectOption(label="▶️ 다음 페이지 보기", value="next", description="더 많은 칸을 보려면 클릭해줘."))
                # 이전 페이지가 필요하면 맨 앞에 '이전' 추가
                if page > 0:
                    current_options.insert(0, discord.SelectOption(label="◀️ 이전 페이지 보기", value="prev", description="이전 칸을 보려면 클릭해줘."))
                    
                return current_options

            # 기본 1페이지 드롭다운 생성
            select_trap = discord.ui.Select(placeholder=f"🎯 {trap_type}을 설치할 칸을 선택해줘!", options=get_options_for_page(0))
            btn_confirm = discord.ui.Button(label=f"{trap_emoji} {trap_type} 설치!", style=discord.ButtonStyle.danger if trap_type=="폭탄" else discord.ButtonStyle.primary, row=2)
            
            view = discord.ui.View()
            view.add_item(select_trap)
            view.add_item(btn_confirm)

            #  드롭다운 내부에서 페이징을 처리하는 마법의 콜백!
            async def trap_callback(inter: discord.Interaction):
                val = select_trap.values[0]
                if val == "next":
                    state["page"] += 1
                    select_trap.options = get_options_for_page(state["page"])
                    await inter.response.edit_message(view=view)
                elif val == "prev":
                    state["page"] -= 1
                    select_trap.options = get_options_for_page(state["page"])
                    await inter.response.edit_message(view=view)
                else:
                    selections["target"] = int(val)
                    await inter.response.defer()
                    
            async def confirm_callback(inter: discord.Interaction):
                if self.player.used_skill:
                    return await inter.response.send_message("❌ 이미 스킬 처리가 완료됐어!", ephemeral=True)
                
                if selections["target"] is None:
                    return await inter.response.send_message(f"❌ {trap_type}을 설치할 칸을 선택해줘!", ephemeral=True)
                    
                target = selections["target"]
                self.game_view.traps[target] = trap_type
                
                self.player.is_resolving_skill = False
                self.player.board_skill_used = True
                self.player.used_skill = True
                
                msg = f"{trap_emoji} **{self.player.member.display_name}**이/가 **[{self.player.board_skill}]**을/를 발동했어!\n(윷판의 {target}번 칸에 {trap_type}이 설치됐어!)"
                
                await inter.response.edit_message(content=f"🔮 **[{self.player.board_skill}]** 스킬 발동 완료! 윷판을 확인해줘!", view=None)
                await self.game_view.update_ui(message_text=msg)
                
            select_trap.callback = trap_callback
            btn_confirm.callback = confirm_callback
            
            await interaction.response.edit_message(content=f"👇 {trap_type}을 설치할 위치를 선택한 후 실행 버튼을 눌러줘!", view=view)

class YutGameView(discord.ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member, is_superpower: bool = False):
        super().__init__(timeout=None)
        self.is_superpower = is_superpower
        self.player1 = YutPlayer(p1, True)
        self.player2 = YutPlayer(p2, False)

        if is_superpower:
            import random
            y_skills = random.sample(YUT_SKILLS, 2)
            b_skills = random.sample(BOARD_SKILLS, 2)
            self.player1.yut_skill = y_skills[0]
            self.player1.board_skill = b_skills[0]
            self.player2.yut_skill = y_skills[1]
            self.player2.board_skill = b_skills[1]

        self.current_player = self.player1
        self.selected_horse_pos = None
        self.traps = {} #  바닥에 설치된 함정들 기록 {칸번호: '포탈' 또는 '폭탄'}
        self.turn_count = 1

        self.board_message = None

        self.setup_buttons()

    def generate_board_image(self):
        img = Image.new('RGBA', (500, 500), color=(40, 44, 52, 255))
        draw = ImageDraw.Draw(img, 'RGBA')

        coords = {
            0: (450, 450), 1: (450, 370), 2: (450, 290), 3: (450, 210), 4: (450, 130),
            5: (450, 50), 6: (370, 50), 7: (290, 50), 8: (210, 50), 9: (130, 50),
            10: (50, 50), 11: (50, 130), 12: (50, 210), 13: (50, 290), 14: (50, 370),
            15: (50, 450), 16: (130, 450), 17: (210, 450), 18: (290, 450), 19: (370, 450),
            21: (383, 117), 22: (317, 183), 23: (250, 250), 24: (183, 317), 25: (117, 383),
            26: (117, 117), 27: (183, 183), 28: (317, 317), 29: (383, 383)
        }

        line_color = (130, 140, 160)
        draw.line([(450,450), (450,50), (50,50), (50,450), (450,450)], fill=line_color, width=8)
        draw.line([(450,50), (50,450)], fill=line_color, width=8)
        draw.line([(50,50), (450,450)], fill=line_color, width=8)

        def draw_arrow(cx, cy, direction):
            ac = (160, 110, 0)
            w = 6
            if direction == 'dl': # ↙️
                draw.line([(cx+7, cy-7), (cx-3, cy+3)], fill=ac, width=w)
                draw.polygon([(cx-7, cy+7), (cx-7, cy-3), (cx+3, cy+7)], fill=ac)
            elif direction == 'dr': # ↘️
                draw.line([(cx-7, cy-7), (cx+3, cy+3)], fill=ac, width=w)
                draw.polygon([(cx+7, cy+7), (cx+7, cy-3), (cx-3, cy+7)], fill=ac)
            elif direction == 'r': # ➡️
                draw.line([(cx-9, cy), (cx+4, cy)], fill=ac, width=w)
                draw.polygon([(cx+9, cy), (cx+1, cy-7), (cx+1, cy+7)], fill=ac)

        #  윈도우 & 리눅스 호환 폰트 로드 시스템
        font_options = [
            "arial.ttf", "malgun.ttf", 
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "DejaVuSans.ttf"
        ]
        
        # 말 위의 숫자 뱃지용 폰트 (크기 24)
        badge_font = None
        for font_name in font_options:
            try: badge_font = ImageFont.truetype(font_name, 24); break
            except IOError: continue
        if badge_font is None: badge_font = ImageFont.load_default()

        #  [새로 추가] 칸 안에 새겨넣을 노드 번호용 폰트 (크기 16으로 큼직하고 짱짱하게!)
        node_font = None
        for font_name in font_options:
            try: node_font = ImageFont.truetype(font_name, 20); break
            except IOError: continue
        if node_font is None: node_font = ImageFont.load_default()

        # 5. 각 좌표에 동그라미 그리고 그 위에 숫자 얹기
        for i in range(30):
            if i not in coords: continue
            cx, cy = coords[i]
            r = 23 
            
            fill_color = (235, 240, 245)
            out_color = (160, 170, 190)
            
            if i in [5, 10, 15]: 
                fill_color = (255, 225, 60)
                out_color = (220, 160, 0)
            elif i == 23:
                fill_color = (255, 150, 50)
                out_color = (210, 100, 0)
            elif i == 0:
                fill_color = (80, 230, 120)
                out_color = (40, 170, 80)
                
            draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=fill_color, outline=out_color, width=4)
            draw.ellipse([cx-r+5, cy-r+5, cx+r-5, cy+r-5], outline=(255,255,255, 180), width=2)
            
            # 화살표 먼저 밑바탕에 그리기
            if i == 5: draw_arrow(cx, cy, 'dl')
            elif i == 10: draw_arrow(cx, cy, 'dr')
            elif i == 15: draw_arrow(cx, cy, 'r')
            elif i == 23: draw_arrow(cx, cy, 'dr')

            #  [핵심] 화살표 위에 숫자를 덮어씌워 정중앙 정렬로 그리기!
            text_str = str(i)
            try:
                # 텍스트의 실제 픽셀 크기를 구해서 오차 없는 정중앙 좌표 계산
                bbox = node_font.getbbox(text_str)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                tx = cx - tw / 2 - bbox[0]
                ty = cy - th / 2 - bbox[1]
            except:
                tx, cy = cx - 5, cy - 7 # 예외 대비책
                
            # 가독성을 위해 노란색/주황색 특수 칸은 글씨를 완전 검은색(10,10,10)으로, 일반 칸은 짙은 남회색으로 지정
            text_color = (10, 10, 10) if i in [5, 10, 15, 23, 0] else (50, 60, 75)
            draw.text((tx, ty), text_str, fill=text_color, font=node_font)

        for trap_pos, trap_type in self.traps.items():
            if trap_pos in coords:
                cx, cy = coords[trap_pos]
                trap_r = 20 # 칸에 딱 맞는 크기
                
                if trap_type == "포탈":
                    # 파란색 테두리와 아우라 (포탈 느낌)
                    draw.ellipse([cx-trap_r, cy-trap_r, cx+trap_r, cy+trap_r], fill=(50, 200, 255, 180), outline=(0, 100, 255, 255), width=3)
                    draw.ellipse([cx-trap_r+6, cy-trap_r+6, cx+trap_r-6, cy+trap_r-6], outline=(255, 255, 255, 200), width=2)
                elif trap_type == "폭탄":
                    # 검은 구체와 빨간 경고 (폭탄 느낌)
                    draw.ellipse([cx-trap_r, cy-trap_r, cx+trap_r, cy+trap_r], fill=(40, 40, 40, 220), outline=(255, 50, 50, 255), width=3)
                    draw.ellipse([cx-4, cy-trap_r-4, cx+4, cy-trap_r+4], fill=(255, 100, 50, 255)) # 폭탄 불꽃

        # 6. 플레이어 말 그리기 헬퍼 함수
        def draw_horse(pos, color_rgb, count):
            if 0 <= pos < 30:
                cx, cy = coords[pos]
                hr = 15 
                draw.ellipse([cx-hr+2, cy-hr+2, cx+hr+2, cy+hr+2], fill=(0,0,0, 80))
                draw.ellipse([cx-hr, cy-hr, cx+hr, cy+hr], fill=color_rgb, outline=(255,255,255,255), width=3)
                draw.ellipse([cx-5, cy-5, cx+5, cy+5], fill=(255,255,255,220))
                
                if count > 1:
                    bx, by = cx + 13, cy + 13 
                    badge_r = 13 
                    draw.ellipse([bx-badge_r, by-badge_r, bx+badge_r, by+badge_r], fill=(30, 30, 30, 255), outline=(255, 255, 255, 255), width=2)
                    draw.text((bx-7, by-13), str(count), fill=(255, 255, 255, 255), font=badge_font)

        # 말 렌더링
        p2_board = [h for h in self.player2.horses if 0 <= h < 30]
        p2_counts = {pos: p2_board.count(pos) for pos in set(p2_board)}
        for pos, count in p2_counts.items(): draw_horse(pos, (85, 170, 255, 255), count)

        p1_board = [h for h in self.player1.horses if 0 <= h < 30]
        p1_counts = {pos: p1_board.count(pos) for pos in set(p1_board)}
        for pos, count in p1_counts.items(): draw_horse(pos, (255, 85, 85, 255), count)

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return discord.File(buffer, filename="yut_board.png")
    
    def setup_buttons(self):
        self.clear_items()
        
        # 1. 윷 던지기 기회가 있을 때
        if self.current_player.throw_count > 0:
            btn_throw = discord.ui.Button(label="윷 던지기", style=discord.ButtonStyle.primary, emoji="🎲")
            btn_throw.callback = self.btn_throw_callback
            self.add_item(btn_throw)
            
        # 2. 던지기 기회는 없고, 쓸 수 있는 윷 결과가 있을 때
        elif self.current_player.move_list:
            self.add_item(HorseSelect(self.current_player))
            
            # 3. 드롭다운에서 말을 선택했다면?
            if self.selected_horse_pos is not None:
                unique_moves = set(self.current_player.move_list)
                valid_move_exists = False 
                
                for yut_str in unique_moves:
                    move_val = yut_to_number(yut_str)
                    
                    #  [핵심] 백스텝 버프가 켜져 있다면 이동 칸 수를 음수로 뒤집기!
                    is_backstep = (self.current_player.active_buff == "백스텝")
                    if is_backstep:
                        move_val = -move_val
                    
                    destinations = calculate_arrival(self.selected_horse_pos, move_val)
                    
                    for dest in destinations:
                        valid_move_exists = True
                        dest_label = "🏁 골인하기" if dest == 99 else f"📍 {dest}번 칸으로 이동"
                        
                        # 버튼에 텍스트 표시도 백스텝이면 '-'를 달아서 보여줌
                        display_yut = f"-{yut_str}" if is_backstep else yut_str
                        
                        btn_move = discord.ui.Button(label=f"{dest_label} ({display_yut})", style=discord.ButtonStyle.success)
                        # callback에는 변환되지 않은 원래 윷 이름(yut_str)을 넘겨줌!
                        btn_move.callback = lambda i, d=dest, y=yut_str: self.btn_move_callback(i, d, y)
                        self.add_item(btn_move)
                        
                if not valid_move_exists:
                    btn_error = discord.ui.Button(label="❌ 이 말은 현재 윷으로 이동 불가", style=discord.ButtonStyle.secondary, disabled=True)
                    self.add_item(btn_error)

        #  초능력 모드이고, 아직 스킬을 안 썼다면 '초능력 사용' 버튼 등장!
        if self.is_superpower and not self.current_player.used_skill and not self.current_player.has_thrown:
            btn_skill = discord.ui.Button(label="초능력 사용", style=discord.ButtonStyle.success, emoji="✨", row=3)
            btn_skill.callback = self.btn_skill_callback
            self.add_item(btn_skill)
                        
        #  빽도만 나와서 어쩔 수 없이 턴을 버려야 할 때를 위한 스킵 버튼
        # btn_skip = discord.ui.Button(label="턴 넘기기", style=discord.ButtonStyle.danger, row=4)
        # btn_skip.callback = self.btn_skip_callback
        # self.add_item(btn_skip)

    #  초능력 버튼 콜백 함수 (구버전 @discord.ui.button을 대체함!)
    async def btn_skill_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.current_player.member.id:
            return await interaction.response.send_message("❌ 지금은 네 턴이 아니야!", ephemeral=True)
            
        #  [스마트 복구 시스템] 이미 자물쇠가 잠겨있다 = 드롭다운 창을 날려먹었다!
        if self.current_player.is_resolving_skill:
            self.board_message = interaction.message 
            skill_view = SkillSelectView(self, self.current_player)
            # 에러 대신 복구 메시지와 함께 메뉴를 다시 띄워줌!
            return await interaction.response.send_message("⚠️ 대상을 선택하던 창을 닫았구나? 아래 버튼을 눌러 다시 진행해줘!", view=skill_view, ephemeral=True)
            
        self.board_message = interaction.message 
        skill_view = SkillSelectView(self, self.current_player)
        await interaction.response.send_message("👇 사용할 초능력을 선택해줘!", view=skill_view, ephemeral=True)

    #  화면 새로고침 헬퍼 함수 (비밀 메뉴에서도 호출할 수 있게 개조!)
    async def update_ui(self, interaction: discord.Interaction = None, message_text=None):
        if self.player1.score >= 4 or self.player2.score >= 4:
            winner = self.player1 if self.player1.score >= 4 else self.player2
            self.clear_items()
            image_file = self.generate_board_image()
            embed = self.create_board_embed()
            embed.color = 0x00FF00
            embed.add_field(name="🏆 게임 종료 🏆", value=f"🎉 **{winner.member.display_name}**이/가 4점을 달성해서 최종 승리했어!", inline=False)
            
            #  interaction이 있으면 그걸로, 없으면 기억해둔 본체 메시지로 업데이트!
            if interaction:
                await interaction.response.edit_message(content=f"🎊 {winner.member.mention}의 승리!!", attachments=[image_file], embed=embed, view=None)
            elif self.board_message:
                await self.board_message.edit(content=f"🎊 {winner.member.mention}의 승리!!", attachments=[image_file], embed=embed, view=None)
            self.stop()
            return

        self.setup_buttons()
        image_file = self.generate_board_image()
        embed = self.create_board_embed()
        
        content = message_text if message_text else f"💭 **{self.current_player.member.display_name}**이/가 말을 움직이는 중이야..."
        
        #  여기도 마찬가지!
        if interaction:
            await interaction.response.edit_message(content=content, attachments=[image_file], embed=embed, view=self)
        elif self.board_message:
            await self.board_message.edit(content=content, attachments=[image_file], embed=embed, view=self)

    # ⭐️ [신규] 플레이어가 이동 가능한 말이 단 하나라도 있는지 판독하는 센서
    def check_has_valid_move(self, player):
        # 1. 윷 던질 기회가 남아있으면 아직 턴 종료 아님!
        if player.throw_count > 0: return True
        # 2. 이동할 윷이 아예 없으면 턴 종료 맞음!
        if not player.move_list: return False
        
        unique_horses = set(player.horses)
        unique_moves = set(player.move_list)
        
        # 3. 모든 말과 모든 윷의 경우의 수를 조합해 봄
        for pos in unique_horses:
            if pos == 99: continue # 골인한 말은 제외
            for yut_str in unique_moves:
                move_val = yut_to_number(yut_str)
                if player.active_buff == "백스텝":
                    move_val = -move_val
                
                # 단 하나라도 도착 가능한 목적지가 존재한다면 True 반환!
                if calculate_arrival(pos, move_val):
                    return True
                    
        # 4. 모든 경우의 수를 다 돌렸는데 갈 수 있는 곳이 없으면 False
        return False

    # [콜백] 윷 던지기 버튼 눌렀을 때
    async def btn_throw_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.current_player.member.id:
            return await interaction.response.send_message("❌ 지금은 네 턴이 아니야!", ephemeral=True)
        
        if self.current_player.is_resolving_skill:
            return await interaction.response.send_message("❌ 초능력을 사용 중일 때는 윷을 던질 수 없어!", ephemeral=True)
        
        self.current_player.has_thrown = True 
        
        import random
        
        #  밑장빼기(버프) 확인 구간!
        if self.current_player.active_buff == "100 마력":
            result = "걸"
            self.current_player.active_buff = None # 버프는 1회용이므로 사용 후 즉시 소멸!
        elif self.current_player.active_buff == "후진 기어":
            result = "빽도"
            self.current_player.active_buff = None # 버프 소모!
        elif self.current_player.active_buff == "모 아니면 도":
            #  도 50%, 모 50%
            result = random.choice(["도", "모"])
            self.current_player.active_buff = None 
        elif self.current_player.active_buff == "마이더스의 손":
            #  윷 50%, 모 50%
            result = random.choice(["윷", "모"])
            self.current_player.active_buff = None
        else:
            # 버프가 없다면 평소처럼 정직한 윷놀이 확률 적용
            yut_results = ["낙", "도", "개", "걸", "윷", "모", "빽도"]
            yut_weights = [1.5, 11.35, 34.04, 34.04, 12.77, 2.52, 3.78]
            result = random.choices(yut_results, weights=yut_weights, k=1)[0]
        
        self.current_player.throw_count -= 1
        
        # 낙 처리 로직
        if result == "낙":
            msg = "😱 앗! 윷이 판 밖으로 나갔어! (**낙**)"
            if self.current_player.active_buff in ["디스 이즈 더블더블", "백스텝"]:
                self.current_player.active_buff = None # 낙 나오면 버프 증발!
        else:
            if self.current_player.active_buff == "디스 이즈 더블더블":
                self.current_player.move_list.extend([result, result]) 
                self.current_player.active_buff = None 
                msg = f"✌️ 디스 이즈 더블더블 효과로 **{result}**가 두 번 적용됐어!"
            else:
                #  백스텝이어도 결과는 그냥 평범하게 넣음! (버프는 소모 안 함!)
                self.current_player.move_list.append(result)
                msg = f"🎲 **{result}**이/가 나왔어!"
            
            # 윷이나 모가 나오면 던질 기회 +1
            if result in ["윷", "모"]: 
                self.current_player.throw_count += 1
            
        self.selected_horse_pos = None

        is_turn_end = False
        
        if self.current_player.throw_count == 0:
            if self.current_player.active_buff == "테이크 아웃":
                # 테이크아웃: 던질 기회가 끝나면 무조건 턴 종료 & 보관
                self.current_player.takeout_storage.extend(self.current_player.move_list)
                self.current_player.active_buff = None
                msg += f"\n☕ 결과를 보관하고 {self.current_player.member.display_name}에게 턴을 넘겼어."
                is_turn_end = True
            elif not self.check_has_valid_move(self.current_player):
                if len(self.current_player.move_list) > 0:
                    # 빽도만 남아서 못 가는 경우 눈물 젖은 안내 메시지 출력
                    msg += f"\n😭 더 이상 이동할 수 있는 말이 없어!"
                    self.current_player.active_buff = None # 쓰지 못한 버프 찌꺼기 청소
                else:
                    msg += f"\n🔄 차례가 넘어갔어."
                is_turn_end = True

        if is_turn_end:
            enemy = self.player2 if self.current_player == self.player1 else self.player1
            self.current_player = enemy
            self.turn_count += 1
            self.current_player.throw_count = 1
            self.current_player.used_skill = False
            self.current_player.has_thrown = False
            self.current_player.is_resolving_skill = False
            self.current_player.move_list.clear()

            msg += f"\n🔄 턴이 종료되어 **{self.current_player.member.display_name}**의 차례로 넘어갔어."
            
            #  다음 턴을 시작하는 플레이어의 보관함에 있던 윷을 꺼내줌!
            if self.current_player.takeout_storage:
                self.current_player.move_list.extend(self.current_player.takeout_storage)
                self.current_player.takeout_storage.clear()
                msg += f"\n🥡 **{self.current_player.member.display_name}**이/가 테이크 아웃으로 보관했던 윷을 꺼내왔어!"
            
        await self.update_ui(interaction, msg)

    #  [핵심 콜백] 목적지 이동 버튼 눌렀을 때 (이동, 업기, 잡기 판정!)
    async def btn_move_callback(self, interaction: discord.Interaction, dest: int, used_yut: str):
        if interaction.user.id != self.current_player.member.id:
            return await interaction.response.send_message("❌ 지금은 네 턴이 아니야!", ephemeral=True)
            
        me = self.current_player
        enemy = self.player2 if me == self.player1 else self.player1
        start_pos = self.selected_horse_pos
        
        # 1. move_val 계산
        move_val = yut_to_number(used_yut)
        if me.active_buff == "백스텝":
            move_val = -move_val

        # ==================================================
        # 🚨 [신규] 트랩 CCTV 발동 구역 (지나온 경로 추적)
        # ==================================================
        passed_tiles = []
        
        if move_val > 0:
            if start_pos == -1:
                #  [버그 수정] 대기실 출발: 1번부터 move_val 번까지 순서대로 스쳐 지나감!
                passed_tiles = list(range(1, move_val + 1))
            else:
                # 판 위에서 출발
                path = FORWARD_PATHS[start_pos]
                passed_tiles = path[1 : move_val + 1]
        else:
            if start_pos != -1:
                # 역주행 로직
                steps = abs(move_val)
                paths = [[start_pos]]
                for _ in range(steps):
                    new_paths = []
                    for p in paths:
                        node = p[-1]
                        if node == 0:
                            new_paths.append(p + [0])
                            continue
                        for back_node in BACKWARD_MAP.get(node, [node]):
                            new_paths.append(p + [back_node])
                    paths = new_paths
                for p in paths:
                    if p[-1] == dest:
                        passed_tiles = p[1:]
                        break

        trap_msg = ""

        for pt in passed_tiles:
            if pt in self.traps:
                trap_type = self.traps[pt]
                trigger_pos = pt
                del self.traps[pt] # 트랩 1회용 삭제
                
                if trap_type == "포탈":
                    dest = 0
                    trap_msg = f"\n🌀 앗! {trigger_pos}번 칸을 지나며 **포탈**을 밟았어! 말이 **0번 칸**으로 텔레포트했어!"
                elif trap_type == "폭탄":
                    dest = -1
                    trap_msg = f"\n💣 앗! {trigger_pos}번 칸을 지나며 **폭탄**을 밟았어! 말이 **대기실**로 쫓겨났어!"
                break 

        #  2. 말 이동 (네가 짰던 완벽한 대기실 1개 vs 윷판 덩어리 로직 복구!)
        moved_count = 0
        if start_pos == -1:
            for i in range(4):
                if me.horses[i] == -1:
                    me.horses[i] = dest
                    moved_count = 1
                    break
        else:
            for i in range(4):
                if me.horses[i] == start_pos:
                    me.horses[i] = dest
                    moved_count += 1
                
        # 3. 이동 리스트에서 사용한 윷 지우기
        me.move_list.remove(used_yut)
        self.selected_horse_pos = None 
        
        # ⭐️ [수정된 부분] 트랩을 밟았는지 여부에 따라 메시지 출력을 완전히 분리!
        if trap_msg:
            # 트랩을 밟았을 때는 '-1번 칸 이동' 같은 기본 메시지를 버리고 트랩 메시지만 띄움!
            if me.active_buff == "백스텝":
                me.active_buff = None
            
            # trap_msg 앞에 붙어있던 '\n'을 떼어내고(strip), 어떤 윷을 써서 밟았는지만 뒤에 살짝 표시
            msg = f"{trap_msg.strip()} ({used_yut} 사용)"
        else:
            # 트랩을 안 밟았을 때만 평범한 이동 메시지 출력
            if me.active_buff == "백스텝":
                me.active_buff = None
                msg = f"⏪ 백스텝 효과 적용! 말이 뒤로 이동하여 {dest}번 칸에 도착했어! (-{used_yut} 사용)"
            else:
                msg = f"🐎 말이 **{dest}번 칸**으로 이동했어! (**{used_yut}** 사용)"

        #  4. 골인 판정 (네가 짰던 점수 업데이트 로직 복구!)
        if dest == 99:
            me.score += moved_count
            msg = f"🎉 {moved_count}개의 말이 **골인**했어! (+{moved_count}점)"
            
        #  5. 잡기 판정 (네가 짰던 심플하고 깔끔한 로직 복구!)
        elif dest != -1 and dest in enemy.horses:
            catch_count = 0
            for i in range(4):
                if enemy.horses[i] == dest:
                    enemy.horses[i] = -1 
                    catch_count += 1
            me.throw_count += 1 
            msg += f"\n⚔️ **상대방의 말을 {catch_count}개 잡았어!!** (한 번 더 던질 수 있어 🎲)"
            
        # 6. 턴 종료 판정 (자물쇠 해제 포함, 네 코드 그대로!)
        if not self.check_has_valid_move(me):
            # 윷이 남았는데도 강제 종료당하는 경우 메시지 추가
            if len(me.move_list) > 0:
                msg += f"\n😭 더 이상 이동할 수 있는 말이 없어!"
                me.active_buff = None # 쓰지 못한 버프 찌꺼기 청소
            self.current_player = enemy
            self.turn_count += 1
            self.current_player.throw_count = 1
            self.current_player.used_skill = False
            self.current_player.has_thrown = False
            self.current_player.is_resolving_skill = False
            self.current_player.move_list.clear()
            msg += f"\n🔄 턴이 종료되어 **{self.current_player.member.display_name}**의 차례로 넘어갔어."
            
            #  보관함 언패킹!
            if self.current_player.takeout_storage:
                self.current_player.move_list.extend(self.current_player.takeout_storage)
                self.current_player.takeout_storage.clear()
                msg += f"\n🥡 **{self.current_player.member.display_name}**이/가 테이크 아웃으로 보관했던 윷을 꺼내왔어!"
            
        await self.update_ui(interaction, msg)

    # 턴 넘기기 버튼 로직
    # async def btn_skip_callback(self, interaction: discord.Interaction):
    #     if interaction.user.id != self.current_player.member.id: return

    #     if self.current_player.is_resolving_skill:
    #         return await interaction.response.send_message("❌ 이미 초능력을 사용하기로 했어! 대상을 선택해줘.", ephemeral=True)
        
    #     #  스킵할 때 혹시 테이크아웃이 켜져 있으면 강제로 보관
    #     if self.current_player.active_buff == "테이크 아웃":
    #         self.current_player.takeout_storage.extend(self.current_player.move_list)
            
    #     self.current_player.active_buff = None

    #     self.current_player = self.player2 if self.current_player == self.player1 else self.player1
    #     self.turn_count += 1
    #     self.current_player.throw_count = 1
    #     self.current_player.used_skill = False
    #     self.current_player.has_thrown = False 
    #     self.current_player.is_resolving_skill = False
    #     self.current_player.move_list.clear()
    #     self.selected_horse_pos = None
        
    #     msg = "⏭️ 턴을 강제로 넘겼습니다."
        
    #     #  보관함 언패킹!
    #     if self.current_player.takeout_storage:
    #         self.current_player.move_list.extend(self.current_player.takeout_storage)
    #         self.current_player.takeout_storage.clear()
    #         msg += f"\n🥡 **{self.current_player.member.display_name}**이/가 보관했던 윷을 꺼내왔어!"
            
    #     await self.update_ui(interaction, msg)

    # 턴 넘기기 버튼 로직
    async def btn_skip_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.current_player.member.id: return

        if self.current_player.is_resolving_skill:
            return await interaction.response.send_message("❌ 이미 초능력을 사용하기로 했어! 대상을 선택해줘.", ephemeral=True)
        
        #  스킵할 때 혹시 테이크아웃이 켜져 있으면 강제로 보관
        if self.current_player.active_buff == "테이크 아웃":
            self.current_player.takeout_storage.extend(self.current_player.move_list)
            
        self.current_player.active_buff = None

        self.current_player = self.player2 if self.current_player == self.player1 else self.player1
        self.turn_count += 1
        self.current_player.throw_count = 1
        self.current_player.used_skill = False
        self.current_player.has_thrown = False 
        self.current_player.is_resolving_skill = False
        self.current_player.move_list.clear()
        self.selected_horse_pos = None
        
        msg = "⏭️ 턴을 강제로 넘겼습니다."
        
        #  보관함 언패킹!
        if self.current_player.takeout_storage:
            self.current_player.move_list.extend(self.current_player.takeout_storage)
            self.current_player.takeout_storage.clear()
            msg += f"\n🥡 **{self.current_player.member.display_name}**이/가 보관했던 윷을 꺼내왔어!"
            
        await self.update_ui(interaction, msg)

    #  [수정됨] 임베드에 텍스트 대신 방금 만든 이미지를 첨부!
    def create_board_embed(self):
        title_text = "🔮 초능력 윷놀이 🔮" if self.is_superpower else "🎲 클래식 윷놀이 🎲"
        
        embed = discord.Embed(
            title=title_text, 
            description=f"현재 턴: {self.current_player.emoji} **{self.current_player.member.display_name}**의 차례!",
            color=0x4CE2EC
        )
        embed.set_image(url="attachment://yut_board.png") 
        
        p1_horses = "🔴" * self.player1.horses.count(-1)
        p1_score = "" * self.player1.score
        p2_horses = "🔵" * self.player2.horses.count(-1)
        p2_score = "" * self.player2.score
        
        if self.is_superpower:
            #  썼으면 이름을 공개하고, 안 썼으면 ❓ 로 가림!
            p1_ys = self.player1.yut_skill if self.player1.yut_skill_used else "❓"
            p1_bs = self.player1.board_skill if self.player1.board_skill_used else "❓"
            p2_ys = self.player2.yut_skill if self.player2.yut_skill_used else "❓"
            p2_bs = self.player2.board_skill if self.player2.board_skill_used else "❓"
            
            p1_info = f"**윷 스킬:** {p1_ys}\n**말 스킬:** {p1_bs}\n**대기석:** {p1_horses}\n**골인:** {p1_score}"
            p2_info = f"**윷 스킬:** {p2_ys}\n**말 스킬:** {p2_bs}\n**대기석:** {p2_horses}\n**골인:** {p2_score}"
        else:
            p1_info = f"**대기석:** {p1_horses}\n**골인:** {p1_score}"
            p2_info = f"**대기석:** {p2_horses}\n**골인:** {p2_score}"
            
        embed.add_field(name=f"🔴 {self.player1.member.display_name}", value=p1_info, inline=True)
        embed.add_field(name=f"🔵 {self.player2.member.display_name}", value=p2_info, inline=True)
        
        move_str = " ".join([f"[{m}]" for m in self.current_player.move_list]) if self.current_player.move_list else "(비어 있음)"
        embed.add_field(name="🎯 현재 이동 리스트", value=f"➡️ **{move_str}**\n*(남은 윷 던지기 기회: {self.current_player.throw_count}번)*", inline=False)
        return embed

#  윷판의 모든 전진 경로를 맵핑한 사전 (현재 위치가 Key)
# 리스트의 인덱스가 곧 전진하는 칸 수! (예: 1칸 전진 -> path[1])
FORWARD_PATHS = {
    #  0번에 정착한 말은 다음 턴에 1칸(도)이라도 나오면 무조건 골인(99)!
    0: [0, 99, 99, 99, 99, 99, 99], 

    # 바깥쪽 테두리 (모서리 출발 제외)
    #  맨 끝에 19 -> 0 -> 99 순서로 이어지도록 0번을 싹 추가했어!
    1: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 0, 99],
    2: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 0, 99],
    3: [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 0, 99],
    4: [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 0, 99],
    6: [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 0, 99],
    7: [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 0, 99],
    8: [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 0, 99],
    9: [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 0, 99],
    11: [11, 12, 13, 14, 15, 16, 17, 18, 19, 0, 99],
    12: [12, 13, 14, 15, 16, 17, 18, 19, 0, 99],
    13: [13, 14, 15, 16, 17, 18, 19, 0, 99],
    14: [14, 15, 16, 17, 18, 19, 0, 99],
    15: [15, 16, 17, 18, 19, 0, 99],
    16: [16, 17, 18, 19, 0, 99],
    17: [17, 18, 19, 0, 99],
    18: [18, 19, 0, 99],
    19: [19, 0, 99], # 19번에서 '도'면 0번에 멈추고, '개'면 99로 나감!
    
    # 우상단 꺾임 루트 (5 -> 21 -> 22 -> 23 -> 24 -> 25 -> 15 -> ... -> 0 -> 99)
    5: [5, 21, 22, 23, 24, 25, 15, 16, 17, 18, 19, 0, 99],
    21: [21, 22, 23, 24, 25, 15, 16, 17, 18, 19, 0, 99],
    22: [22, 23, 24, 25, 15, 16, 17, 18, 19, 0, 99],
    24: [24, 25, 15, 16, 17, 18, 19, 0, 99],
    25: [25, 15, 16, 17, 18, 19, 0, 99],
    
    # 좌상단 꺾임 루트 (10 -> 26 -> 27 -> 23 -> 28 -> 29 -> 0 -> 99)
    10: [10, 26, 27, 23, 28, 29, 0, 99],
    26: [26, 27, 23, 28, 29, 0, 99],
    27: [27, 23, 28, 29, 0, 99],
    28: [28, 29, 0, 99],
    29: [29, 0, 99], # 29번에서 '도'면 0번에 멈추고, '개'면 99로 골인!
    
    # 정중앙 교차로(23번) 정착 후 출발 루트! 
    23: [23, 28, 29, 0, 99]
}

#  [수정] 빽도 역주행 맵도 맵 데이터에 맞게 톱니바퀴 조율!
BACKWARD_MAP = {
    0: [19, 29], #  결승선 갈림길
    1: [0], 2: [1], 3: [2], 4: [3], 5: [4], 6: [5], 7: [6], 8: [7], 9: [8], 
    10: [9], 11: [10], 12: [11], 13: [12], 14: [13], 
    15: [14, 25], #  좌하단 갈림길
    16: [15], 17: [16], 18: [17], 19: [18], 
    21: [5], 22: [21], 
    23: [22, 27], #  정중앙 갈림길
    24: [23], 25: [24],
    26: [10], 27: [26], 28: [23], 29: [28]
}

#  윷 결과값을 숫자(이동 칸 수)로 바꿔주는 헬퍼 함수
def yut_to_number(yut_str):
    mapping = {"도": 1, "개": 2, "걸": 3, "윷": 4, "모": 5, "빽도": -1,
               "-도": -1, "-개": -2, "-걸": -3, "-윷": -4, "-모": -5, "-빽도": 1}
    return mapping.get(yut_str, 0)

#  현재 위치와 이동 칸 수를 주면 '도착할 위치'를 뱉어내는 헬퍼 함수
def calculate_arrival(current_pos, move_value):
    if current_pos == -1:
        if move_value < 0: return [] # 빽도 방어
        return [move_value] # 도->0, 모->4로 정확히 리스트 반환
        
    #  빽도(-1) 및 백스텝(-N) 처리 (BFS 알고리즘 적용)
    if move_value < 0:
        steps = abs(move_value)
        current_nodes = set([current_pos]) # 중복 제거를 위해 set 사용
        
        for _ in range(steps):
            next_nodes = set()
            for node in current_nodes:
                #  [핵심 추가] 후진하다가 0번 칸(결승선 대기)에 도달하면 더 이상 후진하지 않고 멈춤!
                if node == 0:
                    next_nodes.add(0)
                    continue
                
                # 해당 노드에서 갈 수 있는 모든 뒤쪽 경로를 탐색
                for back_node in BACKWARD_MAP.get(node, [node]):
                    next_nodes.add(back_node)
            current_nodes = next_nodes
            
        return list(current_nodes) # 최종 가능한 목적지들 반환!
        
    # 전진 처리
    path = FORWARD_PATHS[current_pos]
    if move_value < len(path):
        return [path[move_value]]
    else:
        return [99]

# 3. 게임 시작 명령어
@bot.tree.command(name="윷놀이", description="친구와 함께 클래식 윷놀이를 시작합니다.")
@app_commands.describe(상대방="같이 게임할 유저를 선택하세요")
async def start_normal_yut(interaction: discord.Interaction, 상대방: discord.Member):
    if 상대방.bot: return await interaction.response.send_message("봇과는 윷놀이를 할 수 없어!", ephemeral=True)
    
    #  is_superpower=False 로 스위치 끄고 실행
    view = YutGameView(interaction.user, 상대방, is_superpower=False)
    image_file = view.generate_board_image() 
    embed = view.create_board_embed()
    
    await interaction.response.send_message(
        f"{interaction.user.mention}이/가 {상대방.mention}에게 클래식 윷놀이를 신청했어!\n(선공: {interaction.user.display_name})", 
        file=image_file, embed=embed, view=view
    )

@bot.tree.command(name="초능력윷놀이", description="친구와 함께 초능력 윷놀이를 시작합니다.")
@app_commands.describe(상대방="같이 게임할 유저를 선택하세요")
async def start_super_yut(interaction: discord.Interaction, 상대방: discord.Member):
    if 상대방.bot: return await interaction.response.send_message("봇과는 윷놀이를 할 수 없어!", ephemeral=True)
    
    #  is_superpower=True 로 스위치 켜고 실행!
    view = YutGameView(interaction.user, 상대방, is_superpower=True)
    image_file = view.generate_board_image() 
    embed = view.create_board_embed()
    
    await interaction.response.send_message(
        f"{interaction.user.mention}이/가 {상대방.mention} 에게 초능력 윷놀이를 신청했어!\n(선공: {interaction.user.display_name})", 
        file=image_file, embed=embed, view=view
    )




# ==========================================
# 포켓몬고 관련 명령어
# ==========================================

# ⭐️ 포켓몬 타입 & 날씨를 디스코드 기본 이모지로 매핑!
TYPE_KOREAN = {
    "Normal": "노말", "Fighting": "격투", "Flying": "비행", "Poison": "독",
    "Ground": "땅", "Rock": "바위", "Bug": "벌레", "Ghost": "고스트",
    "Steel": "강철", "Fire": "불꽃", "Water": "물", "Grass": "풀",
    "Electric": "전기", "Psychic": "에스퍼", "Ice": "얼음", "Dragon": "드래곤",
    "Dark": "악", "Fairy": "페어리"
}

WEATHER_KOREAN = {
    "sunny": "☀️ 맑음",
    "rain": "🌧️ 비",
    "partlycloudy_day": "⛅ 약간 구름",
    "cloudy": "☁️ 흐림",
    "windy": "💨 바람",
    "snow": "⛄ 눈",
    "fog": "🌫️ 안개"
}

# ⭐️ '포고'라는 이름의 명령어 그룹 클래스 생성!
class PoGoGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="포고", description="포켓몬 고 관련 명령어 모음이야!")

    @app_commands.command(name="레이드", description="현재 진행 중인 포켓몬 고 레이드 정보를 확인해!")
    async def raid(self, interaction: discord.Interaction):
        await interaction.response.defer() 
        
        data_url = "https://pokemon-go-api.github.io/pokemon-go-api/api/raidboss.json"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(data_url) as response:
                if response.status != 200:
                    return await interaction.followup.send("❌ 레이드 정보를 가져오는 데 실패했어! API 서버 상태를 확인해 봐.")
                
                raid_data = await response.json()

        target_data = raid_data.get("currentList", {})
        
        if not target_data:
            return await interaction.followup.send("❌ 현재 진행 중인 레이드 목록을 찾을 수 없어!")

        graphics_data = raid_data.get("graphics", {})
        image_url = ""
        
        if "Korean" in graphics_data and "png" in graphics_data["Korean"]:
            image_url = graphics_data["Korean"]["png"]
        elif "English" in graphics_data and "png" in graphics_data["English"]:
            image_url = graphics_data["English"]["png"]
            
        if image_url and not image_url.startswith("http"):
            if "api/graphics" in image_url:
                idx = image_url.find("api/graphics")
                image_url = "https://pokemon-go-api.github.io/pokemon-go-api/" + image_url[idx:]
            else:
                image_url = "https://pokemon-go-api.github.io/pokemon-go-api/" + image_url.lstrip("/")

        if not image_url:
            image_url = "https://pokemon-go-api.github.io/pokemon-go-api/api/graphics/English/default.png"

        tier_names = {
            "lvl1": "⭐ 1성 레이드",
            "lvl3": "⭐⭐⭐ 3성 레이드",
            "lvl5": "⭐⭐⭐⭐⭐ 5성 레이드",
            "mega": "🧬 메가 레이드",
            "legendary_mega": "🧬🌟 전설 메가 레이드",
            "ultra_beast": "🌌 울트라비스트 레이드",
            "shadow_lvl1": "🌑 그림자 1성 레이드",
            "shadow_lvl3": "🌑 그림자 3성 레이드",
            "shadow_lvl5": "🌑 그림자 5성 레이드",
            "ex": "🎫 EX 레이드"
        }

        # ⭐️ 임베드 설명(description)에 모든 텍스트를 한 번에 조립할 준비!
        description_text = "현재 진행 중인 레이드 정보야!\n"

        for tier_key, bosses in target_data.items():
            if not bosses: continue 

            tier_title = tier_names.get(tier_key, f"🔥 {tier_key} 레이드")
            
            # 1. 마크다운 헤더(###)를 써서 레이드 등급 제목을 크고 굵게!
            description_text += f"### {tier_title}\n"
            
            boss_list_text = []
            
            for boss in bosses:
                korean_name = boss.get("names", {}).get("Korean", boss.get("id", "Unknown"))
                
                # 1. 타입 (앞서 만든 TYPE_KOREAN 적용)
                types = boss.get("types", [])
                translated_types = [TYPE_KOREAN.get(t, t) for t in types]
                type_str = f"[{'/'.join(translated_types)}]" if translated_types else ""
                
                # 2. 날씨 (앞서 만든 WEATHER_KOREAN 적용)
                weathers = boss.get("weather", [])
                translated_weathers = [WEATHER_KOREAN.get(w.lower(), w) for w in weathers]
                weather_str = " / ".join(translated_weathers) if translated_weathers else "❌ 없음"
                
                # ⭐️ 3. [신규] 약점(Counter) 데이터 파싱
                # API가 어떻게 줄지 몰라서 리스트, 딕셔너리 모두 뚫어내는 방어막 적용!
                counters_raw = boss.get("counter", boss.get("counters", []))
                counters = []
                if isinstance(counters_raw, list):
                    for c in counters_raw:
                        if isinstance(c, str): counters.append(c)
                        elif isinstance(c, dict) and "type" in c: counters.append(c["type"])
                elif isinstance(counters_raw, dict):
                    counters = list(counters_raw.keys())
                
                translated_counters = [TYPE_KOREAN.get(c, c) for c in counters]
                counter_str = f"[{'/'.join(translated_counters)}]" if translated_counters else "정보 없음"
                
                # 4. CP 범위
                cp_range = boss.get("cpRange", [])
                cp_str = f"{cp_range[0]}~{cp_range[1]}" if len(cp_range) >= 2 else "?"
                
                boost_range = boss.get("cpRangeBoost", [])
                if boost_range and len(boost_range) >= 2:
                    cp_str += f" *(🌡️ {boost_range[0]}~{boost_range[1]})*"
                
                # ⭐️ 5. [UX 개선] 모바일 가독성을 위해 가로 나열을 포기하고 세로로 쌓기!
                # 'ㅤ' (투명 공백)을 써서 하위 항목들만 살짝 들여쓰기 된 것처럼 깔끔하게!
                boss_line = (
                    f"┃ 🔹 **{korean_name}** {type_str}\n"
                    f"┃ ㅤ⚔️ 약점: {counter_str}\n"
                    f"┃ ㅤ🌡️ 날씨: {weather_str}\n"
                    f"┃ ㅤ💯 CP: {cp_str}"
                )
                boss_list_text.append(boss_line)
                
            # 보스들 사이의 띄어쓰기 블록 처리
            description_text += "\n\n".join(boss_list_text) + "\n\n"
            
        embed = discord.Embed(
            title="⚔️ 현재 포켓몬 고 레이드 보스",
            description=description_text.strip(), # 조립된 텍스트를 한방에 꽂아넣기!
            color=0x4CE2EC 
        )

        embed.set_image(url=image_url)
        embed.set_footer(text="데이터 제공: pokemon-go-api")

        await interaction.followup.send(embed=embed)

# ⭐️ 봇의 명령어 트리에 우리가 만든 '포고' 그룹을 등록!
# (주의: bot.run(TOKEN) 바로 위쪽 같은 전역 공간에 둬야 해)
bot.tree.add_command(PoGoGroup())

bot.run(TOKEN)
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
                await message.channel.send(f"오! {users_str} 워들 완료 확인! (현재 {len(done_today)}명 완료)")
        return

    if "Wordle" in message.content and "🟩" in message.content:
        print(f"👀 {message.author.display_name}님의 워들 수동 결과 감지!")
        if message.author.id not in done_today:
            done_today.add(message.author.id)
            await message.channel.send(f"오! {message.author.display_name}, 수동으로 워들 완료 확인! (현재 {len(done_today)}명 완료)")
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
                await after.channel.send(f"오! {users_str}님 워들 완료! (현재 {len(done_today)}명 완료)")

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
                    "lon": lon, "lat": lat # ⭐️ 메모리에 위경도도 같이 저장!
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

# 1. 플레이어의 상태를 저장하는 데이터 클래스
class YutPlayer:
    def __init__(self, member: discord.Member, is_p1: bool):
        self.member = member
        self.emoji = "🔴" if is_p1 else "🔵"  # P1은 빨강, P2는 파랑
        self.horses = [-1, -1, -1, -1]       # 말 4개 (-1: 대기실, 99: 골인, 0~29: 보드판 좌표)
        self.score = 0                       # 골인한 말의 개수
        self.yut_skill = "랜덤 윷 스킬"       # (임시) 나중에 랜덤 부여 로직 추가
        self.board_skill = "랜덤 말 스킬"     # (임시) 나중에 랜덤 부여 로직 추가
        self.move_list = []                  # 예: ['도', '윷', '모']
        self.throw_count = 1                 # 윷을 던질 수 있는 남은 횟수 (기본 1회)
        self.used_skill = False              # 이번 턴에 스킬을 썼는지 여부

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
                desc = "아직 출발하지 않은 말입니다."
            else:
                label = f"윷판 {pos}번 칸에 있는 말 ({count}개)"
                desc = "클릭해서 이동 가능한 칸을 확인하세요."
                
            options.append(discord.SelectOption(label=label, description=desc, value=str(pos)))
            
        super().__init__(placeholder="👇 움직일 말을 선택하세요!", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        view: YutGameView = self.view
        # 선택한 말의 현재 위치를 View에 저장하고 화면을 업데이트(버튼 생성)함
        view.selected_horse_pos = int(self.values[0])
        await view.update_ui(interaction)

class YutGameView(discord.ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member, is_superpower: bool = False):
        super().__init__(timeout=None) # 시간 제한 없음
        self.is_superpower = is_superpower
        self.player1 = YutPlayer(p1, True)
        self.player2 = YutPlayer(p2, False)
        self.current_player = self.player1 # P1부터 시작!
        self.selected_horse_pos = None
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

        # ⭐️ 윈도우 & 리눅스 호환 폰트 로드 시스템
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

        # ⭐️ [새로 추가] 칸 안에 새겨넣을 노드 번호용 폰트 (크기 16으로 큼직하고 짱짱하게!)
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

            # ⭐️ [핵심] 화살표 위에 숫자를 덮어씌워 정중앙 정렬로 그리기!
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
                    
                    # ⭐️ 헬퍼 함수가 리스트를 반환하므로 반복문으로 처리!
                    destinations = calculate_arrival(self.selected_horse_pos, move_val)
                    
                    for dest in destinations: # ⭐️ 갈림길이 2개면 버튼이 2개 생김!
                        valid_move_exists = True
                        dest_label = "🏁 골인하기" if dest == 99 else f"📍 {dest}번 칸으로 이동"
                        btn_move = discord.ui.Button(label=f"{dest_label} ({yut_str})", style=discord.ButtonStyle.success)
                        btn_move.callback = lambda i, d=dest, y=yut_str: self.btn_move_callback(i, d, y)
                        self.add_item(btn_move)
                        
                if not valid_move_exists:
                    btn_error = discord.ui.Button(label="❌ 이 말은 현재 윷으로 이동 불가", style=discord.ButtonStyle.secondary, disabled=True)
                    self.add_item(btn_error)

        # ⭐️ 초능력 모드이고, 아직 스킬을 안 썼다면 '초능력 사용' 버튼 등장!
        if self.is_superpower and not self.current_player.used_skill:
            btn_skill = discord.ui.Button(label="초능력 사용", style=discord.ButtonStyle.success, emoji="✨", row=3)
            btn_skill.callback = self.btn_skill_callback
            self.add_item(btn_skill)
                        
        # ⭐️ 빽도만 나와서 어쩔 수 없이 턴을 버려야 할 때를 위한 스킵 버튼
        btn_skip = discord.ui.Button(label="턴 넘기기", style=discord.ButtonStyle.danger, row=4)
        btn_skip.callback = self.btn_skip_callback
        self.add_item(btn_skip)

    # ⭐️ 초능력 버튼 콜백 함수 (구버전 @discord.ui.button을 대체함!)
    async def btn_skill_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.current_player.member.id:
            return await interaction.response.send_message("지금은 당신의 턴이 아닙니다!", ephemeral=True)
            
        await interaction.response.send_message("초능력 선택 UI가 오픈될 예정입니다. (개발 중 🛠️)", ephemeral=True)

    # ⭐️ 화면을 새로고침하는 헬퍼 함수
    async def update_ui(self, interaction: discord.Interaction, message_text=None):
        # ⭐️ 1. 게임 종료(승리) 판정! 4점을 먼저 내면 즉시 게임 끝!
        if self.player1.score >= 4 or self.player2.score >= 4:
            winner = self.player1 if self.player1.score >= 4 else self.player2
            
            self.clear_items() # 텅 빈 드롭다운을 만들지 않도록 모든 버튼/메뉴 싹 지우기
            image_file = self.generate_board_image()
            embed = self.create_board_embed()
            
            # 승리 축하 메시지 추가
            embed.color = 0x00FF00 # 임베드 띠 색상을 영롱한 초록색으로 변경
            embed.add_field(name="🏆 게임 종료 🏆", value=f"🎉 **{winner.member.display_name}** 님이 4점을 달성하여 최종 승리했습니다!", inline=False)
            
            await interaction.response.edit_message(content=f"🎊 {winner.member.mention} 님의 승리!!", attachments=[image_file], embed=embed, view=None)
            self.stop() # ⭐️ 더 이상 상호작용을 받지 않고 봇의 대기 상태를 종료함
            return

        # 2. 게임이 안 끝났다면 평소처럼 UI 세팅
        self.setup_buttons()
        image_file = self.generate_board_image()
        embed = self.create_board_embed()
        
        content = message_text if message_text else f"현재 턴: {self.current_player.member.mention}"
        await interaction.response.edit_message(content=content, attachments=[image_file], embed=embed, view=self)

    # [콜백] 윷 던지기 버튼 눌렀을 때
    async def btn_throw_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.current_player.member.id:
            return await interaction.response.send_message("당신의 턴이 아닙니다!", ephemeral=True)
            
        import random
        
        # ⭐️ 네가 기획한 현실적인 확률 도입!
        yut_results = ["낙", "도", "개", "걸", "윷", "모", "빽도"]
        # 퍼센트를 가중치(weights)로 그대로 사용!
        yut_weights = [1.5, 11.35, 34.04, 34.04, 12.77, 2.52, 3.78]
        
        # random.choices를 사용하면 가중치에 맞게 1개를 뽑아줌
        result = random.choices(yut_results, weights=yut_weights, k=1)[0]
        
        self.current_player.throw_count -= 1
        
        # ⭐️ '낙' 처리 로직
        if result == "낙":
            msg = "😱 앗! 윷이 판 밖으로 나갔습니다! (**낙**)"
        else:
            self.current_player.move_list.append(result)
            # 윷이나 모가 나오면 던질 기회 +1
            if result in ["윷", "모"]: 
                self.current_player.throw_count += 1
            msg = f"🎲 **{result}**가 나왔습니다!"
            
        self.selected_horse_pos = None # 윷을 새로 던지면 말 선택 초기화
        
        # ⭐️ [핵심] 낙이 나와서 던질 기회가 날아갔는데, 쓸 수 있는 윷(이동 리스트)도 없다면? -> 턴 강제 종료!
        if self.current_player.throw_count == 0 and len(self.current_player.move_list) == 0:
            enemy = self.player2 if self.current_player == self.player1 else self.player1
            self.current_player = enemy
            self.current_player.throw_count = 1
            self.current_player.used_skill = False
            self.current_player.move_list.clear()
            msg += f"\n🔄 이동할 수 없어 **{self.current_player.member.display_name}**의 차례로 넘어갑니다."
            
        await self.update_ui(interaction, msg)

    # ⭐️ [핵심 콜백] 목적지 이동 버튼 눌렀을 때 (이동, 업기, 잡기 판정!)
    async def btn_move_callback(self, interaction: discord.Interaction, dest: int, used_yut: str):
        if interaction.user.id != self.current_player.member.id:
            return await interaction.response.send_message("당신의 턴이 아닙니다!", ephemeral=True)
            
        me = self.current_player
        enemy = self.player2 if me == self.player1 else self.player1
        start_pos = self.selected_horse_pos
        
        # ⭐️ 1. 말 이동 (대기실 출발 vs 윷판 이동 로직 분리!)
        moved_count = 0
        if start_pos == -1:
            # [대기실 출발] 위치가 -1인 말 중에서 딱 '1개'만 찾아서 보냄!
            for i in range(4):
                if me.horses[i] == -1:
                    me.horses[i] = dest
                    moved_count = 1
                    break # ⭐️ 1개만 옮기고 즉시 탈출!
        else:
            # [윷판 이동] 이미 판에 나와 있는 말은 같은 칸에 있는(업힌) 애들 전부 묶어서 이동!
            for i in range(4):
                if me.horses[i] == start_pos:
                    me.horses[i] = dest
                    moved_count += 1
                
        # 2. 이동 리스트에서 사용한 윷 지우기
        me.move_list.remove(used_yut)
        self.selected_horse_pos = None # 이동 후 선택 초기화
        
        msg = f"🐎 말이 {dest}번 칸으로 이동했습니다! ({used_yut} 사용)"
        
        # 3. 골인 판정
        if dest == 99:
            me.score += moved_count
            msg = f"🎉 {moved_count}개의 말이 **골인**했습니다! (+{moved_count}점)"
            
        # 4. 잡기 판정 (도착한 곳에 적의 말이 있다면?)
        elif dest != -1 and dest in enemy.horses:
            catch_count = 0
            for i in range(4):
                if enemy.horses[i] == dest:
                    enemy.horses[i] = -1 # 대기실로 쫓아냄
                    catch_count += 1
            me.throw_count += 1 # ⭐️ 상대 말을 잡으면 윷 던지기 기회 +1 !
            msg = f"⚔️ **상대방의 말을 {catch_count}개 잡았습니다!!** (한 번 더 던질 수 있습니다 🎲)"
            
        # 5. 턴 종료 판정 (던질 기회도 없고, 남은 리스트도 없으면 상대 턴으로!)
        if me.throw_count == 0 and len(me.move_list) == 0:
            self.current_player = enemy
            self.current_player.throw_count = 1
            self.current_player.used_skill = False
            self.current_player.move_list.clear()
            msg += f"\n🔄 턴이 종료되어 **{self.current_player.member.display_name}**의 차례로 넘어갑니다."
            
        await self.update_ui(interaction, msg)

    # 턴 넘기기 버튼 로직
    async def btn_skip_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.current_player.member.id: return
        self.current_player = self.player2 if self.current_player == self.player1 else self.player1
        self.current_player.throw_count = 1
        self.current_player.move_list.clear()
        self.selected_horse_pos = None
        await self.update_ui(interaction, f"⏭️ 턴을 강제로 넘겼습니다.")

    # ⭐️ [수정됨] 임베드에 텍스트 대신 방금 만든 이미지를 첨부!
    def create_board_embed(self):
        # ⭐️ 모드에 따라 타이틀 다르게 설정
        title_text = "🔮 메이플 초능력 윷놀이 🔮" if self.is_superpower else "🎲 클래식 윷놀이 🎲"
        
        embed = discord.Embed(
            title=title_text, 
            description=f"현재 턴: {self.current_player.emoji} **{self.current_player.member.display_name}**의 차례입니다!",
            color=0xFF9900
        )
        embed.set_image(url="attachment://yut_board.png") 
        
        p1_horses = "🔴" * self.player1.horses.count(-1) + " (대기)"
        p1_score = "⭐" * self.player1.score + f" ({self.player1.score}점)"
        p2_horses = "🔵" * self.player2.horses.count(-1) + " (대기)"
        p2_score = "⭐" * self.player2.score + f" ({self.player2.score}점)"
        
        # ⭐️ 초능력 모드일 때만 스킬 정보 표시!
        if self.is_superpower:
            p1_info = f"**윷 스킬:** {self.player1.yut_skill}\n**말 스킬:** {self.player1.board_skill}\n**대기석:** {p1_horses}\n**골인:** {p1_score}"
            p2_info = f"**윷 스킬:** {self.player2.yut_skill}\n**말 스킬:** {self.player2.board_skill}\n**대기석:** {p2_horses}\n**골인:** {p2_score}"
        else:
            p1_info = f"**대기석:** {p1_horses}\n**골인:** {p1_score}"
            p2_info = f"**대기석:** {p2_horses}\n**골인:** {p2_score}"
            
        embed.add_field(name=f"🔴 {self.player1.member.display_name}", value=p1_info, inline=True)
        embed.add_field(name=f"🔵 {self.player2.member.display_name}", value=p2_info, inline=True)
        
        move_str = " ".join([f"[{m}]" for m in self.current_player.move_list]) if self.current_player.move_list else "(비어 있음)"
        embed.add_field(name="🎯 현재 이동 리스트", value=f"➡️ **{move_str}**\n*(남은 윷 던지기 기회: {self.current_player.throw_count}번)*", inline=False)
        return embed

# ⭐️ 윷판의 모든 전진 경로를 맵핑한 사전 (현재 위치가 Key)
# 리스트의 인덱스가 곧 전진하는 칸 수! (예: 1칸 전진 -> path[1])
FORWARD_PATHS = {
    # ⭐️ 0번에 정착한 말은 다음 턴에 1칸(도)이라도 나오면 무조건 골인(99)!
    0: [0, 99, 99, 99, 99, 99, 99], 

    # 바깥쪽 테두리 (모서리 출발 제외)
    # ⭐️ 맨 끝에 19 -> 0 -> 99 순서로 이어지도록 0번을 싹 추가했어!
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

# ⭐️ [수정] 빽도 역주행 맵도 맵 데이터에 맞게 톱니바퀴 조율!
BACKWARD_MAP = {
    0: [19, 29], # ⭐️ 결승선 갈림길
    1: [0], 2: [1], 3: [2], 4: [3], 5: [4], 6: [5], 7: [6], 8: [7], 9: [8], 
    10: [9], 11: [10], 12: [11], 13: [12], 14: [13], 
    15: [14, 25], # ⭐️ 좌하단 갈림길
    16: [15], 17: [16], 18: [17], 19: [18], 
    21: [5], 22: [21], 
    23: [22, 27], # ⭐️ 정중앙 갈림길
    24: [23], 25: [24],
    26: [10], 27: [26], 28: [23], 29: [28]
}

# ⭐️ 윷 결과값을 숫자(이동 칸 수)로 바꿔주는 헬퍼 함수
def yut_to_number(yut_str):
    mapping = {"도": 1, "개": 2, "걸": 3, "윷": 4, "모": 5, "빽도": -1}
    return mapping.get(yut_str, 0)

# ⭐️ 현재 위치와 이동 칸 수를 주면 '도착할 위치'를 뱉어내는 헬퍼 함수
def calculate_arrival(current_pos, move_value):
    if current_pos == -1:
        if move_value < 0: return [] # 빽도 방어
        return [move_value] # 도->0, 모->4로 정확히 리스트 반환
        
    # ⭐️ 빽도(-1) 및 백스텝(-N) 처리 (BFS 알고리즘 적용)
    if move_value < 0:
        steps = abs(move_value)
        current_nodes = set([current_pos]) # 중복 제거를 위해 set 사용
        
        for _ in range(steps):
            next_nodes = set()
            for node in current_nodes:
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
@bot.tree.command(name="윷놀이", description="친구와 함께 오리지널 클래식 윷놀이를 시작합니다!")
@app_commands.describe(상대방="같이 게임할 유저를 선택하세요")
async def start_normal_yut(interaction: discord.Interaction, 상대방: discord.Member):
    if 상대방.bot: return await interaction.response.send_message("봇과는 윷놀이를 할 수 없어요!", ephemeral=True)
    
    # ⭐️ is_superpower=False 로 스위치 끄고 실행
    view = YutGameView(interaction.user, 상대방, is_superpower=False)
    image_file = view.generate_board_image() 
    embed = view.create_board_embed()
    
    await interaction.response.send_message(
        f"{interaction.user.mention} 님이 {상대방.mention} 님에게 클래식 윷놀이를 신청했습니다!\n(선공: {interaction.user.display_name})", 
        file=image_file, embed=embed, view=view
    )

@bot.tree.command(name="초능력윷놀이", description="친구와 함께 초능력 윷놀이를 시작합니다!")
@app_commands.describe(상대방="같이 게임할 유저를 선택하세요")
async def start_super_yut(interaction: discord.Interaction, 상대방: discord.Member):
    if 상대방.bot: return await interaction.response.send_message("봇과는 윷놀이를 할 수 없어요!", ephemeral=True)
    
    # ⭐️ is_superpower=True 로 스위치 켜고 실행!
    view = YutGameView(interaction.user, 상대방, is_superpower=True)
    image_file = view.generate_board_image() 
    embed = view.create_board_embed()
    
    await interaction.response.send_message(
        f"{interaction.user.mention} 님이 {상대방.mention} 님에게 초능력 윷놀이를 신청했습니다!\n(선공: {interaction.user.display_name})", 
        file=image_file, embed=embed, view=view
    )

bot.run(TOKEN)
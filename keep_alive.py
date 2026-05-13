from flask import Flask
from threading import Thread
import logging

app = Flask(__name__)

@app.route('/')
def home():
    return "나불이 메인 페이지입니다! 봇이 살아있습니다."

# UptimeRobot 전용 가벼운 헬스체크 뒷문 추가
@app.route('/ping')
def ping():
    return "pong", 200 # 아주 가볍게 "pong"이라는 글자와 '정상(200)' 신호만 보냄

def run():
    # Flask가 5분마다 접속 기록을 터미널에 도배하는 걸 막는 최적화
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
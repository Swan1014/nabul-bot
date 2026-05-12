from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "워들 봇이 24시간 쌩쌩하게 살아있습니다."

def run():
    # Render 서버가 지정해주는 포트를 자동으로 찾아서 엽니다.
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
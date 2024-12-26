from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from datetime import datetime
import sqlite3
import uuid
import json
import base64
import game_manager
import io
import time
import threading
game_creation_lock = threading.Lock()

app = Flask(__name__)

DATABASE = 'data/database.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/log')
def log_page():
    return render_template('log.html')

@app.route('/log_data')
def log_data():
    info = game_manager.get_all_process_info()
    return jsonify(info)

# 初始化資料庫 (可在專案初次執行時執行)
def init_db():
    conn = get_db_connection()
    conn.execute('''
    CREATE TABLE IF NOT EXISTS plays (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_name TEXT,
        track TEXT,
        start_time DATETIME,
        end_time DATETIME,
        score INTEGER,
        finished BOOLEAN
    )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    # 获取排行榜数据
    conn = get_db_connection()
    circle_leaderboard = conn.execute(
        'SELECT user_name, score, end_time FROM plays WHERE track="circle" ORDER BY score DESC LIMIT 10'
    ).fetchall()
    austria_leaderboard = conn.execute(
        'SELECT user_name, score, end_time FROM plays WHERE track="austria" ORDER BY score DESC LIMIT 10'
    ).fetchall()
    conn.close()

    # 转换为字典列表
    circle_leaderboard = [dict(row) for row in circle_leaderboard]
    austria_leaderboard = [dict(row) for row in austria_leaderboard]

    # 获取高亮玩家名字
    user_name = request.args.get('user_name', '')

    return render_template(
        'index.html',
        circle_leaderboard=circle_leaderboard,
        austria_leaderboard=austria_leaderboard,
        highlight_user=user_name
    )


@app.route('/start_game', methods=['POST'])
def start_game():
    user_name = request.form.get('username')
    track = request.form.get('track')

    if not user_name or not track:
        return "Missing parameters", 400

    with game_creation_lock:
        # 建立資料庫紀錄
        conn = get_db_connection()
        start_time = datetime.now()
        conn.execute('INSERT INTO plays (user_name, track, start_time, finished) VALUES (?, ?, ?, ?)', 
                     (user_name, track, start_time, False))
        play_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        
        conn.commit()
        conn.close()

        # 開啟遊戲子程序
        game_id = game_manager.start_game_process(user_name, track)

        # 暫存遊戲ID與資料表ID的對應
        game_manager.set_play_id_for_game(game_id, play_id)



    return redirect(url_for('game_page', game_id=game_id))

@app.route('/game/<game_id>')
def game_page(game_id):
    player_name = game_manager.get_play_name_for_game(game_id)
    action_port = game_manager.get_action_port_for_game(game_id)
    return render_template('game.html', game_id=game_id,player_id=player_name,action_port=action_port)


@app.route('/stop_game/<game_id>', methods=['POST'])
def stop_game(game_id):
    # 遊戲結束
    final_score = request.form.get('score', 0)
    finished = request.form.get('finished', 'false').lower() == 'true'
    game_manager.stop_game_process(game_id)
    play_id = game_manager.get_play_id_for_game(game_id)

    # 从数据库获取玩家名字
    conn = get_db_connection()
    conn.execute('UPDATE plays SET end_time=?, score=?, finished=? WHERE id=?',
                 (datetime.now(), final_score, finished, play_id))
    conn.commit()
    conn.close()
    return "OK", 200
@app.route('/scoreboard')
def scoreboard():
    conn = get_db_connection()
    rows = conn.execute('SELECT user_name, track, start_time, end_time, score, finished FROM plays ORDER BY score DESC').fetchall()
    conn.close()
    return render_template('scoreboard.html', records=rows)



if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=4999)

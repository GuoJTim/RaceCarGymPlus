import subprocess
import socket
import threading
import time
import os
import requests
import signal
import json
import base64
import io

game_processes = {
  # game_id: {
  #    'process': Popen物件,
  #    'user_name': str,
  #    'track': str,
  #    'start_time': float,
  #    'score': int,
  #    'finished': bool,
  #    'play_id': int,
  #    'port': int,            # 新增紀錄該子程序HTTP服務的port
  # }
}

WBSOCKET_PORT = 30000
def start_game_process(user_name, track):
    # 检查是否存在该玩家的未结束游戏
    for game_id, info in game_processes.items():
        if info['user_name'] == user_name and info['status'] == 'running':
            print(f"已有未结束的游戏，game_id: {game_id}")
            return game_id  # 返回现有游戏的 game_id

    # 如果不存在，则创建新的游戏进程
    game_id = str(len(game_processes) + 1)
    action_port = WBSOCKET_PORT + int(game_id)  # WebSocket 动作通道

    print(" ".join([
        'python3', 'run_game.py', 
        '--track', track, 
        '--action_port', str(action_port),
        '--username', user_name
    ]))

    # 启动子进程
    proc = subprocess.Popen(
        [
            'python3', 'run_game.py', 
            '--track', track, 
            '--action_port', str(action_port),
            '--username', user_name
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    # 检测端口是否成功启动
    def is_port_open(port):
        try:
            with socket.create_connection(('10.5.11.104', port), timeout=1):
                return True
        except (socket.timeout, ConnectionRefusedError):
            return False

    max_retries = 10  # 最大尝试次数
    for _ in range(max_retries):
        if is_port_open(action_port):
            break
        time.sleep(0.5)  # 每次等待 0.5 秒
    else:
        # 如果超过最大重试次数，子进程启动失败
        print(f"子进程启动失败: action_port={action_port}")
        proc.terminate()
        raise RuntimeError("无法连接到子进程的 WebSocket 端口")

    time.sleep(3)

    game_processes[game_id] = {
        'game_id': game_id,
        'process': proc,
        'user_name': user_name,
        'track': track,
        'action_port': action_port,
        'start_time': time.time(),
        'status': 'running'
    }
    return game_id



      


# 停止遊戲進程
def stop_game_process(game_id):
    info = game_processes.get(game_id)
    if info:
        # 停止子程序
        proc = info['process']
        # if proc.poll() is None:
        #     proc.terminate()
        # 更新狀態
        info['status'] = 'deleted'

# 設定 play_id 與遊戲進程的對應
def set_play_id_for_game(game_id, play_id):
    if game_id in game_processes:
        game_processes[game_id]['play_id'] = play_id

# 獲取遊戲進程對應的 play_id
def get_play_id_for_game(game_id):
    info = game_processes.get(game_id)
    if info:
        return info['play_id']
    return None

# 獲取遊戲進程對應的 play_id
def get_play_name_for_game(game_id):
    info = game_processes.get(game_id)
    if info:
        return info['user_name']
    return None
def get_action_port_for_game(game_id):
    info = game_processes.get(game_id)
    if info:
        return info['action_port']
    return None

def get_all_process_info():
    # 回傳所有process的狀態資訊
    # 順便檢查有無已結束未更新狀態的 process
    for gid, info in game_processes.items():
        proc = info['process']
        if proc.poll() is not None and info['status'] == 'running':
            info['status'] = 'ended'

    # 將game_processes轉為可序列化的dict
    result = []
    for gid, info in game_processes.items():
        result.append({
            'game_id': gid,
            'user_name': info['user_name'],
            'track': info['track'],
            'start_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(info['start_time'])),
            'status': info['status']
        })
    return result

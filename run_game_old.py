import socket
import sys
import json
import base64
import threading
import time
import asyncio
import websockets
from environment import EnvironmentWrapper


# WebSocket 處理動作通道
async def handle_action_channel(websocket):
    print("WebSocket connected for action channel")
    try:
        async for message in websocket:
            try:
                action = json.loads(message)  # 接收到的動作指令
                env_instance.step(action)   # 執行動作

                # 获取游戏状态
                status = env_instance.get_status()

                # 返回状态给客户端
                response = json.dumps({
                    "status": True,
                    **status
                })
                await websocket.send(response)
            except Exception as e:
                error_response = json.dumps({
                    "status": False,
                    "error": str(e)
                })
                await websocket.send(error_response)
    except websockets.ConnectionClosed:
        print(f"WebSocket disconnected on port {action_port}")
    except Exception as e:
        print(f"WebSocket error: {e}")
# 啟動 WebSocket Server
async def start_websocket_server():
    
    async with websockets.serve(handle_action_channel, "0.0.0.0", action_port):
        print(f"WebSocket server listening on port {action_port}...")
        await asyncio.Future()  # 永遠不結束
        
        
# 假設參數: --track circle --control_port 6000 --data_port 6001 --action_port 6002
track = "circle"
control_port = 6000
data_port = 6001

# 處理命令行參數
args = sys.argv[1:]
for i in range(0, len(args), 2):
    if args[i] == '--track':
        track = args[i+1]
    elif args[i] == '--control_port':
        control_port = int(args[i+1])
    elif args[i] == '--data_port':
        data_port = int(args[i+1])
    elif args[i] == '--action_port':
        action_port = int(args[i+1])

# 初始化遊戲環境
env_instance = EnvironmentWrapper(track)

# 建立 TCP Server
control_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
control_sock.bind(('0.0.0.0', control_port))
control_sock.listen(1)
print(f"Control channel listening on port {control_port}...")

data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
data_sock.bind(('0.0.0.0', data_port))
data_sock.listen(1)
print(f"Data channel listening on port {data_port}...")


control_conn, _ = control_sock.accept()
data_conn, _ = data_sock.accept()
print("All channels connected.")



# 處理控制通道
def handle_control_channel():
    try:
        while True:
            length_data = control_conn.recv(4)
            if not length_data:
                break
            length = int.from_bytes(length_data, 'big')
            command = control_conn.recv(length).decode('utf-8').strip()

            if command == "GET_STATUS":
                status = env_instance.get_status()
                response = json.dumps({"type": "status", **status})
                send_with_length(control_conn, response)
            else:
                response = json.dumps({"error": "unknown command"})
                send_with_length(control_conn, response)
    except Exception as e:
        print(f"Control channel error: {e}")
    finally:
        control_conn.close()

# 處理資料通道
def handle_data_channel():
    try:
        while True:
            command = data_conn.recv(1024).decode('utf-8').strip()
            if command.startswith("GET_IMG"):
                img_byte_arr = env_instance.get_image_bytes()
                img_data = img_byte_arr.read()
                b64_img = base64.b64encode(img_data).decode('utf-8')
                response = json.dumps({"type": "img", "data": b64_img}) + "\n"
                
                data_conn.sendall(response.encode('utf-8'))
    except Exception as e:
        print(f"Data channel error: {e}")
    finally:
        data_conn.close()




# 發送消息時添加長度標頭
def send_with_length(sock, msg):
    data = msg.encode('utf-8')
    length = len(data)
    sock.sendall(length.to_bytes(4, 'big'))
    sock.sendall(data)


# 啟動 TCP Server 和 WebSocket Server
def main():
    control_thread = threading.Thread(target=handle_control_channel, daemon=True)
    data_thread = threading.Thread(target=handle_data_channel, daemon=True)

    
    control_thread.start()
    data_thread.start()

    asyncio.run(start_websocket_server())  # 啟動 WebSocket Server


    control_thread.join()
    data_thread.join()

    control_sock.close()
    data_sock.close()

if __name__ == "__main__":
    main()
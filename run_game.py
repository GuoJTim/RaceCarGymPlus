import asyncio
import websockets
import json
from environment import EnvironmentWrapper
import base64
import io
import sys

# 获取命令行参数
track = "circle"
action_port = 8765  # 默认 WebSocket 动作通道
username = ""
args = sys.argv[1:]
for i in range(0, len(args), 2):
    if args[i] == '--track':
        track = args[i + 1]
    elif args[i] == '--action_port':
        action_port = int(args[i + 1])
    elif args[i] == '--username':
        username = (args[i + 1])
    

# 初始化游戏环境
env_instance = EnvironmentWrapper(track,username)

async def handle_client(websocket):
    print(f"WebSocket connected on port {action_port}")
    try:
        async for message in websocket:
            request = json.loads(message)
            command = request.get("command")

            if command == "GET_STATUS":
                status = env_instance.get_status()
                response = json.dumps({"type": "status", **status})
                await websocket.send(response)
                
                if env_instance.isEnded():
                    env_instance.save_offline_data()
                    asyncio.get_event_loop().stop()

            elif command == "SET_ACTION":
                action = request.get("action", {})
                env_instance.step(action)
                response = json.dumps({"type": "action_ack", "success": True})
                await websocket.send(response)
            
            elif command == "TERMINATE":
                env_instance.force_stop()
                response = json.dumps({"type": "terminate", "success": True})
                await websocket.send(response)
                asyncio.get_event_loop().stop()
                
                

            elif command == "GET_IMG":
                img_data = env_instance.get_image_bytes().read()
                b64_img = base64.b64encode(img_data).decode('utf-8')
                response = json.dumps({"type": "image", "data": b64_img})
                await websocket.send(response)
            elif command == "GET_WHOLE_IMG":
                img_data = env_instance.get_img_views_bytes().read()
                b64_img = base64.b64encode(img_data).decode('utf-8')
                response = json.dumps({"type": "full_image", "data": b64_img})
                await websocket.send(response)
            else:
                response = json.dumps({"type": "error", "message": "Unknown command"})
                await websocket.send(response)
                
    except websockets.ConnectionClosed:
        print(f"WebSocket disconnected on port {action_port}")
    except Exception as e:
        print(f"Error: {e}")

async def main():
    async with websockets.serve(handle_client, "10.5.11.104", action_port):
        print(f"WebSocket server listening on port {action_port}")
        await asyncio.Future()  # 保持服务器运行

if __name__ == "__main__":
    asyncio.run(main())

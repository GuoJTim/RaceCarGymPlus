import time
from datetime import datetime
from pathlib import Path
import io
from PIL import Image
import numpy as np
from racecar_gym.env import RaceEnv
from PIL import Image, ImageDraw, ImageFont

# MAX_ACCU_TIME = 300
SERVER_RAISE_EXCEPTION = False
output_freq = 50  # 假設原程式有此頻率控制

def create_real_env(track):
    # TODO: 根據 track 建立實際的 gym-like 環境, e.g. env = SomeRacingEnv(track)
    # env.reset() -> obs, info
    
    if track == "circle":
        scenario = "circle_cw_competition_collisionStop"
    else:
        scenario = "austria_competition"
    env = RaceEnv(scenario=scenario,
                  render_mode='rgb_array_birds_eye',
                  reset_when_collision=True if 'austria' in scenario else False)
    
    return env



class EnvironmentWrapper:
    def __init__(self, track,username):
        self.track = track
        self.env = create_real_env(track)
        self.obs, self.info = self.env.reset()
        self.terminal = False
        self.trunc = False
        self.step_count = 0
        self.accu_time = 0.0
        self.total_reward = 0.0
        self.last_get_obs_time = time.time()
        self.images = []
        self.sid = username  # 可從外部傳入
        self.saved = False
        self.file_name = ""
        self.force_stop = False
        self.offline_data = {
            "observations": [],
            "actions": [],
            "rewards": [],
            "dones": [],
            "infos": []
        } 
        self.score = 0
        self.env_time = 0
        self.lap = 0
        self.progress = 0


    def get_observation(self):
        return self.obs

    def get_image_bytes(self):
        # 將目前 obs 轉成PNG圖像並回傳bytes
        img = Image.fromarray(self.obs.transpose((1, 2, 0)))
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr
    def force_stop(self):
        self.terminal = True
        self.force_stop = True
        
    def step(self, action):
        if self.terminal:
            return
        # string is (x ,x)
        action = [action['throttle'], action['steer']]
        # 計算經過時間
        now = time.time()
        self.accu_time += (now - self.last_get_obs_time)
        self.last_get_obs_time = now
        

        self.step_count += 1
        self.obs, reward, self.terminal, self.trunc, self.info = self.env.step(action)
        self.total_reward += reward
        
        self.offline_data["observations"].append(self.obs)
        self.offline_data["actions"].append(action)
        self.offline_data["rewards"].append(reward)
        self.offline_data["dones"].append(self.terminal)
        self.offline_data["infos"].append(self.info)

        self.progress = self.info['progress']
        self.lap = int(self.info['lap'])
        self.score = self.lap + self.progress - 1.0
        
        self.env_time = self.info['time']
        print_info = f'>>>> Step: {self.step_count} Lap: {self.lap}, Progress: {self.progress:.3f}, EnvTime: {self.env_time:.3f}, AccTime: {self.accu_time:.3f}'
        if self.info.get('n_collision') is not None:
            print_info += f' Collision: {self.info["n_collision"]}'
        if self.info.get('collision_penalties') is not None:
            print_info += ' CollisionPenalties: ' + ' '.join(f'{p:.3f}' for p in self.info["collision_penalties"])
            self.env_time = self.info['time'] + sum([v for v in self.info["collision_penalties"]])
        # print(print_info)

         
    def save_offline_data(self):
        
        if self.saved:
            return
        self.saved = True
        # 保存为 JSON 文件或 npz 文件
        if self.score >= 1:
            self.file_name = f'{self.sid}_finished_{self.score}_{datetime.now().strftime("%Y%m%d-%H%M%S")}'
        elif self.force_stop:
            self.file_name = f'{self.sid}_stopped_{self.score}_{datetime.now().strftime("%Y%m%d-%H%M%S")}'
        else:
            self.file_name = f'{self.sid}_normal_{self.score}_{datetime.now().strftime("%Y%m%d-%H%M%S")}'
        
        if self.track == "circle":
            outdir = "circle_stored_offline_data/"
        else:
            outdir = "aust_stored_offline_data/"
        # 将数据保存为 .npz 格式
        np.savez(
            outdir + self.file_name,
            observations=np.array(self.offline_data["observations"], dtype=object),
            actions=np.array(self.offline_data["actions"]),
            rewards=np.array(self.offline_data["rewards"]),
            dones=np.array(self.offline_data["dones"]),
            infos=np.array(self.offline_data["infos"], dtype=object)
        )
    def isEnded(self):
        return self.terminal

    def get_status(self):
        # 回傳非obs的環境參數，如terminal, total_reward, step_count等
        # total_reward可自行計算(假設info內有紀錄或自行加總)
        # 下例僅示意
        
        return {
            'terminal': bool(self.terminal),
            'truncated': bool(self.trunc),
            'step': self.step_count,
            'acc_time': self.env_time,
            'score': self.score,
            'record_name': self.file_name
        }

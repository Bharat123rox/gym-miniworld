# ssh poppy@flogo.local
# fuser -k /dev/ttyA*
# poppy-services --disable-camera --no-browser -vv --zmq poppy-ergo-jr
#
# python3 -m experiments.test_robot_control

import time
import random
import argparse
import zmq
import numpy as np
from gym_miniworld.envs import ergojr, BoxPos, RemoteBot
from .utils import *
from .pred_boxpos import Model

parser = argparse.ArgumentParser()
parser.add_argument("--noreach", action='store_true')
args = parser.parse_args()

ROBOT = "flogo.local"
PORT = 5757
context = zmq.Context()
socket = context.socket(zmq.PAIR)
print ("Connecting to server...")
socket.connect("tcp://{}:{}".format(ROBOT, PORT))
print('connected')

# Florian: for speed I'd recommend 100-200
# 300 is pretty fast and 50 is super slow
socket.send_json({"robot": {"set_max_speed": {"max_speed": 60}}})
socket.send_json({"robot": {"set_compliant": {"trueorfalse": False}}})

# Connect to the camera
env = RemoteBot(obs_width=80, obs_height=60)

env2 = BoxPos(domain_rand=False)
env2.reset()
env2.ergojr.draw_robot = False
env2.render('human')

model = Model()
model.load_state_dict(torch.load('pred_boxpos.torch'))
model.cuda()
model.eval()

if args.noreach:
    req = {"robot": {"set_pos": {"positions":[0,-85,90,0,-90,0]}}}
    socket.send_json(req)
    socket.recv_json()
    time.sleep(3)
    socket.send_json({"robot": {"set_compliant": {"trueorfalse": True}}})

while True:
    obs, _, _, _ = env.step(env.actions.done)
    obs = obs.transpose(2, 1, 0)
    obs = make_var(obs).unsqueeze(0)

    pos = model(obs)
    pos = pos.squeeze().detach().cpu().numpy()
    box_present = pos[4] > 0.5
    dir = pos[3]
    pos = pos[:3]

    if not box_present:
        pos = [-5, 0, 0]

    print(pos)
    env.render('human')

    env2.box.pos = pos
    env2.box.dir = dir
    env2.render('human')

    # Avoid hitting the table or trying to go through it
    pos[1] = max(0.03, pos[1])

    if args.noreach:
        continue

    if box_present:
        angles = ergojr.angles_near_pos(pos)
        angles[-1] = random.choice([20, -20])
    else:
        angles = [0,-85,90,0,-90,0]

    req = {"robot": {"set_pos": {"positions":angles}}}
    socket.send_json(req)
    answer = socket.recv_json()

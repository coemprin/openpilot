import sys
import time
import json
import socket
import threading
import time
from openpilot.common.params import Params
import threading
import numpy as np

from cereal import messaging
from openpilot.common.params import Params
from openpilot.common.realtime import Ratekeeper
from openpilot.system.hardware import HARDWARE


LX, LY, RX, RY, LT, RT = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
accelReceiver, steerReceiver = False, False
sensi = 0.1

def update_values(data):
    global LX, LY, RX, RY, LT, RT, accelReceiver, steerReceiver
    try:
        values = list(map(float, data.split()))
        if len(values) == 10:

            LX, LY, RX, RY, LT, RT, A, B, X, Y= values
            print(f"accel Manuelle = {accelReceiver}, steer Manuelle = {steerReceiver}")

            if A :
                accelReceiver = True
            if B :
                accelReceiver = False
            if X :
                steerReceiver = True
            if Y :
                steerReceiver = False
        else:
            print(f"Erreur : Données incorrectes reçues -> {data}")

    except (ValueError, KeyError) as e:
        print(f"Erreur de parsing : {e}")

#A -> active accel
#B -> desactive accel
#X -> active volant
#Y -> desactive volant

def send_thread():
  pm = messaging.PubMaster(['testJoystick'])

  rk = Ratekeeper(100, print_delay_threshold=None)

  while True:
    # if rk.frame % 20 == 0:
    #print("port_receiver : in send_thread accelReceiver = ", accelReceiver, "\n") # CA MARCHE

    joystick_msg = messaging.new_message('testJoystick')
    joystick_msg.valid = True
    # joystick_msg.testJoystick.axes = [joystick.axes_values[ax] for ax in joystick.axes_order]
    joystick_msg.testJoystick.accelReceiver = accelReceiver
    joystick_msg.testJoystick.steerReceiver = steerReceiver
    joystick_msg.testJoystick.lX = LX
    joystick_msg.testJoystick.lT = LT
    joystick_msg.testJoystick.rT = RT

    pm.send('testJoystick', joystick_msg)

    rk.keep_time()

def start_receiver():
    print("Receiver en attente de données...")
    try:
        #Start the thread
        threading.Thread(target=send_thread, daemon=True).start()

        while True:
            data = sys.stdin.readline().strip()
            if data == "STOP":
                print("Commande d'arrêt reçue, arrêt du receiver.")
                break
            update_values(data)
            time.sleep(0.01)
    except Exception as e:
        print(f"Erreur : {e}")

def main():
    start_receiver()

if __name__ == "__main__":
    start_receiver()


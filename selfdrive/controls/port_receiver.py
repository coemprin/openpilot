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

s = socket.socket()

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


def joystick_control_thread():

    #Setup the joystick
    global LX, LY, RX, RY, LT, RT, accelReceiver, steerReceiver, sensi

    print("Waiting for connection from controller...")
    s.bind(("localhost", 8002))
    s.listen(1)
    conn, _ = s.accept()
    print("Connected to the controller")

    #Params().put_bool('JoystickDebugMode', True)
    #Start the thread
    threading.Thread(target=send_thread, daemon=True).start()

    while True:
        line = conn.recv(4096)
        if not line:
            break
        try:
            data = json.loads(line)

            for i, button in enumerate(data["buttons"]):
                if i==0 and button == 1:
                    accelReceiver = True
                    #print(f"accelReceiver : {accelReceiver}")
                if i==1 and button == 1:
                    accelReceiver = False
                    #print(f"accelReceiver : {accelReceiver}")
                if i==2 and button == 1:
                    steerReceiver = True
                    #print(f"steerReceiver : {steerReceiver}")
                if i==3 and button == 1:
                    steerReceiver = False
                    #print(f"steerReceiver : {steerReceiver}")

            for i, axes in enumerate(data["axes"]):

                if i == 0 and abs(axes-LX) > sensi:
                    LX = axes
                    print(f"LX is pressed: {LX}")
                    '''
                if i == 1 and abs(axes-LY) > sensi:
                    LY = axes
                    print(f"LY is pressed: {LY}")
                if i == 2 and abs(axes-RX) > sensi:
                    RX = axes
                    print(f"RX is pressed: {RX}")
                if i == 3 and abs(axes-RY) > sensi:
                    RY = axes
                    print(f"RY is pressed: {RY}")
                    '''
                if i == 4 and abs(axes-LT) > sensi:
                    LT = axes
                    print(f"LT is pressed: {LT}")
                if i == 5 and abs(axes-RT) > sensi:
                    RT = axes
                    print(f"RT is pressed: {RT}")

        except json.JSONDecodeError:
            continue




def main():
  joystick_control_thread()

if __name__=="__main__":
    main()

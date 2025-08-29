#!/usr/bin/env python3
import os
import argparse
import threading
import numpy as np
from inputs import UnpluggedError, get_gamepad
import sys
import time
import socket

from cereal import messaging
from openpilot.common.params import Params
from openpilot.common.realtime import Ratekeeper
from openpilot.system.hardware import HARDWARE
from openpilot.tools.lib.kbhit import KBHit

EXPO = 0.4

LX, LY, RX, RY, LT, RT = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
accelReceiver, steerReceiver = False, False


class Keyboard:
  def __init__(self):
    self.kb = KBHit()
    self.axis_increment = 0.05  # 5% of full actuation each key press
    self.axes_map = {'w': 'gb', 's': 'gb',
                     'a': 'steer', 'd': 'steer'}
    self.axes_values = {'gb': 0., 'steer': 0.}
    self.axes_order = ['gb', 'steer']
    self.cancel = False

  def update(self):
    key = self.kb.getch().lower()
    self.cancel = False
    if key == 'r':
      self.axes_values = {ax: 0. for ax in self.axes_values}
    elif key == 'c':
      self.cancel = True
    elif key in self.axes_map:
      axis = self.axes_map[key]
      incr = self.axis_increment if key in ['w', 'a'] else -self.axis_increment
      self.axes_values[axis] = float(np.clip(self.axes_values[axis] + incr, -1, 1))
    else:
      return False
    return True


class Joystick:
  def __init__(self):
    # This class supports a PlayStation 5 DualSense controller on the comma 3X
    # TODO: find a way to get this from API or detect gamepad/PC, perhaps "inputs" doesn't support it
    self.cancel_button = 'BTN_NORTH'  # BTN_NORTH=X/triangle
    if HARDWARE.get_device_type() == 'pc':
      accel_axis = 'ABS_Z'
      steer_axis = 'ABS_RX'
      # TODO: once the longcontrol API is finalized, we can replace this with outputting gas/brake and steering
      self.flip_map = {'ABS_RZ': accel_axis}
    else:
      accel_axis = 'ABS_RX'
      steer_axis = 'ABS_Z'
      self.flip_map = {'ABS_RY': accel_axis}

    #self.min_axis_value = {accel_axis: 0., steer_axis: 0.}
    #self.max_axis_value = {accel_axis: 255., steer_axis: 255.}
    self.axes_values = {accel_axis: 0., steer_axis: 0.}
    self.axes_order = [accel_axis, steer_axis]
    self.cancel = False

  def update(self):

    global LX, LY, RX, RY, LT, RT, A, B, X, Y
    try:

      data = sys.stdin.readline().strip()
      if data == "STOP":
          print("Commande d'arrêt reçue, arrêt du receiver.")
    except Exception as e:
          print(f"\nUne erreur est survenue : {e}\n")

    try:
        values = list(map(float, data.split()))
        if len(values) == 10:
            LX, LY, RX, RY, LT, RT, A, B, X, Y= values

            print(f"Joystick_Control : RT - LT = {RT - LT}")

        else:
            print(f"Erreur : Données incorrectes reçues -> {data}")

    except (ValueError, KeyError) as e:
        print(f"Erreur de parsing : {e}")

    try:

      normAcc = float(np.interp(RT - LT,[-2,2],[-1,1]))
      normAcc = normAcc if abs(normAcc) > 0.03 else 0.  # center can be noisy, deadzone of 3%
      self.axes_values[joystick.axes_order[0]] = EXPO * normAcc ** 3 + (1 - EXPO) * normAcc  # less action near center for fine control

      normStee = -float(LX)  #joystick a gauche : LX = -1, joystick à droite LX = +1
      normStee = normStee if abs(normStee) > 0.03 else 0.  # center can be noisy, deadzone of 3%
      self.axes_values[joystick.axes_order[1]] = EXPO * normStee ** 3 + (1 - EXPO) * normStee  # less action near center for fine control
      print(f"accel = {self.axes_values[joystick.axes_order[0]]}, steer = {self.axes_values[joystick.axes_order[1]]}\n")

    except Exception as e:
          print(f"\nUne erreur est survenue : {e}\n")

    return True

def send_thread(joystick):  #Publie au reste du Comma
  pm = messaging.PubMaster(['testJoystick'])
  existing_file = True
  rk = Ratekeeper(100, print_delay_threshold=None)

  while True:
    if rk.frame % 20 == 0:
      print('\n' + ', '.join(f'{name}: {round(v, 3)}' for name, v in joystick.axes_values.items()))

    joystick_msg = messaging.new_message('testJoystick')
    joystick_msg.valid = True
    joystick_msg.testJoystick.axes = [joystick.axes_values[ax] for ax in joystick.axes_order]

    if existing_file:
      try:
        with open("/data/media/0/log_joy_ctrl.txt", 'a') as f:
          #f.write(f"Controlsd : AccelReceiver : {accelReceiver} and SteerReceiver {steerReceiver}\n")
          f.write(f"accel = {joystick.axes_values[joystick.axes_order[0]]}, steer = {joystick.axes_values[joystick.axes_order[1]]}\n")
          print(f"accel = {joystick.axes_values[joystick.axes_order[0]]}, steer = {joystick.axes_values[joystick.axes_order[1]]}\n")


      except FileNotFoundError:
          print("\nErreur : le fichier ou le dossier n'existe pas.\n")
          existing_file = False
      except PermissionError:
          print("\nErreur : permission refusée pour écrire dans ce fichier.\n")
          existing_file = False
      except Exception as e:
          print(f"\nUne erreur est survenue : {e}\n")
          existing_file = False

    pm.send('testJoystick', joystick_msg)

    rk.keep_time()


def joystick_control_thread(joystick):
  Params().put_bool('JoystickDebugMode', True)
  threading.Thread(target=send_thread, args=(joystick,), daemon=True).start()

  print("Debut joystick_control :\n")

  #creation de la socket
  s = socket.socket()
  s.bind(("localhost",12345))
  s.listen(1)

  conn, _ = s.accept()
  print("Connected to the computer")

  while True:

    joystick.update()
    time.sleep(0.01)





def main():
  joystick_control_thread(Joystick())


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Publishes events from your joystick to control your car.\n' +
                                               'openpilot must be offroad before starting joystick_control. This tool supports ' +
                                               'a PlayStation 5 DualSense controller on the comma 3X.',
                                   formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument('--keyboard', action='store_true', help='Use your keyboard instead of a joystick')
  args = parser.parse_args()

  if not Params().get_bool("IsOffroad") and "ZMQ" not in os.environ:
    print("The car must be off before running joystick_control.")
    exit()

  print()
  if args.keyboard:
    print('Gas/brake control: `W` and `S` keys')
    print('Steering control: `A` and `D` keys')
    print('Buttons')
    print('- `R`: Resets axes')
    print('- `C`: Cancel cruise control')
  else:
    print('Using joystick, make sure to run cereal/messaging/bridge on your device if running over the network!')
    print('If not running on a comma device, the mapping may need to be adjusted.')

  joystick = Keyboard() if args.keyboard else Joystick()
  joystick_control_thread(joystick)

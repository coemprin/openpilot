#!/usr/bin/env python3
import os
import argparse
import threading
import numpy as np
#from inputs import UnpluggedError, get_gamepad
import sys
import time

from cereal import messaging
from openpilot.common.params import Params
from openpilot.common.realtime import Ratekeeper
from openpilot.system.hardware import HARDWARE
from openpilot.tools.lib.kbhit import KBHit

EXPO = 0.4

accelToCar, steerToCar, speedToCar = 0.0, 0.0, 0.0
PORT = 12345
IP = "0.0.0.0"
conn = None
s = None
server_online = True
sm = None
pm = None


import socket


def receive_socket():
    global accelToCar, steerToCar, speedToCar
    global conn, s

    try :
      buffer = conn.recv(1024).decode()
      if not buffer :
        return False


      for line in buffer.strip().split('\n'):
          print("Serveur : reçu du client : ", line)

          try:
              data = dict(part.split('=') for part in line.split(','))
              accelToCar = float(data.get('accel', accelToCar))
              steerToCar = float(data.get('steer', steerToCar))
              speedToCar = float(data.get('speed', speedToCar))

              print("Acceleration:", accelToCar)
              print("Steer:", steerToCar)
              print("Vitesse:", speedToCar)

          except Exception as e:
              print("Erreur de parsing :", e)
              return False
    except Exception as e :
       print("Erreur de reception du message client :", e)
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

    global steerToCar, accelToCar
    global conn

    try:
        if not receive_socket() :
          print("\n--> Connection Perdu <--\n")
          conn.close()
          conn = None
          return False

    except Exception as e:
          print(f"\nUne erreur est survenue 1 : {e}\n")
          conn.close()
          conn = None
          return False

    try:
      self.axes_values[self.axes_order[0]] = float(accelToCar)
      self.axes_values[self.axes_order[1]] = float(steerToCar)
      print(f"Server: donnee envoyé à Joystick.py : accel = {self.axes_values[self.axes_order[0]]}, steer = {self.axes_values[self.axes_order[1]]}\n")

    except Exception as e:
          print(f"\nUne erreur est survenue 2 : {e}\n")

    return True

def publish_thread(joystick):
  global pm
  existing_file = True
  rk = Ratekeeper(100, print_delay_threshold=None)
  global conn

  while True:
    if not Params().get_bool('JoystickDebugMode') :
       Params().put_bool('JoystickDebugMode', True) #garder le joystick mode actif

    joystick_msg = messaging.new_message('testJoystick')
    joystick_msg.valid = True
    if (conn) :
       joystick_msg.testJoystick.axes = [joystick.axes_values[ax] for ax in joystick.axes_order]
    else :
       joystick_msg.testJoystick.axes = [0.0,0.0]

    if existing_file and conn:
      try:
        with open("/data/media/0/log_joy_ctrl.txt", 'a') as f:

          f.write(f"envoye a Joystick : accel = {joystick_msg.testJoystick.axes[0]}, steer = {joystick_msg.testJoystick.axes[1]}\n")

      except FileNotFoundError:
          print("\nErreur : le fichier ou le dossier n'existe pas.\n")
          existing_file = False
      except PermissionError:
          print("\nErreur : permission refusée pour écrire dans ce fichier.\n")
          existing_file = False
      except Exception as e:
          print(f"\nUne erreur est survenue 3 : {e}\n")
          existing_file = False

    pm.send('testJoystick', joystick_msg)

    rk.keep_time()


def sender_thread(): #envois les données au noeud ROS via socket


  global conn, sm
  speedEstimateToROS = 0.0
  steeringAngleDegToROS = 0.0
  speedRAWToROS = 0.0
  accelEstimateToROS = 0.0
  steerTorqueToROS = 0.0



  while True:

      try :
        sm.update(0)
        CS = sm['carState']
        speedEstimateToROS = CS.vEgo
        steeringAngleDegToROS = CS.steeringAngleDeg
        speedRAWToROS = CS.vEgoRaw
        accelEstimateToROS = CS.aEgo
        steerTorqueToROS = CS.steeringTorque
        #print(str(speedEstimateToROS) + " " + str(steeringAngleDegToROS))

      except Exception as e:
        print(f"\nUne erreur est survenue 4 : {e}\n")
        break

      #Envoi de Données
      data_to_send = f"speed={speedEstimateToROS:.4f},angle={steeringAngleDegToROS:.4f},\
                       rawspeed={speedRAWToROS:.4f},accel={accelEstimateToROS:.4f},\
                       torque={steerTorqueToROS :.4f}\n"
      #print("data envoye : " + data_to_send)


      try:
          if conn :
            conn.sendall(data_to_send.encode())
          else : break
      except (BrokenPipeError, ConnectionResetError) as e:
          print(f"Erreur d'envoi : {e}")
          break  # sortir de la boucle pour éviter de spammer

      time.sleep(0.02)  # Attend 20 milliseconde

   #recoit la vitesse et angle et le retourne à ROS via socket

def Connect() :
  global conn,s

  s.listen(1)
  print("Serveur en attente de connection...")

  conn, addr = s.accept()
  print(f"Connexion établie avec {addr}\n")

  if conn : return True
  else : return False

def run():
  global sm, pm, s

  sm = messaging.SubMaster(['carState'])
  pm = messaging.PubMaster(['testJoystick'])

  joystick = Joystick()
  Params().put_bool('JoystickDebugMode', True)

  s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  s.bind((IP, PORT))

  while (True):
    Connect()

    threading.Thread(target=publish_thread, args=(joystick,), daemon=True).start()
    threading.Thread(target=sender_thread, daemon=True).start()

    print("Debut joystick_control :\n")

    server_online = True
    while server_online:

      server_online = joystick.update()
      time.sleep(0.001) #time.sleep(0.01)




def main():

  run()


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

  run()

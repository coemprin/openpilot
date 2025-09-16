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
    '''Receive data from the client and update the variables''' #Is another thread is needed for this? I dont think so
    global accelToCar, steerToCar, speedToCar
    global conn, s

    try :
      buffer = conn.recv(1024).decode()
      if not buffer :
        return False


      for line in buffer.strip().split('\n'):
          print("joy_ctrl : receive_socket : received message :", line)

          try:
              data = dict(part.split('=') for part in line.split(','))
              accelToCar = float(data.get('accel', accelToCar))
              steerToCar = float(data.get('steer', steerToCar))
              speedToCar = float(data.get('speed', speedToCar))

              print("Accel:", accelToCar)
              print("Steer:", steerToCar)
              print("Speed:", speedToCar)

          except Exception as e:
              print("Parsing Error :", e)
              return False
    except Exception as e :
       print("Error while receiving message  :", e)
       return False


    return True



class Data:
  def __init__(self):
    self.accel = 0.
    self.steer = 0.

  def update(self):
    '''Update the variables'''

    global steerToCar, accelToCar
    global conn

    try:
        if not receive_socket() :
          print("\n--> Connection Lost <--\n")
          conn.close()
          conn = None
          return False

    except Exception as e:
          print(f"\nError while calling receive_socket() : {e}\n")
          conn.close()
          conn = None
          return False

    try:

      self.accel = float(accelToCar)
      self.steer = float(steerToCar)
      print(f"joy_ctrl: data sent to Joystick.py : accel = {self.accel}, steer = {self.steer}\n")

    except Exception as e:
          print(f"\nError while sending to Joystick.py : {e}\n")

    return True

def publish_thread(data):
  '''Publish the data on the topic JoystickdebugMode'''
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
       joystick_msg.testJoystick.accel = data.accel
       joystick_msg.testJoystick.steer = data.steer
    else :
       joystick_msg.testJoystick.accel = 0.0
       joystick_msg.testJoystick.steer = 0.0


    if existing_file and conn:
      try:
        with open("/data/media/0/log_joy_ctrl.txt", 'a') as f:

          f.write(f"Sent to Joystick : accel = {joystick_msg.testJoystick.accel}, steer = {joystick_msg.testJoystick.steer}\n")

      except FileNotFoundError:
          print("\nError : the file doesn't exist.\n")
          existing_file = False
      except PermissionError:
          print("\nError : Write access denied.\n")
          existing_file = False
      except Exception as e:
          print(f"\nError while writing logs : {e}\n")
          existing_file = False

    pm.send('testJoystick', joystick_msg)

    rk.keep_time()


def sender_thread():
  '''Gather Data from CarState and send it to the Client''' #Is another thread is needed for this? YES


  global conn, sm
  speedToNode, angleToNode = 0.0, 0.0

  while True:

      try :
        sm.update(0)
        CS = sm['carState']
        speedToNode = CS.vEgo
        angleToNode = CS.steeringAngleDeg
        #print(str(speedToNode) + " " + str(angleToNode))

      except Exception as e:
        print(f"\nError while gathering data from carState : {e}\n")
        break

      #Envoi de Données
      data_to_send = f"speed={speedToNode:.4f},angle={angleToNode:.4f}\n"
      #print("data envoye : " + data_to_send)


      try:
          if conn :
            conn.sendall(data_to_send.encode())
          else : break
      except (BrokenPipeError, ConnectionResetError) as e:
          print(f"Error while sending data to Client : {e}")
          break

      time.sleep(0.02)  # Wait 20 milliseconds


def Connect() :
  '''Connect to Client'''
  global conn,s

  s.listen(1)
  print("Server waiting for connection...")

  conn, addr = s.accept()
  print(f"Connection established with {addr}\n")

  if conn : return True
  else : return False

def run():
  '''Set up the socket server and the threads'''
  global sm, pm, s

  try :

    sm = messaging.SubMaster(['carState'])
    pm = messaging.PubMaster(['testJoystick'])

  except Exception as e:
        print(f"\nError while preparing sub and pub : {e}\n")
        return 0
  try :
    data = Data()
  except Exception as e:
        print(f"\nError while initialize Data : {e}\n")
        return 0

  #This next line is essential
  try:
    Params().put_bool('JoystickDebugMode', True)
  except Exception as e:
        print(f"\nError while enabling joystick mode : {e}\n")
        return 0

  try :

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((IP, PORT))

  except Exception as e:
        print(f"\nError while preparing socket and binding : {e}\n")
        return 0

  while (True):
    try :
      Connect()
    except Exception as e:
        print(f"\nError while connecting : {e}\n")
        return 0

    try:
      threading.Thread(target=publish_thread, args=(data,), daemon=True).start()
      threading.Thread(target=sender_thread, daemon=True).start()
      #threading.Thread(target=gather_thread, daemon=True).start()
    except Exception as e:
        print(f"\nError while launching threads : {e}\n")
        return 0

    print("Debut joystick_control :\n")

    server_online = True
    while server_online:

      server_online = data.update()
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

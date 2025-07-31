import os
import operator

from cereal import car
from openpilot.common.params import Params
from openpilot.system.hardware import PC, TICI
from openpilot.system.manager.process import PythonProcess, NativeProcess, DaemonProcess

WEBCAM = os.getenv("USE_WEBCAM") is not None

def driverview(started: bool, params: Params, CP: car.CarParams) -> bool:
  return started or params.get_bool("IsDriverViewEnabled")

def notcar(started: bool, params: Params, CP: car.CarParams) -> bool:
  return started and CP.notCar

def iscar(started: bool, params: Params, CP: car.CarParams) -> bool:
  return started and not CP.notCar

def logging(started: bool, params: Params, CP: car.CarParams) -> bool:
  run = (not CP.notCar) or not params.get_bool("DisableLogging")
  return started and run

def ublox_available() -> bool:
  return os.path.exists('/dev/ttyHS0') and not os.path.exists('/persist/comma/use-quectel-gps')

def ublox(started: bool, params: Params, CP: car.CarParams) -> bool:
  use_ublox = ublox_available()
  if use_ublox != params.get_bool("UbloxAvailable"):
    params.put_bool("UbloxAvailable", use_ublox)
  return started and use_ublox

def joystick(started: bool, params: Params, CP: car.CarParams) -> bool:
  return started and params.get_bool("JoystickDebugMode")

def not_joystick(started: bool, params: Params, CP: car.CarParams) -> bool:
  return started and not params.get_bool("JoystickDebugMode")

def long_maneuver(started: bool, params: Params, CP: car.CarParams) -> bool:
  return started and params.get_bool("LongitudinalManeuverMode")

def not_long_maneuver(started: bool, params: Params, CP: car.CarParams) -> bool:
  return started and not params.get_bool("LongitudinalManeuverMode")

def qcomgps(started: bool, params: Params, CP: car.CarParams) -> bool:
  return started and not ublox_available()

def always_run(started: bool, params: Params, CP: car.CarParams) -> bool:
  return True

def only_onroad(started: bool, params: Params, CP: car.CarParams) -> bool:
  return started

def only_offroad(started: bool, params: Params, CP: car.CarParams) -> bool:
  return not started

def or_(*fns):
  return lambda *args: operator.or_(*(fn(*args) for fn in fns))

def and_(*fns):
  return lambda *args: operator.and_(*(fn(*args) for fn in fns))

procs = [
  DaemonProcess("manage_athenad", "system.athena.manage_athenad", "AthenadPid"), #gère des appel API avec connect.comma.ai

  NativeProcess("loggerd", "system/loggerd", ["./loggerd"], logging),
  NativeProcess("encoderd", "system/loggerd", ["./encoderd"], only_onroad),
  NativeProcess("stream_encoderd", "system/loggerd", ["./encoderd", "--stream"], notcar),
  PythonProcess("logmessaged", "system.logmessaged", always_run),

  #NativeProcess("camerad", "system/camerad", ["./camerad"], driverview, enabled=not WEBCAM), #manage road camera and driver camera
  #PythonProcess("webcamerad", "tools.webcam.camerad", driverview, enabled=WEBCAM),
  NativeProcess("logcatd", "system/logcatd", ["./logcatd"], only_onroad), #LOG
  NativeProcess("proclogd", "system/proclogd", ["./proclogd"], only_onroad), #LOG
  #PythonProcess("micd", "system.micd", iscar), #manage microphone
  PythonProcess("timed", "system.timed", always_run, enabled=not PC), #synchronize the time

  # TODO Make python process once TG allows opening QCOM from child proc
  #NativeProcess("dmonitoringmodeld", "selfdrive/modeld", ["./dmonitoringmodeld"], driverview, enabled=(WEBCAM or not PC)), #check if the driver is aware
  # TODO Make python process once TG allows opening QCOM from child proc
  NativeProcess("modeld", "selfdrive/modeld", ["./modeld"], only_onroad), #predict how to drive
  NativeProcess("sensord", "system/sensord", ["./sensord"], only_onroad, enabled=not PC), #configure and read the sensors
  NativeProcess("ui", "selfdrive/ui", ["./ui"], always_run, watchdog_max_dt=(5 if not PC else None)), #UI (enlever le guide utilisateur?)
  #PythonProcess("soundd", "selfdrive.ui.soundd", only_onroad), #sound alert
  PythonProcess("locationd", "selfdrive.locationd.locationd", only_onroad), #location of car : deduct SPEED, ...
  NativeProcess("_pandad", "selfdrive/pandad", ["./pandad"], always_run, enabled=False),
  PythonProcess("calibrationd", "selfdrive.locationd.calibrationd", only_onroad), #this is useful for the neuronal prediction
  PythonProcess("torqued", "selfdrive.locationd.torqued", only_onroad), #adjust parameters of lateral control
  #PythonProcess("controlsd", "selfdrive.controls.controlsd", and_(not_joystick, iscar)), #control the car from planning of plannerd
  PythonProcess("joystickd", "tools.joystick.joystickd", or_(joystick, notcar)),
  PythonProcess("selfdrived", "selfdrive.selfdrived.selfdrived", only_onroad), # ???
  PythonProcess("card", "selfdrive.car.card", only_onroad), #manage comunication with vehicle through CAN BUS
  PythonProcess("deleter", "system.loggerd.deleter", always_run), #LOG
  PythonProcess("dmonitoringd", "selfdrive.monitoring.dmonitoringd", driverview, enabled=(WEBCAM or not PC)), # logic : check if the driver need to retake control
  PythonProcess("qcomgpsd", "system.qcomgpsd.qcomgpsd", qcomgps, enabled=TICI), #manage the collect of GPS datas
  PythonProcess("pandad", "selfdrive.pandad.pandad", always_run),
  PythonProcess("paramsd", "selfdrive.locationd.paramsd", only_onroad), #car parameters
  NativeProcess("ubloxd", "system/ubloxd", ["./ubloxd"], ublox, enabled=TICI), #analyse GNSS data : location
  PythonProcess("pigeond", "system.ubloxd.pigeond", ublox, enabled=TICI), #manage GNSS Ublox
  PythonProcess("plannerd", "selfdrive.controls.plannerd", not_long_maneuver), #planning of lateral and longitudinal control from the neuronal prediction
  #PythonProcess("maneuversd", "tools.longitudinal_maneuvers.maneuversd", long_maneuver), #manage longitudinal control
  PythonProcess("radard", "selfdrive.controls.radard", only_onroad), #gather data from different radars
  PythonProcess("hardwared", "system.hardware.hardwared", always_run), #manage material aspects
  PythonProcess("tombstoned", "system.tombstoned", always_run, enabled=not PC),
  PythonProcess("updated", "system.updated.updated", only_offroad, enabled=not PC),
  PythonProcess("uploader", "system.loggerd.uploader", always_run), #LOG
  PythonProcess("statsd", "system.statsd", always_run),

  # debug procs
  NativeProcess("bridge", "cereal/messaging", ["./bridge"], notcar),
  PythonProcess("webrtcd", "system.webrtc.webrtcd", notcar),
  #PythonProcess("webjoystick", "tools.bodyteleop.web", notcar),
  #PythonProcess("joystick", "tools.joystick.joystick_control", and_(joystick, iscar)), #I launched this manually on mode offroad
]

managed_processes = {p.name: p for p in procs}

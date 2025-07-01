import sys
import time


LX, LY, RX, RY, LT, RT = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
accelReceiver, steerReceiver = 0, 0

def update_values(data):
    global LX, LY, RX, RY, LT, RT, accelReceiver, steerReceiver
    try:
        values = list(map(float, data.split()))
        if len(values) == 10:
            LX, LY, RX, RY, LT, RT, A, B, X, Y= values
            #print(f"Mis à jour : LX={LX}, LY={LY}, RX={RX}, RY={RY}, LT={LT}, RT={RT}")

            if A :
                accelReceiver = 1
            if B :
                accelReceiver = 0
            if X :
                steerReceiver = 1
            if Y :
                steerReceiver = 0
        else:
            print(f"Erreur : Données incorrectes reçues -> {data}")

    except (ValueError, KeyError) as e:
        print(f"Erreur de parsing : {e}")

def start_receiver():
    print("Receiver en attente de données...")
    try:
        while True:
            data = sys.stdin.readline().strip()
            if data == "STOP":
                print("Commande d'arrêt reçue, arrêt du receiver.")
                break
            update_values(data)
            time.sleep(0.01)
    except Exception as e:
        print(f"Erreur : {e}")

if __name__ == "__main__":
    start_receiver()

#A -> active accel
#B -> desactive accel
#X -> active volant
#Y -> desactive volant



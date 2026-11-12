#! /usr/bin/env python3
"""
PicassoBot - Script 1: Stift übernehmen

Zwei Modi (Schalter PEN_FROM_HAND unten):

  PEN_FROM_HAND = True, HANDOVER_AT = 'grundstellung':
    Senkrechte Grundstellung, Greifer auf, Stift einsetzen, Enter, Greifer zu.

  PEN_FROM_HAND = True, HANDOVER_AT = 'zeichnung':
    1. Über die Mitte der Zeichnung fahren, Greifer zeigt nach unten
    2. Als Letztes gerade runter auf die Zeichenhöhe (DRAW_DZ)
    3. Greifer öffnen
    4. Stift SENKRECHT zwischen die Finger stellen, Spitze AUF dem Papier, Enter
    5. Greifer schliessen, hoch auf die Warteposition
    -> Der Stift steckt so automatisch immer gleich tief und wird danach
       nicht mehr gedreht (kein Umkippen im Greifer).

  PEN_FROM_HAND = False -> Roboter holt den Stift aus dem Halter (Standard):
    1. Grundstellung
    2. Greifer öffnen
    3. Vorposition PEN_PRE_JOINTS_DEG (Elbow 57.2 Grad, über dem Stift)
    4. NUR der Elbow dreht auf 90 Grad -> Greifer senkt sich senkrecht auf den Stift
    5. Greifer schliessen
    6. NUR der Elbow zurück -> Stift wird nach oben gezogen

Starten (real_robot.launch muss laufen, Papier liegt am Platz):
    cd /root/catkin_ws/src/ur-lab/src
    python3 01_grab_pen.py
    python3 01_grab_pen.py --dry-run     # nur Befehle anzeigen
Danach direkt:  python3 02_zeichnen.py
"""

import argparse
import sys
from math import radians

import picasso_config as cfg
from picasso_robot import PicassoRobot

# ====================================================================== #
# EINSTELLUNGEN
# ====================================================================== #

# True  = Mensch reicht den Stift
# False = Roboter holt den Stift selbst aus dem Halter (PEN_GRAB_...)
PEN_FROM_HAND = False

# Wo der Mensch den Stift übergibt (nur für PEN_FROM_HAND = True):
#   'grundstellung' = senkrechte Grundstellung (HANDOVER_JOINTS_DEG unten)
#   'zeichnung'     = über der Zeichnung, Greifer nach unten, Spitze auf dem Papier
HANDOVER_AT = 'grundstellung'

# Stellung für die Übergabe in der Grundstellung (Grad).
# [0, -90, 0, -90, 0, 0]: Arm senkrecht, Greifer zeigt waagrecht zum Zuschauer.
# Tipp: [0, -90, 0, 0, 0, 0] (Wrist 1 = 0) -> Greifer zeigt senkrecht nach UNTEN,
#       der Stift wird danach beim Zeichnen nicht mehr gedreht und kippt weniger.
HANDOVER_JOINTS_DEG = [0, -90, 0, -90, 0, 0]

# Greifer: 0 = ganz offen, 255 = ganz zu
GRIPPER_OPEN = 0
GRIPPER_CLOSED = 255        # Greifer stoppt von selbst, sobald er den Stift berührt
GRIPPER_FORCE = 150         # 0-255. Höher = Stift rutscht weniger (vorher 80 -> kippte)

# Geschwindigkeiten (am Anfang langsam lassen!)
SPEED_TRAVEL = 0.2          # rad/s für movej-Fahrten
SPEED_APPROACH = 0.02       # m/s für das letzte Stück nach unten

# --- nur für PEN_FROM_HAND = False ------------------------------------ #
# Manuell am Pendant angefahren (05.11.2026), Gelenkwinkel in GRAD.
# Die beiden Stellungen unterscheiden sich NUR im Elbow: so senkt sich der
# Greifer als letzte Bewegung fast senkrecht auf den Stift und kippt ihn nicht.
PEN_PRE_JOINTS_DEG = [0, -90, 57.2, -90, -90, 0]   # Vorposition, ca. 17 cm über dem Stift
PEN_GRAB_JOINTS_DEG = [0, -90, 90, -90, -90, 0]    # offener Greifer umschliesst Stift
SPEED_ELBOW = 0.1           # rad/s für die letzte Elbow-Bewegung (33 Grad in ~6 s)

# ====================================================================== #


def _ask(prompt, dry_run):
    if dry_run:
        print(prompt + ' [Dry-Run: übersprungen]')
        return ''
    return input(prompt)


def _over_drawing(robot, dz, linear, v):
    """Fährt über die Mitte der Zeichnung, dz Meter über dem Nullpunkt."""
    robot.move_joints_offset(cfg.NULLPUNKT_JOINTS, dx=cfg.DRAW_SHIFT[0], dy=cfg.DRAW_SHIFT[1],
                             dz=dz, linear=linear, v=v)


def pen_at_home(robot):
    """Übergabe in der Grundstellung: Greifer auf, Mensch setzt Stift ein, Greifer zu."""
    print('1/3 Grundstellung')
    robot.move_joints([radians(a) for a in HANDOVER_JOINTS_DEG], v=SPEED_TRAVEL)

    while True:
        print('2/3 Greifer öffnen')
        robot.set_gripper(GRIPPER_OPEN)

        _ask('    Stift zwischen die Finger halten (immer gleich tief, z. B. bis zur '
             'Klebeband-Markierung), Hand weg, dann Enter ...', robot.dry_run)

        print('3/3 Greifer schliessen')
        status = robot.set_gripper(GRIPPER_CLOSED, force=GRIPPER_FORCE)
        if status == 2 or robot.dry_run:
            print('    Stift gegriffen. Merci!')
            return status

        print('    Kein Stift erkannt (Status {}).'.format(status))
        if _ask('    Nochmal versuchen? [J/n] ', robot.dry_run).strip().lower() == 'n':
            return status


def pen_over_drawing(robot):
    """Übergabe über dem Papier: Greifer zeigt nach unten, Stift steht auf dem Papier."""
    if cfg.DRAW_DZ is None:
        sys.exit('DRAW_DZ in picasso_config.py fehlt (Höhe der Finger über dem Papier, '
                 'z. B. 0.05).')
    wait_dz = cfg.DRAW_DZ + cfg.WAIT_LIFT

    print('1/5 Über die Mitte der Zeichnung fahren')
    _over_drawing(robot, wait_dz, linear=False, v=SPEED_TRAVEL)

    print('2/5 Greifer öffnen')
    robot.set_gripper(GRIPPER_OPEN)

    print('3/5 Gerade runter auf Zeichenhöhe')
    _over_drawing(robot, cfg.DRAW_DZ, linear=True, v=SPEED_APPROACH)

    while True:
        _ask('4/5 Stift SENKRECHT zwischen die Finger stellen, Spitze AUF dem Papier, '
             'Hand weg, dann Enter ...', robot.dry_run)

        print('5/5 Greifer schliessen')
        status = robot.set_gripper(GRIPPER_CLOSED, force=GRIPPER_FORCE)
        if status == 2 or robot.dry_run:
            print('    Stift gegriffen. Merci!')
            break

        print('    Kein Stift erkannt (Status {}).'.format(status))
        robot.set_gripper(GRIPPER_OPEN)
        if _ask('    Nochmal versuchen? [J/n] ', robot.dry_run).strip().lower() == 'n':
            return status

    print('    Hoch auf die Warteposition - bereit für 02_zeichnen.py')
    _over_drawing(robot, wait_dz, linear=True, v=SPEED_APPROACH)
    return status


def grab_pen(robot, home):
    """Stift aus dem Halter holen - wie am Pendant manuell erprobt:
    Vorposition anfahren, dann als LETZTE Bewegung nur den Elbow drehen.
    Dabei senkt sich der Greifer fast senkrecht auf den Stift und richtet
    sich gleichzeitig senkrecht auf, so kippt der Stift nicht um."""
    pre = [radians(a) for a in PEN_PRE_JOINTS_DEG]
    grab = [radians(a) for a in PEN_GRAB_JOINTS_DEG]

    print('1/6 Grundstellung')
    robot.move_joints(home, v=SPEED_TRAVEL)

    print('2/6 Greifer öffnen')
    robot.set_gripper(GRIPPER_OPEN)

    print('3/6 Vorposition über dem Stift (Elbow {:.1f} Grad)'.format(PEN_PRE_JOINTS_DEG[2]))
    robot.move_joints(pre, v=SPEED_TRAVEL)

    print('4/6 Nur Elbow: runter auf den Stift (Elbow {:.1f} Grad)'.format(PEN_GRAB_JOINTS_DEG[2]))
    robot.move_joints(grab, a=0.3, v=SPEED_ELBOW)

    while True:
        _ask('    Stift sitzt zwischen den Fingern? (bei Bedarf von Hand zurechtrücken, '
             'Hand weg) Enter = greifen ...', robot.dry_run)

        print('5/6 Greifer schliessen')
        status = robot.set_gripper(GRIPPER_CLOSED, force=GRIPPER_FORCE)
        if status == 2 or robot.dry_run:
            print('    Stift gegriffen.')
            break

        print('    Kein Stift erkannt (Status {}).'.format(status))
        robot.set_gripper(GRIPPER_OPEN)
        if _ask('    Nochmal versuchen? [J/n] ', robot.dry_run).strip().lower() == 'n':
            break

    print('6/6 Nur Elbow: wieder hoch in die Vorposition')
    robot.move_joints(pre, a=0.3, v=SPEED_ELBOW)
    return status


def main():
    parser = argparse.ArgumentParser(description='PicassoBot: Stift übernehmen')
    parser.add_argument('--ip', help='Roboter-IP (überschreibt den ROS-Parameter robot_ip)')
    parser.add_argument('--dry-run', action='store_true', help='Befehle nur anzeigen')
    try:
        import rospy
        argv = rospy.myargv()[1:]  # ROS-Remappings (name:=wert) ignorieren
    except ImportError:
        argv = sys.argv[1:]
    args = parser.parse_args(argv)

    with PicassoRobot(robot_ip=args.ip, dry_run=args.dry_run, node_name='grab_pen') as robot:
        if PEN_FROM_HAND and HANDOVER_AT == 'zeichnung':
            pen_over_drawing(robot)
        elif PEN_FROM_HAND:
            pen_at_home(robot)
        else:
            grab_pen(robot, cfg.HOME_JOINTS)


if __name__ == '__main__':
    main()
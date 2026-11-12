#! /usr/bin/env python3
"""
PicassoBot - gemeinsame Basisklasse für alle Scripts.

Baut auf move_real_robot.py auf und ergänzt:
  - Bewegung im Gelenkraum (movej) UND zu kartesischen Posen (movel / movej p[...])
  - Warten, bis eine Bewegung fertig ist (über /joint_states)
  - Greifer-Steuerung mit Rückmeldung (Robotiq, Port 63352)
  - Mehrere Bewegungen als ein URScript-Programm senden (für das Zeichnen)
  - Dry-Run-Modus: druckt nur die Befehle, ohne Roboter und ohne ROS

Einheiten (wie in URScript):
  - Positionen x, y, z in METERN       (Teach Pendant zeigt mm an -> /1000 rechnen!)
  - Rotationen rx, ry, rz in RADIANT   (Rotationsvektor, wie auf dem Pendant)
  - Gelenkwinkel in RADIANT
"""

import socket
import time

try:
    import rospy
    from sensor_msgs.msg import JointState
    ROS_AVAILABLE = True
except ImportError:  # z. B. auf dem Laptop für einen Dry-Run
    ROS_AVAILABLE = False


class PicassoRobot:

    PORT_UR = 30002
    PORT_GRIPPER = 63352

    def __init__(self, robot_ip=None, dry_run=False, node_name='picasso_robot', use_gripper=True):
        """use_gripper=False: Greifer wird nicht angesprochen (z. B. beim Zeichnen,
        damit ein gegriffener Stift nicht herunterfällt)."""
        self.dry_run = dry_run
        self._joints = None
        self.socket_ur = None
        self.socket_gripper = None

        if self.dry_run:
            print('[DRY-RUN] Keine Verbindung zum Roboter, Befehle werden nur ausgegeben.')
            return

        if not ROS_AVAILABLE:
            raise RuntimeError('rospy nicht gefunden. Im ROS-Container starten oder --dry-run verwenden.')

        rospy.init_node(node_name)
        host = robot_ip or rospy.get_param('robot_ip')
        rospy.loginfo('Verbinde mit Roboter %s ...', host)

        # Gelenkzustände mithören, damit wir wissen, wann eine Bewegung fertig ist
        topic = rospy.get_param('~joint_states_topic', '/joint_states')
        rospy.Subscriber(topic, JointState, self._joint_state_callback)

        self.socket_ur = socket.create_connection((host, self.PORT_UR), timeout=5)
        if use_gripper:
            self.socket_gripper = socket.create_connection((host, self.PORT_GRIPPER), timeout=5)
            self._activate_gripper()
        time.sleep(0.5)  # kurz warten, damit erste /joint_states ankommen

    # ------------------------------------------------------------------ #
    # Grundlagen
    # ------------------------------------------------------------------ #

    def _joint_state_callback(self, msg):
        self._joints = list(msg.position)

    def _log(self, text):
        if self.dry_run or not ROS_AVAILABLE:
            print(text)
        else:
            rospy.loginfo(text)

    def send_urscript(self, script):
        """Schickt einen URScript-Befehl oder ein ganzes Programm an den Roboter.
        Achtung: Ein neuer Befehl bricht eine laufende Bewegung ab!"""
        if not script.endswith('\n'):
            script += '\n'
        if self.dry_run:
            print('[URScript] ' + script.rstrip())
            return
        self.socket_ur.sendall(script.encode())

    @staticmethod
    def _fmt(values):
        return ', '.join('{:.5f}'.format(float(v)) for v in values)

    # ------------------------------------------------------------------ #
    # Bewegung
    # ------------------------------------------------------------------ #

    def move_joints(self, joints, a=0.5, v=0.3, wait=True):
        """Fährt im Gelenkraum zu den 6 Gelenkwinkeln (rad)."""
        self.send_urscript('movej([{}], a={}, v={})'.format(self._fmt(joints), a, v))
        if wait:
            self.wait_until_stopped()

    def move_pose(self, pose, a=0.3, v=0.05, linear=True, wait=True):
        """Fährt zur TCP-Pose [x, y, z, rx, ry, rz] (m, rad).
        linear=True  -> movel: gerade Linie (für kurze, präzise Wege, z. B. runter zum Stift)
        linear=False -> movej: schnellster Weg in Gelenken (für grosse Wege, Bahn nicht gerade!)"""
        cmd = 'movel' if linear else 'movej'
        self.send_urscript('{}(p[{}], a={}, v={})'.format(cmd, self._fmt(pose), a, v))
        if wait:
            self.wait_until_stopped()

    def move_joints_offset(self, joints, dz=0.0, a=0.3, v=0.05, linear=True, wait=True, dx=0.0, dy=0.0):
        """Fährt zu der TCP-Pose, die zu den Gelenkwinkeln 'joints' (rad) gehört,
        verschoben um dx, dy, dz Meter (Basis-Koordinaten). Die Umrechnung macht der
        Roboter selbst mit get_forward_kin - man muss keine Pose am Pendant ablesen."""
        q = '[{}]'.format(self._fmt(joints))
        target = 'pose_add(get_forward_kin({}), p[{:.5f}, {:.5f}, {:.5f}, 0, 0, 0])'.format(q, dx, dy, dz)
        if linear:
            self.send_urscript('movel({}, a={}, v={})'.format(target, a, v))
        else:
            # Gelenkstellung nahe der angegebenen wählen (qnear), damit der Arm
            # gleich "gefaltet" ankommt wie beim Teachen am Pendant
            self.send_urscript('movej(get_inverse_kin({}, {}), a={}, v={})'.format(target, q, a, v))
        if wait:
            self.wait_until_stopped()

    @staticmethod
    def offset_pose(pose, dx=0.0, dy=0.0, dz=0.0):
        """Gibt eine Kopie der Pose zurück, verschoben im Basis-Koordinatensystem (m)."""
        p = list(pose)
        p[0] += dx
        p[1] += dy
        p[2] += dz
        return p

    def run_program(self, lines, name='picasso_prog', wait=True, timeout=120.0, settle=1.0):
        """Schickt mehrere URScript-Zeilen als EIN Programm.
        So laufen viele Bewegungen nacheinander, ohne sich gegenseitig abzubrechen.
        settle: so lange muss der Arm stillstehen, bis das Programm als fertig gilt.
        Muss länger sein als jede Pause (sleep) im Programm!
        Rückgabe: True = bewegt und fertig, None = hat sich gar nicht bewegt
        (z. B. Fehler/Popup auf dem Pendant), False = Timeout."""
        body = '\n'.join('  ' + line for line in lines)
        self.send_urscript('def {}():\n{}\nend\n'.format(name, body))
        if wait:
            # längere Wartezeiten: Programm muss erst übersetzt werden, und an
            # Ecken steht der Arm kurz still - das darf nicht als "fertig" gelten
            return self.wait_until_stopped(timeout=timeout, start_timeout=5.0, settle=settle)
        return True

    def stop(self, deceleration=1.0):
        """Bremst die aktuelle Bewegung ab (z. B. wenn das richtige Wort fällt)."""
        self.send_urscript('stopl({})'.format(deceleration))

    def wait_until_stopped(self, timeout=30.0, start_timeout=1.0, tolerance=2e-4, settle=0.4):
        """Wartet, bis sich der Roboter bewegt hat und wieder still steht.
        Nutzt /joint_states. Kommen keine Daten an, wird eine feste Zeit gewartet.
        Rückgabe: True = bewegt und fertig, None = keine Bewegung, False = Timeout/unbekannt."""
        if self.dry_run:
            return True
        if self._joints is None:
            rospy.logwarn('Keine /joint_states empfangen - warte pauschal 3 s.')
            time.sleep(3.0)
            return False

        def max_diff(a, b):
            return max(abs(x - y) for x, y in zip(a, b))

        # 1) Warten, bis die Bewegung beginnt (sonst sind wir evtl. schon am Ziel)
        reference = list(self._joints)
        t0 = time.monotonic()
        while time.monotonic() - t0 < start_timeout and not rospy.is_shutdown():
            if max_diff(self._joints, reference) > tolerance:
                break
            time.sleep(0.02)
        else:
            return None  # hat sich nicht bewegt -> schon am Ziel oder Fehler

        # 2) Warten, bis die Gelenke für 'settle' Sekunden ruhig sind
        last = list(self._joints)
        still_since = time.monotonic()
        while time.monotonic() - t0 < timeout and not rospy.is_shutdown():
            time.sleep(0.05)
            current = list(self._joints)
            if max_diff(current, last) > tolerance:
                last = current
                still_since = time.monotonic()
            elif time.monotonic() - still_since >= settle:
                return True

        rospy.logwarn('Timeout: Roboter nach %.0f s noch nicht still.', timeout)
        return False

    # ------------------------------------------------------------------ #
    # Greifer (Robotiq über URCap-Socket, Port 63352)
    # ------------------------------------------------------------------ #

    def _gripper_cmd(self, cmd):
        """Schickt einen Befehl an den Greifer und gibt die Antwort zurück."""
        if self.dry_run:
            print('[Greifer] ' + cmd)
            return 'ack'
        self.socket_gripper.sendall((cmd + '\n').encode())
        try:
            return self.socket_gripper.recv(1024).decode().strip()
        except socket.timeout:
            return ''

    def _gripper_get(self, var):
        """Liest einen Greifer-Wert, z. B. 'OBJ' -> int."""
        answer = self._gripper_cmd('GET ' + var)  # Antwort z. B. "OBJ 2"
        try:
            return int(answer.split()[-1])
        except (ValueError, IndexError):
            return -1

    def _activate_gripper(self, timeout=5.0):
        """Aktiviert den Greifer NUR, wenn er noch nicht aktiv ist.
        Eine erneute Aktivierung öffnet den Greifer - ein gehaltener Stift fiele herunter."""
        if self._gripper_get('STA') == 3:   # STA 3 = bereits aktiviert
            return
        self._gripper_cmd('SET ACT 1')
        t0 = time.monotonic()
        while self._gripper_get('STA') != 3 and time.monotonic() - t0 < timeout:
            time.sleep(0.1)
        self._gripper_cmd('SET GTO 1')

    def set_gripper(self, position, speed=150, force=80, wait=True, timeout=5.0):
        """position: 0 = ganz offen, 255 = ganz zu.
        Rückgabe (OBJ-Status): 2 = Objekt beim Schliessen gegriffen,
        3 = Position erreicht ohne Objekt, 1 = beim Öffnen blockiert, -1 = unbekannt."""
        position = max(0, min(255, int(position)))
        self._gripper_cmd('SET SPE {}'.format(int(speed)))
        self._gripper_cmd('SET FOR {}'.format(int(force)))
        self._gripper_cmd('SET POS {}'.format(position))
        self._gripper_cmd('SET GTO 1')
        if not wait or self.dry_run:
            return -1

        time.sleep(0.2)  # Greifer Zeit geben loszufahren
        t0 = time.monotonic()
        obj = self._gripper_get('OBJ')
        while obj == 0 and time.monotonic() - t0 < timeout:  # 0 = fährt noch
            time.sleep(0.05)
            obj = self._gripper_get('OBJ')
        return obj

    def open_gripper(self, **kwargs):
        return self.set_gripper(0, **kwargs)

    # ------------------------------------------------------------------ #
    # Aufräumen
    # ------------------------------------------------------------------ #

    def close(self):
        for s in (self.socket_ur, self.socket_gripper):
            if s is not None:
                s.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
#! /usr/bin/env python3
"""
PicassoBot - Script 2: Am Nullpunkt warten, Form eingeben, zeichnen, Geste

Voraussetzung: Stift ist im Greifer (Script 1), real_robot.launch läuft.

Ablauf:
  1. Grundstellung -> über den Nullpunkt (Warteposition)
  2. Form im Terminal auswählen (Nummer oder Name, q = beenden)
  3. Roboter prüft, ob alle Punkte erreichbar sind, und zeichnet
  4. Italienische Geste Richtung Zuschauer (-Y)
  5. Zurück zur Warteposition -> nächste Form

Die Zeichnung (DRAW_SIZE, Standard 8 x 8 cm) liegt mittig auf dem Nullpunkt,
verschiebbar mit DRAW_SHIFT in picasso_config.py.

Starten:
    cd /root/catkin_ws/src/ur-lab/src
    python3 02_zeichnen.py --hoehe      # EINMALIG: Zeichenhöhe mit Stift bestimmen
    python3 02_zeichnen.py              # zeichnen
    python3 02_zeichnen.py --dry-run    # nur URScript anzeigen
    python3 02_zeichnen.py --list       # Formen auflisten
    python3 02_zeichnen.py --karte      # Wort vom Laptop empfangen (karte_lesen.py), Tastatur geht weiterhin
"""

import argparse
import math
import sys

import picasso_config as cfg
import shapes
from picasso_robot import PicassoRobot

HOEHE_START = 0.08      # Kalibrierung beginnt so hoch über dem Nullpunkt (m)
HOEHE_MAX_STEP = 20     # grösster erlaubter Schritt in mm


def _fmt(*values):
    return ', '.join('{:.5f}'.format(v) for v in values)


def _q():
    return '[{}]'.format(_fmt(*cfg.NULLPUNKT_JOINTS))


def to_offset(x, y):
    """Formkoordinate (0..100) -> Verschiebung (m) relativ zum Nullpunkt."""
    dx = cfg.DRAW_SHIFT[0] + (x - 50.0) / 100.0 * cfg.DRAW_SIZE
    dy = cfg.DRAW_SHIFT[1] + (y - 50.0) / 100.0 * cfg.DRAW_SIZE
    return dx, dy


def pose_expr(dx, dy, dz):
    return 'pose_add(base, p[{}, 0, 0, 0])'.format(_fmt(dx, dy, dz))


# ---------------------------------------------------------------------- #
# Reichweite im Voraus prüfen (in Python, bevor der Roboter etwas bekommt)
# ---------------------------------------------------------------------- #

def ur3e_flange_xy(joints):
    """Vorwärtskinematik UR3e (DH-Parameter von Universal Robots).
    Liefert x, y des Flansches in Basis-Koordinaten (m) - dieselben Werte,
    die das Pendant unter Tool Position anzeigt."""
    d = [0.15185, 0, 0, 0.13105, 0.08535, 0.0921]
    a = [0, -0.24355, -0.2132, 0, 0, 0]
    alpha = [math.pi / 2, 0, 0, math.pi / 2, -math.pi / 2, 0]
    T = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    for i in range(6):
        ct, st = math.cos(joints[i]), math.sin(joints[i])
        ca, sa = math.cos(alpha[i]), math.sin(alpha[i])
        A = [[ct, -st * ca, st * sa, a[i] * ct],
             [st, ct * ca, -ct * sa, a[i] * st],
             [0, sa, ca, d[i]],
             [0, 0, 0, 1]]
        T = [[sum(T[r][k] * A[k][c] for k in range(4)) for c in range(4)] for r in range(4)]
    return T[0][3], T[1][3]


NULL_X, NULL_Y = ur3e_flange_xy(cfg.NULLPUNKT_JOINTS)


def radius_of(dx, dy):
    return math.hypot(NULL_X + dx, NULL_Y + dy)


def check_reach(strokes, shift=None):
    """Gibt (min_radius, max_radius) aller Punkte zurück (m)."""
    shift = shift or cfg.DRAW_SHIFT
    radii = []
    for s in strokes:
        for x, y in s:
            dx = shift[0] + (x - 50.0) / 100.0 * cfg.DRAW_SIZE
            dy = shift[1] + (y - 50.0) / 100.0 * cfg.DRAW_SIZE
            radii.append(radius_of(dx, dy))
    return min(radii), max(radii)


def fits(strokes, shift=None):
    r_min, r_max = check_reach(strokes, shift)
    return (r_max <= cfg.REACH_MAX_RADIUS - cfg.REACH_MARGIN and
            r_min >= cfg.REACH_MIN_RADIUS + cfg.REACH_MARGIN)


def suggest_shift(strokes):
    """Sucht die kleinste Verschiebung Richtung Sockel (+Y, 5-mm-Schritte), bei der es passt."""
    for step in range(0, 41):
        shift = (cfg.DRAW_SHIFT[0], cfg.DRAW_SHIFT[1] + step * 0.005)
        if fits(strokes, shift):
            return shift
    return None


def reach_report(name, strokes):
    """True wenn die Form passt, sonst Meldung ausgeben und False."""
    r_min, r_max = check_reach(strokes)
    if fits(strokes):
        return True
    limit_max = cfg.REACH_MAX_RADIUS - cfg.REACH_MARGIN
    limit_min = cfg.REACH_MIN_RADIUS + cfg.REACH_MARGIN
    print('  "{}" liegt ausserhalb des Arbeitsbereichs:'.format(name))
    if r_max > limit_max:
        print('    weitester Punkt {:.0f} mm vom Sockel, erlaubt {:.0f} mm ({:.0f} mm zu weit)'
              .format(r_max * 1000, limit_max * 1000, (r_max - limit_max) * 1000))
    if r_min < limit_min:
        print('    nächster Punkt {:.0f} mm vom Sockel, erlaubt ab {:.0f} mm'
              .format(r_min * 1000, limit_min * 1000))
    shift = suggest_shift(strokes)
    if shift:
        print('    Passt mit:  DRAW_SHIFT = ({:.3f}, {:.3f})  in picasso_config.py'.format(*shift))
    else:
        print('    DRAW_SIZE verkleinern - eine Verschiebung allein reicht nicht.')
    return False


def field_report():
    """Prüft das ganze Zeichenfeld (alle Formen liegen darin)."""
    field = [[(0, 0), (100, 0), (100, 100), (0, 100)]]
    r_min, r_max = check_reach(field)
    print('Zeichenfeld {:.0f} x {:.0f} mm, Abstand zum Sockel {:.0f}-{:.0f} mm '
          '(erlaubt {:.0f}-{:.0f} mm)'.format(cfg.DRAW_SIZE * 1000, cfg.DRAW_SIZE * 1000,
                                             r_min * 1000, r_max * 1000,
                                             (cfg.REACH_MIN_RADIUS + cfg.REACH_MARGIN) * 1000,
                                             (cfg.REACH_MAX_RADIUS - cfg.REACH_MARGIN) * 1000))
    if not fits(field):
        print('  Achtung: Ecken des Feldes liegen ausserhalb - grosse Formen werden abgelehnt.')
        shift = suggest_shift(field)
        if shift:
            print('  Ganzes Feld passt mit:  DRAW_SHIFT = ({:.3f}, {:.3f})'.format(*shift))


def stroke_pause():
    """(an/aus, Sekunden) aus picasso_config.py. Fehlen die Werte dort: keine Pause."""
    return (bool(getattr(cfg, 'STROKE_PAUSE', False)),
            float(getattr(cfg, 'STROKE_PAUSE_SEC', 2.0)))


def build_draw_program(groups, draw_dz):
    """Baut ein URScript-Programm: zuerst Reichweite aller Punkte prüfen,
    dann alle Striche zeichnen, zum Schluss zurück zur Warteposition.
    groups = Bausteine (Liste von Strich-Listen, siehe shapes.groups);
    mit STROKE_PAUSE wird zwischen den Bausteinen pausiert."""
    strokes = [s for g in groups for s in g]
    z_down = draw_dz - cfg.PEN_PRESS
    z_lift = draw_dz + cfg.PEN_LIFT
    z_wait = draw_dz + cfg.WAIT_LIFT

    points = [to_offset(x, y) for s in strokes for x, y in s]
    lines = ['base = get_forward_kin({})'.format(_q())]

    # 1) Reichweiten-Check: nichts bewegen, wenn ein Punkt nicht erreichbar ist.
    #    Die Meldung nennt den ersten Punkt, der nicht geht (in mm relativ zum Nullpunkt).
    checked = set()
    for dx, dy in points:
        for z in (z_down, z_lift):
            key = (round(dx, 4), round(dy, 4), round(z, 4))
            if key in checked:
                continue
            checked.add(key)
            lines += ['if not is_within_safety_limits({}):'.format(pose_expr(dx, dy, z)),
                      '  popup("Nicht erreichbar: x={:+.0f} y={:+.0f} z={:+.0f} mm ab Nullpunkt. '
                      'DRAW_SHIFT dy erhoehen oder DRAW_DZ pruefen.", "PicassoBot", False, True)'
                      .format(dx * 1000, dy * 1000, z * 1000),
                      '  halt',
                      'end']

    # 2) Zeichnen (optional mit Pause nach jedem Baustein, Stift dabei angehoben)
    a_draw = 0.3
    pause_on, pause_s = stroke_pause()
    for gi, group in enumerate(groups):
        if pause_on and gi > 0:
            lines.append('sleep({})'.format(pause_s))   # Publikum darf raten
        for stroke in group:
            lines += _stroke_lines(stroke, z_down, z_lift, a_draw)

    # 3) Zurück zur Warteposition
    lines.append('movel({}, a=0.5, v={})'.format(pose_expr(*cfg.DRAW_SHIFT, z_wait), cfg.SPEED_PEN_UP))
    return lines


def _stroke_lines(stroke, z_down, z_lift, a_draw):
    """Ein Strich: anheben, hinfahren, absetzen, zeichnen, anheben."""
    pts = [to_offset(x, y) for x, y in stroke]
    sx, sy = pts[0]
    ex, ey = pts[-1]
    lines = ['movel({}, a=0.5, v={})'.format(pose_expr(sx, sy, z_lift), cfg.SPEED_PEN_UP),
             'movel({}, a={}, v={})'.format(pose_expr(sx, sy, z_down), a_draw, cfg.SPEED_APPROACH)]
    for dx, dy in pts[1:]:
        lines.append('movel({}, a={}, v={})'.format(pose_expr(dx, dy, z_down), a_draw, cfg.SPEED_DRAW))
    lines.append('movel({}, a=0.5, v={})'.format(pose_expr(ex, ey, z_lift), cfg.SPEED_APPROACH))
    return lines


def build_gesture_program():
    """Italienische Geste: Greifer kippt Richtung Zuschauer und nickt hoch/runter.
    Nur Wrist 1 bewegt sich, darum gibt es keine Reichweitenprobleme."""
    point = cfg.GESTURE_POINT_DEG
    nod = cfg.GESTURE_NOD_DEG
    v, a = cfg.GESTURE_SPEED, 2.0
    lines = ['q = get_actual_joint_positions()']

    def wrist1(deg_offset):
        return ('movej([q[0], q[1], q[2], q[3] + d2r({}), q[4], q[5]], a={}, v={})'
                .format(deg_offset, a, v))

    lines.append(wrist1(point))
    for _ in range(cfg.GESTURE_REPEAT):
        lines.append(wrist1(point - nod))   # Schnabel hoch
        lines.append(wrist1(point + nod))   # Schnabel runter
    lines.append(wrist1(point))
    lines.append('movej(q, a={}, v={})'.format(a, v))  # zurück
    return lines


def choose_shape():
    names = sorted(shapes.SHAPES)
    print('\nWas soll PicassoBot zeichnen?')
    for i, name in enumerate(names, 1):
        print('  {:2d}) {}'.format(i, name))
    print('   q) beenden')
    while True:
        answer = input('Nummer oder Name: ').strip().lower()
        if answer in ('q', 'quit', 'exit'):
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(names):
            return names[int(answer) - 1]
        if answer in shapes.SHAPES:
            return answer
        print('  Unbekannt, bitte nochmal.')


class KartenEmpfang:
    """Wartet gleichzeitig auf ein Wort vom Laptop (karte_lesen.py, per TCP)
    und auf die Tastatur. Was zuerst kommt, gewinnt.
    Protokoll: Laptop schickt 'wort\\n', Roboter antwortet 'OK wort' oder 'ERR text'."""

    def __init__(self, port):
        import socket
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(('0.0.0.0', port))   # Container hat network_mode: host
        self.server.listen(1)

    def close(self):
        self.server.close()

    def wait(self):
        import select
        names = sorted(shapes.SHAPES)
        print('\nWarte auf Karte vom Laptop (Port {}) ... oder hier eintippen:'.format(self.port))
        print('  ' + ', '.join(names))
        print('  q = beenden')
        quellen = [self.server, sys.stdin]
        while True:
            print('Karte / Name / Nummer: ', end='', flush=True)
            ready, _, _ = select.select(quellen, [], [])
            if sys.stdin in ready:                                   # Tastatur
                zeile = sys.stdin.readline()
                if zeile == '':                  # keine Tastatur (z. B. im Hintergrund gestartet)
                    quellen = [self.server]
                    continue
                answer = zeile.strip().lower()
                if answer in ('q', 'quit', 'exit'):
                    return None
                if answer.isdigit() and 1 <= int(answer) <= len(names):
                    return names[int(answer) - 1]
                if answer in shapes.SHAPES:
                    return answer
                print('  Unbekannt, bitte nochmal.')
                continue

            conn, addr = self.server.accept()                        # Laptop
            conn.settimeout(5.0)
            try:
                word = conn.recv(256).decode('utf-8', 'replace').strip().lower()
                if word in shapes.SHAPES:
                    conn.sendall('OK {}\n'.format(word).encode())
                    print('\nKarte vom Laptop ({}): {}'.format(addr[0], word))
                    return word
                conn.sendall('ERR unbekannte Form: {}\n'.format(word).encode())
                print('\n  Laptop schickte unbekanntes Wort "{}" - ignoriert.'.format(word))
            except OSError as e:
                print('\n  Verbindung zum Laptop fehlgeschlagen: {}'.format(e))
            finally:
                conn.close()


def go_to_wait(robot, draw_dz):
    print('Fahre zur Warteposition über dem Nullpunkt ...')
    robot.move_joints(cfg.HOME_JOINTS, v=cfg.SPEED_TRAVEL)
    robot.move_joints_offset(cfg.NULLPUNKT_JOINTS, dx=cfg.DRAW_SHIFT[0], dy=cfg.DRAW_SHIFT[1],
                             dz=draw_dz + cfg.WAIT_LIFT, linear=False, v=cfg.SPEED_TRAVEL)


def draw_loop(robot, draw_dz, preset=None, karte=None):
    field_report()
    go_to_wait(robot, draw_dz)
    while True:
        name = preset or (karte.wait() if karte else choose_shape())
        preset = None
        if name is None:
            break
        strokes = shapes.get(name)
        if not reach_report(name, strokes):
            if robot.dry_run:
                break
            continue
        length_m = shapes.stroke_length(strokes) / 100.0 * cfg.DRAW_SIZE
        print('Zeichne "{}" ({} Striche, ca. {:.0f} cm Linie) ...'.format(
            name, len(strokes), length_m * 100))

        pause_on, pause_s = stroke_pause()
        settle = pause_s + 1.0 if pause_on else 1.0   # Pause darf nicht als "fertig" gelten
        result = robot.run_program(build_draw_program(shapes.groups(name), draw_dz), name='zeichne',
                                   timeout=600, settle=settle)
        if result is None:
            print('  Roboter hat sich nicht bewegt. Meldung auf dem Pendant prüfen '
                  '(z. B. "nicht erreichbar" -> DRAW_SHIFT anpassen).')
            continue
        if result is False:
            print('  Zeichnen dauerte zu lange oder wurde gestoppt - Pendant prüfen.')
            continue

        print('Voilà! Geste ...')
        robot.run_program(build_gesture_program(), name='geste', timeout=60)

        if robot.dry_run:
            break

    print('Zurück in die Grundstellung.')
    robot.move_joints(cfg.HOME_JOINTS, v=cfg.SPEED_TRAVEL)


def calibrate_height(robot):
    """Stiftspitze schrittweise absenken, bis sie das Papier berührt."""
    print('Höhen-Kalibrierung')
    print('  Stift muss im Greifer sein, Papier unter dem Nullpunkt.')
    print('  Der Roboter fährt {:.0f} cm über den Nullpunkt.'.format(HOEHE_START * 100))
    if not robot.dry_run:
        input('  Enter = losfahren (Ctrl+C = abbrechen) ')

    dz = HOEHE_START
    robot.move_joints(cfg.HOME_JOINTS, v=cfg.SPEED_TRAVEL)
    robot.move_joints_offset(cfg.NULLPUNKT_JOINTS, dz=dz, linear=False, v=cfg.SPEED_TRAVEL)
    if robot.dry_run:
        return

    print('\nEingabe in mm nach UNTEN (z. B. 10, 5, 1), negativ = nach oben, ok = Spitze berührt Papier')
    while True:
        answer = input('  Höhe {:+.1f} mm über Nullpunkt > '.format(dz * 1000)).strip().lower()
        if answer == 'ok':
            break
        try:
            step = float(answer.replace(',', '.'))
        except ValueError:
            print('  Zahl oder ok eingeben.')
            continue
        if abs(step) > HOEHE_MAX_STEP:
            print('  Maximal {} mm pro Schritt.'.format(HOEHE_MAX_STEP))
            continue
        dz -= step / 1000.0
        robot.move_joints_offset(cfg.NULLPUNKT_JOINTS, dz=dz, linear=True, v=cfg.SPEED_APPROACH)

    robot.move_joints_offset(cfg.NULLPUNKT_JOINTS, dz=dz + cfg.WAIT_LIFT, linear=True,
                             v=cfg.SPEED_APPROACH)
    print('\nIn picasso_config.py eintragen:\n')
    print('    DRAW_DZ = {:.4f}\n'.format(dz))


def main():
    parser = argparse.ArgumentParser(description='PicassoBot: zeichnen')
    parser.add_argument('shape', nargs='?', help='Form direkt angeben (sonst Auswahl)')
    parser.add_argument('--hoehe', action='store_true', help='Zeichenhöhe mit Stift bestimmen')
    parser.add_argument('--ip', help='Roboter-IP (überschreibt ROS-Parameter robot_ip)')
    parser.add_argument('--dry-run', action='store_true', help='Befehle nur anzeigen')
    parser.add_argument('--list', action='store_true', help='Formen auflisten')
    parser.add_argument('--karte', nargs='?', const=5005, type=int, metavar='PORT',
                        help='Wort vom Laptop (karte_lesen.py) empfangen, Standard-Port 5005')
    try:
        import rospy
        argv = rospy.myargv()[1:]
    except ImportError:
        argv = sys.argv[1:]
    args = parser.parse_args(argv)

    if args.list:
        field_report()
        for name in sorted(shapes.SHAPES):
            r_min, r_max = check_reach(shapes.get(name))
            print('  {:14s} {:3.0f}-{:3.0f} mm  {}'.format(
                name, r_min * 1000, r_max * 1000, 'ok' if fits(shapes.get(name)) else 'ZU WEIT'))
        return
    if args.shape and args.shape.lower() not in shapes.SHAPES:
        sys.exit('Unbekannte Form. Verfügbar: ' + ', '.join(sorted(shapes.SHAPES)))

    draw_dz = cfg.DRAW_DZ
    if draw_dz is None and not args.hoehe:
        if args.dry_run:
            draw_dz = 0.03
        else:
            sys.exit('Zuerst die Zeichenhöhe bestimmen:  python3 02_zeichnen.py --hoehe\n'
                     'und den Wert als DRAW_DZ in picasso_config.py eintragen.')

    # use_gripper=False: Greifer nicht ansprechen, sonst öffnet er sich und der Stift fällt
    with PicassoRobot(robot_ip=args.ip, dry_run=args.dry_run, node_name='zeichnen',
                      use_gripper=False) as robot:
        if args.hoehe:
            calibrate_height(robot)
        else:
            karte = KartenEmpfang(args.karte) if args.karte else None
            try:
                draw_loop(robot, draw_dz, preset=args.shape and args.shape.lower(), karte=karte)
            finally:
                if karte:
                    karte.close()


if __name__ == '__main__':
    main()
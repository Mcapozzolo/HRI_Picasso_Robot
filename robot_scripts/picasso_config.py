"""
PicassoBot - gemeinsame Konfiguration für alle Scripts.

Einheiten: Positionen/Verschiebungen in METERN, Gelenkwinkel hier in GRAD
(radians() rechnet sie um, wie d2r() in URScript).
"""

from math import radians

# ---------------------------------------------------------------------- #
# Stellungen (Gelenkwinkel: Base, Shoulder, Elbow, Wrist 1, Wrist 2, Wrist 3)
# ---------------------------------------------------------------------- #

# Grundstellung: Arm senkrecht, entspricht movej([0, d2r(-90), 0, d2r(-90), 0, 0])
HOME_JOINTS = [radians(a) for a in [0, -90, 0, -90, 0, 0]]

# Nullpunkt (manuell am Pendant angefahren, ohne Stift, Greifer zeigt nach unten)
NULLPUNKT_JOINTS = [radians(a) for a in [69.89, -56.84, 61.77, -94.33, -87.84, 160]]

# ---------------------------------------------------------------------- #
# Zeichnen (alle Höhen relativ zum Nullpunkt, + = höher)
#
# Achsen von der Zuschauerseite (-Y) aus gesehen:
#   +X = nach rechts,  +Y = vom Zuschauer weg (zum Sockel),  +Z = nach oben
# ---------------------------------------------------------------------- #

# Höhe, auf der die STIFTSPITZE das Papier berührt, relativ zum Nullpunkt.
# Mit  python3 02_zeichnen.py --hoehe  bestimmen und hier eintragen.
DRAW_DZ = 0.053

# Grösse des quadratischen Zeichenfelds
DRAW_SIZE = 0.08

# Mitte der Zeichnung relativ zum Nullpunkt (dx, dy).
# Der Nullpunkt liegt nah an der Reichweitengrenze. Falls der Roboter
# "Reichweite" meldet: dy erhöhen (z. B. 0.06 = 6 cm Richtung Sockel).
DRAW_SHIFT = (0.0, 0.07)

# Arbeitsbereich: Abstand der Stiftspitze von der Sockelachse (waagrecht).
# Gemessen am 05.11.2026: maximal 435 mm (Elbow ~19 Grad, 12 cm über Nullpunkt).
# Das Script prüft jede Form vorher und fährt nicht los, wenn ein Punkt ausserhalb liegt.
REACH_MAX_RADIUS = 0.435
REACH_MIN_RADIUS = 0.20     # nicht zu nah an den Sockel (Kollision mit dem eigenen Arm)
REACH_MARGIN = 0.005        # Sicherheitsabstand zur gemessenen Grenze

PEN_PRESS = 0.001   # so tief unter die Berührhöhe drücken, damit der Stift sicher malt
PEN_LIFT = 0.01     # Stift zwischen den Strichen anheben
WAIT_LIFT = 0.04    # Warteposition: so hoch über dem Papier

# Pause nach jedem Strich (z. B. Smiley: Kopf - Pause - Auge - Pause - Auge - Pause - Mund),
# damit das Publikum Zeit zum Raten hat. Zum Testen auf False lassen.
STROKE_PAUSE = True
STROKE_PAUSE_SEC = 1.0   # Dauer der Pause in Sekunden

# ---------------------------------------------------------------------- #
# Geschwindigkeiten
# ---------------------------------------------------------------------- #
SPEED_TRAVEL = 0.3      # rad/s  grosse Fahrten (movej)
SPEED_APPROACH = 0.02   # m/s    Stift absetzen / Höhe einstellen
SPEED_PEN_UP = 0.05     # m/s    Stift angehoben zum nächsten Strich
SPEED_DRAW = 0.03       # m/s    beim Zeichnen (langsam = "PicassoBot denkt nach")

# ---------------------------------------------------------------------- #
# Italienische Geste nach der Zeichnung ("Schnabel" zum Zuschauer, -Y)
# Wrist 1 kippt den Greifer: negativ = Richtung Zuschauer
# ---------------------------------------------------------------------- #
GESTURE_POINT_DEG = -80   # Greifer zeigt fast waagrecht zum Zuschauer
GESTURE_NOD_DEG = 20      # so weit hoch/runter nicken
GESTURE_REPEAT = 2
GESTURE_SPEED = 1.0       # rad/s
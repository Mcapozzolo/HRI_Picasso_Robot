"""
PicassoBot - Formen-Bibliothek.

Jede Form ist eine Liste von Strichen. Ein Strich ist eine Liste von Punkten (x, y),
die ohne Absetzen gezeichnet werden. Zwischen Strichen wird der Stift angehoben.

Koordinaten: 0..100 in beide Richtungen, (0, 0) = unten links, y zeigt nach oben.
Die Form wird später automatisch auf das Zeichenfeld skaliert (8 x 8 cm -> 1 Einheit = 0.8 mm).

Bausteine (für STROKE_PAUSE in picasso_config.py):
  - Enthält eine Form KEIN PAUSE, kommt nach jedem Strich eine Pause.
  - Enthält sie PAUSE-Einträge, wird nur dort pausiert. Alles zwischen zwei PAUSE
    ist ein Baustein und wird am Stück gezeichnet (z. B. alle Giftpunkte des Pilzes).
  Die Reihenfolge ist bewusst gewählt: zuerst der mehrdeutige Teil, das verräterische
  Detail zuletzt - so hat das Publikum etwas zu raten.

Vorschau aller Formen mit der Breite eures Stifts (Standard 3 mm):
    python3 shapes.py          ->  shapes_preview.png   (braucht matplotlib)
    python3 shapes.py 4        ->  mit 4 mm Stift
"""

import math

PAUSE = 'PAUSE'   # Marker zwischen Bausteinen


# ---------------------------------------------------------------------- #
# Bausteine zum Konstruieren
# ---------------------------------------------------------------------- #

def circle(cx, cy, r, n=36):
    """Geschlossener Kreis aus n Segmenten."""
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
            for i in range(n + 1)]


def dot(cx, cy, r=2.0):
    """Kleiner Punkt - mit dem dicken Stift wird daraus ein ausgefüllter Tupfen."""
    return circle(cx, cy, r, n=10)


def ellipse(cx, cy, rx, ry, n=36, rot_deg=0):
    c, s = math.cos(math.radians(rot_deg)), math.sin(math.radians(rot_deg))
    pts = []
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        pts.append((cx + x * c - y * s, cy + x * s + y * c))
    return pts


def arc(cx, cy, r, start_deg, end_deg, n=16):
    return [(cx + r * math.cos(math.radians(start_deg + (end_deg - start_deg) * i / n)),
             cy + r * math.sin(math.radians(start_deg + (end_deg - start_deg) * i / n)))
            for i in range(n + 1)]


def bezier(p0, p1, p2, p3, n=16):
    """Kubische Bezier-Kurve von p0 nach p3 (p1, p2 = Kontrollpunkte)."""
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        pts.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return pts


def wave(x0, x1, y, amp, periods, n=40):
    """Waagrechte Wellenlinie."""
    return [(x0 + (x1 - x0) * i / n, y + amp * math.sin(2 * math.pi * periods * i / n))
            for i in range(n + 1)]


def closed(points):
    return list(points) + [points[0]]


def mirror(stroke):
    """Spiegelt einen Strich an der senkrechten Mittellinie x = 50."""
    return [(100 - x, y) for x, y in stroke]


def star_points(cx, cy, r_out, r_in, n=5):
    pts = []
    for i in range(2 * n):
        r = r_out if i % 2 == 0 else r_in
        a = math.pi / 2 + i * math.pi / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return closed(pts)


# ---------------------------------------------------------------------- #
# Ursprüngliche Formen
# ---------------------------------------------------------------------- #

def _sun():
    rays = []
    for i in range(8):
        a = 2 * math.pi * i / 8
        rays.append([(50 + 26 * math.cos(a), 50 + 26 * math.sin(a)),
                     (50 + 42 * math.cos(a), 50 + 42 * math.sin(a))])
    return [circle(50, 50, 18), PAUSE] + rays          # Strahlen = ein Baustein


def _star():
    return [star_points(50, 48, 46, 19)]


def _heart(n=40, cx=50, cy=55, s=2.7):
    pts = []
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * s, cy + y * s))
    return [pts]


def _flower():
    petals = [circle(50 + 16 * math.cos(math.radians(a)), 62 + 16 * math.sin(math.radians(a)), 9, n=20)
              for a in range(90, 450, 60)]
    return ([[(50, 0), (50, 45)], PAUSE,              # Stiel
             [(50, 18), (36, 30), (50, 26)], PAUSE,   # Blatt
             circle(50, 62, 7, n=20), PAUSE]          # Mitte
            + petals)                                 # alle Blätter = ein Baustein


# ---------------------------------------------------------------------- #
# Neue Formen (mit Details)
# ---------------------------------------------------------------------- #

def _eiffelturm():
    left = [(10, 0), (24, 22), (33, 42), (39, 60), (44, 78), (47, 90), (50, 99)]
    outline = left + [(100 - x, y) for x, y in reversed(left[:-1])]
    return [
        arc(50, 0, 19, 180, 0),                          # Bogen zwischen den Beinen
        PAUSE,
        [(20, 24), (80, 24)],                            # 1. Plattform
        PAUSE,
        outline,                                         # Umriss
        PAUSE,
        [(31, 46), (69, 46)],                            # 2. Plattform
        [(27, 26), (61, 44)], [(73, 26), (39, 44)],      # Gitter unten
        [(36, 48), (56, 72)], [(64, 48), (44, 72)],      # Gitter oben
        PAUSE,
        [(41, 76), (59, 76)],                            # 3. Plattform
        [(50, 99), (50, 100)],                           # Antenne
    ]


def _croissant():
    outer = arc(50, 34, 42, 195, -15, n=24)
    inner = arc(50, 34, 18, -20, 200, n=16)
    body = outer + [(96, 14)] + inner + [(4, 14), outer[0]]
    segments = [[(50 + 19 * math.cos(math.radians(a)), 34 + 19 * math.sin(math.radians(a))),
                 (50 + 41 * math.cos(math.radians(a)), 34 + 41 * math.sin(math.radians(a)))]
                for a in (150, 118, 90, 62, 30)]
    return [body, PAUSE] + segments


def _baguette():
    rot = 32
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))

    def local(x, y):   # Koordinaten entlang der Brotachse -> Formkoordinaten
        return (50 + x * c - y * s, 50 + x * s + y * c)

    cuts = [[local(t - 5, -6), local(t + 7, 6)] for t in (-30, -15, 0, 15, 30)]
    return [ellipse(50, 50, 50, 13, n=40, rot_deg=rot), PAUSE] + cuts


def _weinglas():
    bowl = [(23, 96)] + arc(50, 78, 28, 180, 360, n=20) + [(77, 96)]
    return [
        bowl,                                            # Kelch
        PAUSE,
        [(50, 50), (50, 12)],                            # Stiel
        PAUSE,
        ellipse(50, 9, 20, 4, n=24),                     # Fuss
        PAUSE,
        [(23, 74), (77, 74)],                            # Weinspiegel
        [(31, 66), (40, 70)],                            # Lichtreflex
        PAUSE,
        ellipse(50, 96, 27, 3.5, n=24),                  # Rand
    ]


def _schnecke():
    spiral = []
    turns, r_max, n = 2.4, 27.0, 90
    for i in range(n + 1):
        t = i / n
        a = 2 * math.pi * turns * t
        spiral.append((42 + r_max * t * math.cos(a), 46 + r_max * t * math.sin(a)))
    body = ([(4, 17), (72, 17)] + bezier((72, 17), (86, 17), (92, 26), (90, 38))
            + bezier((90, 38), (88, 46), (76, 44), (70, 34)))
    return [
        spiral,                                          # Haus (mehrdeutig!)
        PAUSE,
        body,                                            # Körper
        PAUSE,
        [(84, 42), (78, 62)], dot(78, 64, 2.5),          # Fühler
        [(88, 42), (94, 60)], dot(94, 62, 2.5),
        dot(83, 34, 1.5),                                # Auge
    ]


def _gluehbirne():
    glass = [(39, 26), (37, 38)] + arc(50, 60, 26, 240, -60, n=30) + [(63, 38), (61, 26)]
    rays = [[(50 + 31 * math.cos(math.radians(a)), 60 + 31 * math.sin(math.radians(a))),
             (50 + 39 * math.cos(math.radians(a)), 60 + 39 * math.sin(math.radians(a)))]
            for a in (20, 55, 90, 125, 160)]
    return [
        glass,                                           # Glaskolben (wie ein Kreis)
        PAUSE,
        [(38, 26), (62, 26)], [(39, 19), (61, 19)],      # Gewinde
        [(40, 12), (60, 12)], [(45, 5), (55, 5)],
        PAUSE,
        [(45, 26), (45, 50), (47, 56), (50, 50), (53, 56), (55, 50), (55, 26)],  # Glühdraht
        PAUSE,
    ] + rays                                             # Leuchten


def _fliegenpilz():
    cap = arc(50, 44, 44, 180, 0, n=28) + bezier((94, 44), (70, 36), (30, 36), (6, 44))
    stem = [(38, 39), (35, 9)] + bezier((35, 9), (36, 3), (64, 3), (65, 9)) + [(62, 39)]
    dots = [circle(x, y, r, n=14) for x, y, r in
            [(26, 56, 5), (44, 70, 5.5), (62, 74, 4.5), (76, 58, 5), (52, 54, 4), (34, 78, 3.5)]]
    return [
        cap,                                             # Hut (Hügel? Schirm?)
        PAUSE,
        stem,                                            # Stiel
        PAUSE,
    ] + dots + [                                         # Giftpunkte = ein Baustein
        PAUSE,
        bezier((36, 27), (44, 22), (56, 22), (64, 27)),  # Ring am Stiel
        dot(20, 4, 1.5), [(10, 3), (90, 3)],             # Boden
    ]


def _eis():
    A, B, C = (30, 56), (70, 56), (50, 2)
    grid = []
    for t in (1 / 3, 2 / 3):
        grid.append([(A[0] + t * (B[0] - A[0]), A[1]), (C[0] + t * (B[0] - C[0]), C[1] + t * (B[1] - C[1]))])
        grid.append([(B[0] + t * (A[0] - B[0]), B[1]), (C[0] + t * (A[0] - C[0]), C[1] + t * (A[1] - C[1]))])
    scoop = (arc(50, 66, 23, -5, 185, n=24)
             + [(26, 62), (30, 57), (34, 61), (38, 55), (43, 60), (48, 54), (53, 60),
                (58, 54), (63, 60), (68, 55), (72, 61), (74, 62)])
    return [
        closed([A, B, C]),                               # Waffel (Dreieck)
        PAUSE,
    ] + grid + [                                         # Waffelmuster
        PAUSE,
        scoop,                                           # Kugel mit Tropfkante
        PAUSE,
        circle(50, 93, 4, n=16), [(50, 97), (55, 100)],  # Kirsche
        PAUSE,
        dot(40, 74, 1.2), dot(58, 78, 1.2), dot(48, 70, 1.2),   # Streusel
    ]


def _regenschirm():
    canopy = arc(50, 52, 44, 180, 0, n=30)
    scallops = arc(78, 52, 14, 0, 180, n=10) + arc(50, 52, 14, 0, 180, n=10)[1:] + arc(22, 52, 14, 0, 180, n=10)[1:]
    return [
        canopy,                                          # Bogen (Regenbogen? Hügel?)
        PAUSE,
        scallops,                                        # Bögen unten
        PAUSE,
        [(50, 96), (36, 52)], [(50, 96), (64, 52)],      # Speichen
        PAUSE,
        [(50, 96), (50, 13)] + arc(42, 13, 8, 0, -180, n=10),   # Griff mit Haken
        PAUSE,
        [(10, 36), (7, 28)], [(88, 38), (85, 30)], [(18, 22), (15, 14)], [(82, 22), (79, 14)],  # Regen
    ]


def _rakete():
    body = ([(38, 26), (38, 64)] + bezier((38, 64), (38, 82), (46, 92), (50, 98))
            + bezier((50, 98), (54, 92), (62, 82), (62, 64)) + [(62, 26), (38, 26)])
    return [
        body,                                            # Rumpf mit Spitze
        PAUSE,
        [(38, 42), (24, 24), (24, 12), (38, 26)],         # Flossen
        mirror([(38, 42), (24, 24), (24, 12), (38, 26)]),
        PAUSE,
        circle(50, 58, 7, n=20),                         # Fenster
        PAUSE,
        [(38, 74), (62, 74)],                            # Spitze abgesetzt
        PAUSE,
        [(42, 24), (44, 12), (47, 18), (50, 4), (53, 18), (56, 12), (58, 24)],   # Flamme
    ]


def _apfel():
    body = ([(50, 68)] + arc(35, 44, 28, 72, 290, n=22) + [(50, 15)]
            + arc(65, 44, 28, 250, 468, n=22) + [(50, 68)])
    leaf = bezier((53, 80), (58, 94), (74, 96), (80, 90)) + bezier((80, 90), (74, 80), (60, 78), (53, 80))
    return [
        body,                                            # Apfel (oder Herz? Po?)
        PAUSE,
        bezier((50, 66), (50, 74), (51, 80), (54, 88)),  # Stiel
        PAUSE,
        leaf,                                            # Blatt
        [(55, 81), (76, 90)],                            # Blattader
        PAUSE,
        arc(36, 46, 17, 115, 165, n=8),                  # Glanzlicht
    ]


def _schneemann():
    return [
        circle(50, 17, 16),                              # unten
        PAUSE,
        circle(50, 45, 12),                              # Mitte
        PAUSE,
        circle(50, 70, 13),                              # Kopf (gross genug für Gesicht)
        PAUSE,
        [(39, 50), (18, 64)], [(24, 60), (21, 70)], [(24, 60), (13, 61)],   # Arm links
        [(61, 50), (82, 64)], [(76, 60), (79, 70)], [(76, 60), (87, 61)],   # Arm rechts
        PAUSE,
        [(35, 83), (65, 83)], closed([(41, 83), (59, 83), (58, 99), (42, 99)]),   # Hut
        PAUSE,
        dot(44, 75, 1.6), dot(56, 75, 1.6),              # Augen
        [(50, 70), (63, 67), (50, 66)],                  # Karottennase
        PAUSE,
        dot(50, 51, 1.8), dot(50, 45, 1.8), dot(50, 39, 1.8),   # Knöpfe
    ]


def _tasse():
    body = [(22, 72), (25, 22)] + bezier((25, 22), (26, 12), (34, 10), (40, 10)) + \
           [(60, 10)] + bezier((60, 10), (66, 10), (74, 12), (75, 22)) + [(78, 72)]
    steam = [[(x + 4 * math.sin(i / 10 * 2 * math.pi), 80 + i * 2) for i in range(11)] for x in (38, 50, 62)]
    heart = _heart(n=28, cx=50, cy=42, s=1.1)[0]
    return [
        body,                                            # Becher
        PAUSE,
        arc(77, 44, 14, 90, -90, n=14),                  # Henkel aussen
        arc(77, 44, 7, 90, -90, n=10),                   # Henkel innen
        PAUSE,
        ellipse(50, 72, 28, 5, n=28),                    # Rand
        PAUSE,
        bezier((6, 8), (20, 2), (80, 2), (94, 8)),       # Untertasse
        PAUSE,
    ] + steam + [                                        # Dampf
        PAUSE,
        heart,                                           # Herz auf der Tasse
    ]


def _mond_stern():
    crescent = arc(40, 50, 38, 60, 300, n=28) + arc(58, 50, 33, 271.7, 88.3, n=22)
    return [
        crescent,                                        # Mondsichel
        PAUSE,
        star_points(78, 72, 13, 5.5),                    # Stern
        PAUSE,
        [(80, 22), (80, 38)], [(72, 30), (88, 30)],      # Funkeln
        dot(66, 92, 1.5), dot(92, 50, 1.5),
    ]


def _ballon():
    string = [(50 + 4 * math.sin(i / 14 * 3 * math.pi), 29 - i * 2) for i in range(15)]
    return [
        ellipse(50, 62, 25, 31),                         # Ballon
        PAUSE,
        closed([(46, 28), (54, 28), (50, 32)]),          # Knoten
        PAUSE,
        string,                                          # Schnur
        PAUSE,
        arc(50, 62, 18, 110, 160, n=8),                  # Glanzlicht
    ]


def _wolke_regen():
    cloud = ([(80, 46), (22, 46)] + arc(25, 58, 12, 255, 80, n=12)
             + arc(45, 70, 16, 165, 20, n=14) + arc(66, 66, 14, 120, 10, n=12)
             + arc(80, 55, 9, 80, -90, n=10))
    rain = [[(22, 38), (18, 28)], [(34, 38), (30, 28)], [(70, 38), (66, 28)],
            [(28, 20), (24, 10)], [(78, 22), (74, 12)], [(40, 18), (36, 8)]]
    return [
        cloud,                                           # Wolke
        PAUSE,
    ] + rain + [                                         # Regen = ein Baustein
        PAUSE,
        [(58, 44), (49, 27), (57, 27), (47, 4)],         # Blitz
    ]


def _schmetterling():
    upper = bezier((49, 60), (36, 98), (2, 94), (9, 72)) + bezier((9, 72), (13, 58), (32, 52), (49, 54))
    lower = bezier((49, 50), (26, 52), (10, 30), (23, 17)) + bezier((23, 17), (34, 8), (46, 24), (49, 42))
    return [
        upper, lower,                                    # linke Flügel
        PAUSE,
        mirror(upper), mirror(lower),                    # rechte Flügel
        PAUSE,
        ellipse(50, 47, 3.5, 24, n=24),                  # Körper
        circle(50, 76, 5, n=16),                         # Kopf
        PAUSE,
        bezier((48, 80), (46, 88), (40, 94), (36, 96)), dot(35, 96, 2),   # Fühler
        bezier((52, 80), (54, 88), (60, 94), (64, 96)), dot(65, 96, 2),
        PAUSE,
        circle(27, 74, 6, n=16), circle(73, 74, 6, n=16),   # Flügelmuster
        dot(32, 30, 3), dot(68, 30, 3),
    ]


def _matterhorn():
    return [
        [(0, 8), (100, 8)],                              # Boden
        PAUSE,
        [(2, 8), (18, 26), (30, 44), (40, 66), (47, 84), (52, 96), (59, 94),
         (62, 80), (70, 64), (80, 50), (98, 26)],        # Berg mit gebogener Spitze
        PAUSE,
        [(39, 64), (44, 56), (48, 62), (54, 54), (60, 62), (65, 58), (69, 64)],   # Schneegrenze
        PAUSE,
        [(52, 96), (55, 80), (54, 60)],                  # Grat (nur im Schnee)
        PAUSE,
        arc(14, 84, 7, 0, 360, n=16),                    # Sonne
    ]


def _schweizer_flagge():
    top =[(14 + 70 * i / 20, 95 + 2 * math.sin(i / 20 * 2 * math.pi)) for i in range(21)]
    bottom = [(14 + 70 * i / 20, 39 + 2 * math.sin(i / 20 * 2 * math.pi)) for i in range(20, -1, -1)]
    flag = top + bottom + [top[0]]
    cx, cy, a, w = 49, 67, 18, 6        # Kreuz: Mitte, halbe Länge, halbe Breite
    cross = closed([(cx - w, cy + a), (cx + w, cy + a), (cx + w, cy + w), (cx + a, cy + w),
                    (cx + a, cy - w), (cx + w, cy - w), (cx + w, cy - a), (cx - w, cy - a),
                    (cx - w, cy - w), (cx - a, cy - w), (cx - a, cy + w), (cx - w, cy + w)])
    return [
        [(14, 0), (14, 96)], circle(14, 98, 2, n=10),    # Fahnenstange
        PAUSE,
        flag,                                            # wehende Fahne
        PAUSE,
        cross,                                           # Schweizer Kreuz
        PAUSE,
        [(4, 0), (24, 0)],                               # Boden
    ]


SHAPES = {
    'quadrat': [
        closed([(0, 0), (100, 0), (100, 100), (0, 100)]),  # füllt das ganze Zeichenfeld
    ],
    'haus': [
        closed([(20, 0), (80, 0), (80, 50), (20, 50)]),   # Wände
        [(12, 48), (50, 88), (88, 48)],                     # Dach
        [(42, 0), (42, 26), (58, 26), (58, 0)],             # Tür
    ],
    'sonne': _sun(),
    'stern': _star(),
    'herz': _heart(),
    'baum': [
        closed([(44, 0), (56, 0), (56, 30), (44, 30)]),    # Stamm
        circle(50, 60, 30),                                 # Krone
    ],
    'fisch': [
        ellipse(42, 50, 30, 18),                            # Körper
        closed([(71, 50), (92, 68), (92, 32)]),             # Schwanz
        circle(28, 54, 3, n=12),                            # Auge
    ],
    'blume': _flower(),
    'smiley': [
        circle(50, 50, 42),
        circle(35, 63, 4, n=12),
        circle(65, 63, 4, n=12),
        arc(50, 50, 24, 205, 335),
    ],
    'boot': [
        closed([(10, 30), (90, 30), (75, 12), (25, 12)]),  # Rumpf
        [(50, 30), (50, 90)],                               # Mast
        closed([(53, 86), (53, 36), (82, 36)]),             # Segel
        [(0, 6), (12, 9), (25, 5), (38, 9), (50, 5), (62, 9), (75, 5), (88, 9), (100, 6)],  # Wellen
    ],
    'katze': [
        circle(50, 42, 30), PAUSE,                          # Kopf
        [(28, 62), (30, 92), (47, 72)],                     # Ohren
        [(53, 72), (70, 92), (72, 62)], PAUSE,
        circle(39, 50, 4, n=12),                            # Augen
        circle(61, 50, 4, n=12), PAUSE,
        closed([(46, 38), (54, 38), (50, 33)]), PAUSE,      # Nase
        [(44, 33), (5, 38)], [(44, 31), (5, 26)],           # Schnurrhaare (passend zum Schnurrbart!)
        [(56, 33), (95, 38)], [(56, 31), (95, 26)],
    ],
    # --- neu ---
    'eiffelturm': _eiffelturm(),
    'croissant': _croissant(),
    'baguette': _baguette(),
    'weinglas': _weinglas(),
    'schnecke': _schnecke(),
    'gluehbirne': _gluehbirne(),
    'fliegenpilz': _fliegenpilz(),
    'eis': _eis(),
    'regenschirm': _regenschirm(),
    'rakete': _rakete(),
    'apfel': _apfel(),
    'schneemann': _schneemann(),
    'tasse': _tasse(),
    'mond': _mond_stern(),
    'ballon': _ballon(),
    'gewitter': _wolke_regen(),
    'schmetterling': _schmetterling(),
    'matterhorn': _matterhorn(),
    'schweiz': _schweizer_flagge(),
}


def _key(name):
    key = name.strip().lower()
    if key not in SHAPES:
        raise KeyError('Unbekannte Form "{}". Verfügbar: {}'.format(name, ', '.join(sorted(SHAPES))))
    return key


def get(name):
    """Alle Striche der Form (ohne PAUSE-Marker)."""
    return [s for s in SHAPES[_key(name)] if s != PAUSE]


def groups(name):
    """Bausteine der Form: Liste von Strich-Listen. Zwischen Bausteinen wird pausiert."""
    items = SHAPES[_key(name)]
    if PAUSE not in items:
        return [[s] for s in items]          # jeder Strich ein eigener Baustein
    result, current = [], []
    for s in items:
        if s == PAUSE:
            if current:
                result.append(current)
            current = []
        else:
            current.append(s)
    if current:
        result.append(current)
    return result


def start_point(strokes):
    return strokes[0][0]


def stroke_length(strokes):
    """Gesamtlänge aller Striche (in Form-Einheiten), z. B. für Zeitschätzung."""
    return sum(math.dist(a, b) for s in strokes for a, b in zip(s, s[1:]))


if __name__ == '__main__':
    # Vorschau aller Formen als PNG, mit der echten Stiftbreite (Standard 3 mm);
    # Farbe wechselt pro Baustein, roter Punkt = Startpunkt
    import sys
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    pen_mm = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
    field_mm = 80.0                                   # DRAW_SIZE
    names = sorted(SHAPES)
    cols = 6
    rows = (len(names) + cols - 1) // cols
    cell = 2.6                                        # Zoll pro Feld
    fig, axes = plt.subplots(rows, cols, figsize=(cols * cell, rows * (cell + 0.3) + 0.5))
    for ax in axes.flat:
        ax.axis('off')
    fig.tight_layout(pad=1.5, rect=(0, 0, 1, 0.96))
    colors = ['#1a1a1a', '#1f5fa8', '#b8441f', '#2a8a3e', '#7a3fa0', '#a07a00', '#00808a']
    for ax, name in zip(axes.flat, names):
        ax.set_xlim(-5, 105)
        ax.set_ylim(-5, 105)
        ax.set_aspect('equal')
        bbox = ax.get_window_extent()
        pt_per_unit = bbox.width / 110.0 * 72.0 / fig.dpi
        lw = pen_mm / (field_mm / 100.0) * pt_per_unit
        ax.add_patch(plt.Rectangle((0, 0), 100, 100, fill=False, ls=':', lw=0.6, color='#999999'))
        for gi, grp in enumerate(groups(name)):
            for s in grp:
                ax.plot([p[0] for p in s], [p[1] for p in s], '-', color=colors[gi % len(colors)],
                        linewidth=lw, solid_capstyle='round', solid_joinstyle='round')
        ax.plot(*start_point(get(name)), 'o', color='red', markersize=4)
        ax.set_title('{}  ({} Bausteine)'.format(name, len(groups(name))), fontsize=9)
    fig.suptitle('PicassoBot-Formen, Stift {:.0f} mm auf {:.0f} x {:.0f} mm  -  Farbe = Baustein'
                 .format(pen_mm, field_mm, field_mm), fontsize=11)
    fig.savefig('shapes_preview.png', dpi=110)
    print('Vorschau gespeichert: shapes_preview.png  (Stift {} mm)'.format(pen_mm))
#! /usr/bin/env python3
"""
PicassoBot - Karte lesen (läuft auf dem LAPTOP, nicht auf dem Roboter)

Die Kamera zeigt ein Bild mit einem Rahmen. Karte in den Rahmen halten,
LEERTASTE drücken: Die Handschrift wird gelesen (TrOCR, offline), mit den
Formen aus shapes.py abgeglichen und das Wort an den Roboter geschickt.
Auf dem Roboter läuft dazu:   python3 02_zeichnen.py --karte

Bei unsicherer Erkennung fragt das Script im Terminal nach (Top 3 zur Auswahl).

EINMALIG ZU HAUSE (mit Internet):
    pip install -r requirements_laptop.txt
    python karte_lesen.py --vorbereiten          # lädt das Modell nach ./trocr_modell

IM LABOR (Laptop im WLAN airobotics, kein Internet nötig):
    python karte_lesen.py                        # Laptop-Kamera
    python karte_lesen.py --kamera 1             # USB-Webcam (z. B. am Roboter montiert)

TESTEN OHNE ROBOTER:
    python karte_lesen.py --nicht-senden                     # nur anzeigen, nichts schicken
    python karte_lesen.py --bild karte1.jpg karte2.jpg       # Fotos statt Kamera
    python karte_lesen.py --test-text KATZC --nicht-senden   # ohne Modell: nur Abgleich testen

Tasten im Kamerafenster: LEERTASTE = lesen, M = Wort von Hand eingeben, Q/ESC = beenden
Jede Aufnahme wird unter ./aufnahmen/ gespeichert (zum Nachprüfen und Verbessern).

Karten am besten: DRUCKBUCHSTABEN, dicker schwarzer Filzstift, weisse Karte, ein Wort.
"""

import argparse
import datetime
import difflib
import os
import socket
import sys
import unicodedata

import shapes

# ---------------------------------------------------------------------- #
# Einstellungen
# ---------------------------------------------------------------------- #
ROBOTER_IP = '192.168.1.122'      # NUC im WLAN airobotics
ROBOTER_PORT = 5005               # wie in 02_zeichnen.py --karte
MODELL_NAME = 'microsoft/trocr-small-handwritten'   # grösser/genauer: microsoft/trocr-base-handwritten
MODELL_ORDNER = 'trocr_modell'
SCHWELLE = 0.80                   # ab dieser Sicherheit ohne Rückfrage zeichnen ...
ABSTAND = 0.08                    # ... und nur, wenn der Zweitbeste so viel schlechter ist
RAHMEN = (0.15, 0.30, 0.85, 0.70) # Rahmen im Kamerabild (links, oben, rechts, unten) als Anteil

# Zusätzliche Schreibweisen auf Karten -> Form in shapes.py
SYNONYME = {
    'GLUEHLAMPE': 'gluehbirne', 'LAMPE': 'gluehbirne',
    'PILZ': 'fliegenpilz',
    'GLACE': 'eis', 'GLACECORNET': 'eis', 'EISCREME': 'eis',
    'WOLKE': 'gewitter', 'REGEN': 'gewitter', 'BLITZ': 'gewitter',
    'FAHNE': 'schweiz', 'FLAGGE': 'schweiz', 'SCHWEIZERFAHNE': 'schweiz', 'SCHWEIZERKREUZ': 'schweiz',
    'BERG': 'matterhorn',
    'KAFFEE': 'tasse', 'KAFFEETASSE': 'tasse',
    'WEIN': 'weinglas',
    'GESICHT': 'smiley',
    'SCHIFF': 'boot', 'SEGELBOOT': 'boot',
    'BROT': 'baguette',
    'TURM': 'eiffelturm',
    'MONDSICHEL': 'mond',
    'SCHIRM': 'regenschirm',
}


# ---------------------------------------------------------------------- #
# Abgleich mit der Wortliste
# ---------------------------------------------------------------------- #

def normalisieren(text):
    """GROSS, Umlaute ausgeschrieben, nur Buchstaben: 'Glühbirne!' -> 'GLUEHBIRNE'."""
    t = text.upper().replace('Ä', 'AE').replace('Ö', 'OE').replace('Ü', 'UE').replace('ß', 'SS')
    t = unicodedata.normalize('NFKD', t)
    return ''.join(c for c in t if 'A' <= c <= 'Z')


def vokabular():
    """Alle Schreibweisen -> Form. Grundlage sind die Formen in shapes.py."""
    voc = {normalisieren(k): k for k in shapes.SHAPES}
    for wort, form in SYNONYME.items():
        if form in shapes.SHAPES:
            voc[normalisieren(wort)] = form
    return voc


def abgleichen(kandidaten, voc):
    """kandidaten: [(gelesener Text, Gewicht 0..1)], bester zuerst.
    Rückgabe: [(form, sicherheit)] absteigend, jede Form nur einmal."""
    best = {}
    for text, gewicht in kandidaten:
        t = normalisieren(text)
        if not t:
            continue
        for schreibweise, form in voc.items():
            r = difflib.SequenceMatcher(None, t, schreibweise).ratio()
            score = r * (0.85 + 0.15 * gewicht)
            if score > best.get(form, 0.0):
                best[form] = score
    return sorted(best.items(), key=lambda x: -x[1])


def warnung_aehnliche_woerter(voc, grenze=0.75):
    worte = sorted(set(voc.values()))
    for i, a in enumerate(worte):
        for b in worte[i + 1:]:
            r = difflib.SequenceMatcher(None, normalisieren(a), normalisieren(b)).ratio()
            if r >= grenze:
                print('  Hinweis: "{}" und "{}" sind sich sehr ähnlich ({:.2f}) - '
                      'hier wird öfter nachgefragt.'.format(a, b, r))


# ---------------------------------------------------------------------- #
# Texterkennung (TrOCR, offline)
# ---------------------------------------------------------------------- #

class Leser:
    def __init__(self, ordner=MODELL_ORDNER):
        if not os.path.isdir(ordner):
            sys.exit('Modell nicht gefunden ({}). Zuerst zu Hause mit Internet ausführen:\n'
                     '    python karte_lesen.py --vorbereiten'.format(ordner))
        os.environ.setdefault('HF_HUB_OFFLINE', '1')     # im Labor nie ins Internet
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
        print('Lade Modell aus {} ...'.format(ordner))
        self.proc = TrOCRProcessor.from_pretrained(ordner)
        self.model = VisionEncoderDecoderModel.from_pretrained(ordner)
        self.model.eval()

    def lesen(self, bild_rgb, n=5):
        """Gibt die n wahrscheinlichsten Lesarten zurück: [(text, gewicht 0..1)]."""
        import torch
        from PIL import Image
        pix = self.proc(images=Image.fromarray(bild_rgb), return_tensors='pt').pixel_values
        with torch.no_grad():
            out = self.model.generate(pix, num_beams=n, num_return_sequences=n, max_new_tokens=24,
                                      output_scores=True, return_dict_in_generate=True)
        texte = self.proc.batch_decode(out.sequences, skip_special_tokens=True)
        logp = out.sequences_scores.tolist()
        top = max(logp)
        gewichte = [pow(2.718281828, lp - top) for lp in logp]   # bester = 1.0
        return list(zip(texte, gewichte))


def vorbereiten():
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    print('Lade {} herunter (einmalig, ca. 250 MB) ...'.format(MODELL_NAME))
    TrOCRProcessor.from_pretrained(MODELL_NAME).save_pretrained(MODELL_ORDNER)
    VisionEncoderDecoderModel.from_pretrained(MODELL_NAME).save_pretrained(MODELL_ORDNER)
    print('Fertig: Modell liegt in ./{}  - im Labor ist kein Internet mehr nötig.'.format(MODELL_ORDNER))


# ---------------------------------------------------------------------- #
# Bild aufbereiten
# ---------------------------------------------------------------------- #

def rahmen_px(shape):
    h, w = shape[:2]
    l, o, r, u = RAHMEN
    return int(l * w), int(o * h), int(r * w), int(u * h)


def schrift_ausschneiden(bild_bgr):
    """Schneidet den Rahmen aus und darin eng um die Schrift (mit Rand).
    Rückgabe: RGB-Bild für das Modell."""
    import cv2
    import numpy as np
    x0, y0, x1, y1 = rahmen_px(bild_bgr.shape)
    roi = bild_bgr[y0:y1, x0:x1]
    grau = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    maske = cv2.adaptiveThreshold(cv2.GaussianBlur(grau, (5, 5), 0), 255,
                                  cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15)
    maske = cv2.morphologyEx(maske, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    # Weisse Karte finden (grösste helle Fläche) und nur Tinte INNERHALB der Karte zählen,
    # sonst gilt die Kante Karte/Hintergrund als Schrift
    _, hell = cv2.threshold(grau, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    konturen, _ = cv2.findContours(hell, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if konturen:
        karte = max(konturen, key=cv2.contourArea)
        if cv2.contourArea(karte) > 0.15 * grau.size:
            innen = np.zeros_like(grau)
            cv2.drawContours(innen, [cv2.convexHull(karte)], -1, 255, -1)
            k = max(3, int(0.04 * min(grau.shape)))
            innen = cv2.erode(innen, np.ones((k, k), np.uint8))
            maske = cv2.bitwise_and(maske, innen)

    rand = int(0.03 * min(maske.shape))                      # Rahmenkanten/Finger ignorieren
    maske[:rand, :] = maske[-rand:, :] = 0
    maske[:, :rand] = maske[:, -rand:] = 0
    ys, xs = np.nonzero(maske)
    if len(xs) > 50:
        a, b = np.percentile(xs, [1, 99]).astype(int)
        c, d = np.percentile(ys, [1, 99]).astype(int)
        m = int(0.15 * max(b - a, d - c))
        roi = roi[max(0, c - m):d + m, max(0, a - m):b + m]
    return cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)


# ---------------------------------------------------------------------- #
# An den Roboter senden
# ---------------------------------------------------------------------- #

def senden(form, host, port):
    try:
        with socket.create_connection((host, port), timeout=5) as s:
            s.sendall((form + '\n').encode())
            s.settimeout(2.0)
            try:
                antwort = s.recv(256)
            except socket.timeout:
                print('  Roboter zeichnet noch - Wort wird übernommen, sobald er bereit ist ...')
                s.settimeout(600)
                antwort = s.recv(256)
        antwort = antwort.decode('utf-8', 'replace').strip()
        print('  Roboter: ' + (antwort or '(keine Antwort)'))
        return antwort.startswith('OK')
    except OSError as e:
        print('  Roboter nicht erreichbar ({}:{}): {}'.format(host, port, e))
        print('  Läuft auf dem NUC  python3 02_zeichnen.py --karte ?  Laptop im WLAN airobotics?')
        return False


# ---------------------------------------------------------------------- #
# Entscheiden: sofort zeichnen oder nachfragen
# ---------------------------------------------------------------------- #

def entscheiden(treffer, kandidaten, interaktiv=True):
    """Gibt die Form zurück, die gezeichnet werden soll, oder None (nochmal lesen)."""
    gelesen = ', '.join('"{}"'.format(t) for t, _ in kandidaten[:3])
    print('  gelesen: ' + (gelesen or '(nichts)'))
    if not treffer:
        print('  Keine passende Form gefunden.')
        return None
    top = treffer[:3]
    print('  Treffer: ' + ',  '.join('{} {:.0%}'.format(f, s) for f, s in top))
    bester, sicher = top[0]
    zweiter = top[1][1] if len(top) > 1 else 0.0
    if sicher >= SCHWELLE and sicher - zweiter >= ABSTAND:
        print('  -> sicher erkannt: {}'.format(bester))
        return bester
    if not interaktiv:
        print('  -> unsicher, im Testmodus keine Rückfrage')
        return None
    for i, (f, s) in enumerate(top, 1):
        print('     {}) {}  ({:.0%})'.format(i, f, s))
    antwort = input('  Unsicher. Nummer, Name eintippen, oder Enter = nochmal lesen: ').strip().lower()
    if antwort.isdigit() and 1 <= int(antwort) <= len(top):
        return top[int(antwort) - 1][0]
    if antwort in shapes.SHAPES:
        return antwort
    return None


def speichern(bild, text):
    import cv2
    os.makedirs('aufnahmen', exist_ok=True)
    stempel = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    name = '{}_{}.jpg'.format(stempel, normalisieren(text)[:20] or 'leer')
    cv2.imwrite(os.path.join('aufnahmen', name), bild)


# ---------------------------------------------------------------------- #
# Hauptprogramm
# ---------------------------------------------------------------------- #

def verarbeiten(bild_bgr, leser, voc, args, interaktiv=True):
    if args.test_text:
        kandidaten = [(args.test_text, 1.0)]
    else:
        print('  lese ...')
        kandidaten = leser.lesen(schrift_ausschneiden(bild_bgr))
    if bild_bgr is not None:
        speichern(bild_bgr, kandidaten[0][0] if kandidaten else '')
    form = entscheiden(abgleichen(kandidaten, voc), kandidaten, interaktiv)
    if form and not args.nicht_senden:
        senden(form, args.roboter, args.port)
    elif form:
        print('  (nicht gesendet: --nicht-senden)')
    return form


def kamera_schleife(leser, voc, args):
    import cv2
    cam = cv2.VideoCapture(args.kamera)
    if not cam.isOpened():
        sys.exit('Kamera {} nicht gefunden. Andere Nummer mit --kamera 1 probieren.'.format(args.kamera))
    fenster = 'PicassoBot - Karte (Leertaste = lesen, M = von Hand, Q = Ende)'
    status = 'Karte in den Rahmen halten, Leertaste'
    while True:
        ok, bild = cam.read()
        if not ok:
            continue
        anzeige = bild.copy()
        x0, y0, x1, y1 = rahmen_px(bild.shape)
        cv2.rectangle(anzeige, (x0, y0), (x1, y1), (0, 200, 0), 2)
        cv2.putText(anzeige, status, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 0), 2)
        cv2.imshow(fenster, anzeige)
        taste = cv2.waitKey(1) & 0xFF
        if taste in (ord('q'), 27):
            break
        if taste == ord(' '):
            print('\nKarte erkannt?')
            form = verarbeiten(bild, leser, voc, args)
            status = 'Gesendet: {}'.format(form) if form else 'Nochmal: Karte in den Rahmen, Leertaste'
        if taste == ord('m'):
            wort = input('\nForm von Hand: ').strip().lower()
            if wort in shapes.SHAPES and not args.nicht_senden:
                senden(wort, args.roboter, args.port)
            elif wort not in shapes.SHAPES:
                print('  Unbekannt. Verfügbar: ' + ', '.join(sorted(shapes.SHAPES)))
    cam.release()
    cv2.destroyAllWindows()


def main():
    global SCHWELLE, RAHMEN
    ap = argparse.ArgumentParser(description='PicassoBot: Karte lesen und an den Roboter senden')
    ap.add_argument('--vorbereiten', action='store_true', help='Modell herunterladen (einmalig, mit Internet)')
    ap.add_argument('--kamera', type=int, default=0, help='Kamera-Nummer (0 = eingebaut, 1 = USB)')
    ap.add_argument('--bild', nargs='+', help='Fotos statt Kamera verarbeiten')
    ap.add_argument('--test-text', help='Texterkennung überspringen, diesen Text abgleichen')
    ap.add_argument('--roboter', default=ROBOTER_IP)
    ap.add_argument('--port', type=int, default=ROBOTER_PORT)
    ap.add_argument('--nicht-senden', action='store_true', help='nur anzeigen, nichts an den Roboter')
    ap.add_argument('--schwelle', type=float, default=SCHWELLE)
    args = ap.parse_args()
    SCHWELLE = args.schwelle

    if args.vorbereiten:
        vorbereiten()
        return

    voc = vokabular()
    print('{} Formen, {} Schreibweisen.'.format(len(set(voc.values())), len(voc)))
    warnung_aehnliche_woerter(voc)
    leser = None if args.test_text else Leser()

    if args.test_text and not args.bild:
        verarbeiten(None, leser, voc, args)
    elif args.bild:
        import cv2
        for pfad in args.bild:
            print('\n' + pfad)
            bild = cv2.imread(pfad)
            if bild is None:
                print('  konnte nicht gelesen werden')
                continue
            # Fotos: ganzes Bild als Rahmen verwenden
            RAHMEN = (0.0, 0.0, 1.0, 1.0)
            verarbeiten(bild, leser, voc, args, interaktiv=not args.nicht_senden)
    else:
        kamera_schleife(leser, voc, args)


if __name__ == '__main__':
    main()

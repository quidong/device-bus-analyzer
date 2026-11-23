"""
Tests für das 3D-Druck-Gehäuse (enclosure/).

  python3 -m pytest -q tests/test_enclosure.py

Prüft in Einbaulage gegen die echten Platinendaten (enclosure/board.json):
  * STL-Dateien geschlossen (wasserdicht) und druckbar groß
  * Platine passt ohne Kollision, liegt auf dem Steg, wird von Rippen gehalten
  * Kein Bauteil berührt Deckel oder Unterteil, der RAST-Stecker hat Platz,
    wird seitlich geführt, kann nicht abheben, Kabel wird geklemmt
  * Gehäuse ist dicht: von innen gibt es keinen Weg nach außen außer der
    Kabeldurchführung, und die ist mit Kabel geschlossen
  * Magnettaschen: richtige Größe, außen geschlossen, kollidieren nicht
  * LED-Lichtleiter mit dünner Restwand
  * Antennenbereich frei, Deckel und Unterteil durchdringen sich nicht
"""
import json
import os

import pytest

trimesh = pytest.importorskip("trimesh")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENC = os.path.join(ROOT, "enclosure")


@pytest.fixture(scope="module")
def data():
    with open(os.path.join(ENC, "board.json")) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def tray():
    return trimesh.load(os.path.join(ENC, "macs_gehaeuse_unterteil.stl"))


@pytest.fixture(scope="module")
def lid():
    return trimesh.load(os.path.join(ENC, "test", "deckel_montiert.stl"))


@pytest.fixture(scope="module")
def lid_print():
    return trimesh.load(os.path.join(ENC, "macs_gehaeuse_deckel.stl"))


def box(x0, y0, z0, x1, y1, z1):
    b = trimesh.creation.box(extents=[x1 - x0, y1 - y0, z1 - z0])
    b.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
    return b


def overlap(a, b):
    """Schnittvolumen in mm³ (0 = keine Kollision)."""
    inter = trimesh.boolean.intersection([a, b], engine="manifold")
    return 0.0 if inter.is_empty else float(inter.volume)


def inside(mesh, *pts):
    return list(mesh.contains(pts))


# ----------------------------------------------------------------- Dateien
def test_meshes_watertight(tray, lid, lid_print):
    for m in (tray, lid, lid_print):
        assert m.is_watertight and m.volume > 1000


def test_print_size_and_orientation(tray, lid_print):
    for m in (tray, lid_print):
        lo, hi = m.bounds
        assert (hi - lo).max() < 100            # passt auf jedes Druckbett
    # Deckel liegt mit der flachen Oberseite auf z=0
    assert abs(lid_print.bounds[0][2]) < 1e-3


# ------------------------------------------------------------------ Platine
def test_board_fits_without_collision(data, tray, lid):
    t = data["P"]["board_t"]
    pcb = box(0.02, 0.02, 0.0, data["W"] - 0.02, data["H"] - 0.02, t)
    assert overlap(pcb, tray) < 0.01
    assert overlap(pcb, lid) < 0.01


def test_board_rests_on_ledge(data, tray):
    W, H = data["W"], data["H"]
    pts = [(0.5, H / 2, -0.1), (W - 0.5, H / 2, -0.1),
           (5.0, 0.5, -0.1), (W - 5.0, 0.5, -0.1),       # Wangen neben dem Stecker
           (W / 2, H - 0.5, -0.1)]
    assert all(inside(tray, *pts))


def test_board_clamped_by_ribs(data, lid):
    t = data["P"]["board_t"]
    assert len(data["press"]) >= 3
    assert sum(max(x1 - x0, y1 - y0) for x0, y0, x1, y1 in data["press"]) >= 40   # mm Klemmlänge
    sides = set()
    for x0, y0, x1, y1 in data["press"]:
        assert inside(lid, ((x0 + x1) / 2, (y0 + y1) / 2, t + 0.1))[0]
        sides.add("l" if x0 <= 0 else "r" if x1 >= data["W"] else "b" if y0 <= 0 else "t")
    assert {"l", "r"} <= sides          # beide langen Seiten gehalten


def test_board_cannot_slide_lengthwise(data, tray):
    # Anschlag oberhalb der Platinenoberkante, unterhalb des Antennenüberstands
    gap = data["P"]["gap"]
    assert inside(tray, (data["W"] / 2, data["H"] + gap + 0.7, 0.8))[0]


# ----------------------------------------------------------------- Bauteile
def test_components_clear_of_enclosure(data, tray, lid):
    t = data["P"]["board_t"]
    hits = []
    for ref, p in data["parts"].items():
        if ref == "J2":                  # Steckkante: eigener Test (Steckerkörper)
            continue
        x0, y0, x1, y1 = p["bbox"]
        h = p["h"]
        if ref == "J1":                  # Buchsenkörper statt Courtyard (ragt bündig an die Kante)
            x0, y0, x1, y1 = 0.0, data["usb"]["y0"], 7.4, data["usb"]["y1"]
        b = box(x0, y0, t + 0.05, x1, y1, t + h)
        for name, m in (("Deckel", lid), ("Unterteil", tray)):
            v = overlap(b, m)
            if v > 0.01:
                hits.append((ref, name, round(v, 2)))
    assert not hits, hits


def _plug(data, shrink=0.0):
    P, R = data["P"], data["rast"]
    return box(R["cx"] - P["plug_w"] / 2 + shrink, R["edge"] - P["plug_out"] + shrink,
               P["plug_z0"] + shrink,
               R["cx"] + P["plug_w"] / 2 - shrink, R["edge"] + P["plug_on_board"] - shrink,
               P["board_t"] + P["plug_above"] - shrink)


def test_rast_plug_fits(data, tray, lid):
    plug = _plug(data, 0.02)
    assert overlap(plug, tray) < 0.01
    assert overlap(plug, lid) < 0.01


def test_rast_plug_guided_sideways(data, tray):
    """Führungswände links/rechts mit wenig Spiel – der Stecker kann nicht
    seitlich verrutschen (vor der Zunge; auf der Zunge führen die Platinenwangen)."""
    P, R = data["P"], data["rast"]
    play = P["guide_play"]
    assert 0.1 <= play <= 0.4
    y = R["edge"] - P["plug_out"] / 2 - 1.5             # vor der Zungenkante
    for z in (P["plug_z0"] + 0.5, P["board_t"] + 1.0, P["board_t"] + P["plug_above"] - 0.5):
        for sgn in (-1, 1):
            xo = R["cx"] + sgn * (P["plug_w"] / 2 + play + 0.1)
            assert inside(tray, (xo, y, z))[0], (sgn, z)
    # Platinenwangen neben der Aussparung führen den Stecker auf der Zunge
    assert R["notch_w"] - P["plug_w"] <= 1.0


def test_rast_plug_held_down(data, lid):
    """Niederhalter im Deckel knapp über dem Stecker (beide Enden), Mitte frei
    für die Adern."""
    P, R = data["P"], data["rast"]
    top = P["board_t"] + P["plug_above"]
    y = R["edge"] - P["plug_out"] / 2
    for sgn in (-1, 1):
        x = R["cx"] + sgn * (P["plug_w"] / 2 - 1.0)
        assert inside(lid, (x, y, top + P["hold_gap"] + 0.2))[0], sgn
        assert not inside(lid, (x, y, top + P["hold_gap"] - 0.2))[0], sgn
    assert not inside(lid, (R["cx"], y, top + 1.0))[0]      # Adern frei


def test_board_cannot_slide_forward(data, tray):
    """Die Führungswände sind zugleich Anschlag für die Platinenwangen."""
    P, R = data["P"], data["rast"]
    for sgn in (-1, 1):
        x = R["cx"] + sgn * (P["plug_w"] / 2 + P["guide_play"] + P["guide_t"] / 2)
        assert inside(tray, (x, -P["gap"] - 0.2, P["board_t"] / 2))[0]
        assert data["W"] > x > 0
        # an dieser Stelle hat die Platine Material (Wange)
        assert abs(x - R["cx"]) > R["notch_w"] / 2


def test_cable_room_in_front_of_plug(data, tray, lid):
    P, R = data["P"], data["rast"]
    t = P["board_t"]
    room = box(R["cx"] - 3, -P["gap"] - P["chamber"] + 1.5, t,
               R["cx"] + 3, R["edge"] - P["plug_out"] - 0.1, t + P["hood_above"] - 0.2)
    assert overlap(room, tray) < 0.01 and overlap(room, lid) < 0.01


def _cable_x(data):
    return [data["parts"][r]["x"] for r in data["cable_exits"]]


def _cable(data, cx, d):
    P = data["P"]
    c = trimesh.creation.cylinder(radius=d / 2, height=40)
    c.apply_transform(trimesh.transformations.rotation_matrix(1.5708, [1, 0, 0]))
    c.apply_translation([cx, -20 + 3, P["board_t"] + P["cable_z"]])
    return c


def test_cable_passes_through_wall_and_is_clamped(data, tray, lid):
    P = data["P"]
    gland = P["cable_d"] + 2 * P["cable_fit"]
    assert P["cable_d"] - 0.6 <= gland < P["cable_d"]       # klemmt, quetscht nicht
    for cx in _cable_x(data):
        cab = _cable(data, cx, gland - 0.05)
        assert overlap(cab, tray) < 0.01 and overlap(cab, lid) < 0.01
        assert overlap(_cable(data, cx, P["cable_d"]), lid) > 0.1   # Klemmung


def test_enclosure_sealed(data, tray, lid):
    """Rays aus dem Innenraum in alle Richtungen müssen auf Material treffen –
    das Kabel steckt dabei in der Durchführung."""
    import numpy as np
    shell = [tray, lid]
    for cx in _cable_x(data):
        shell.append(_cable(data, cx, data["P"]["cable_d"]))
    allm = trimesh.util.concatenate(shell)
    P = data["P"]
    rng = np.random.default_rng(1)
    dirs = rng.normal(size=(600, 3))
    dirs /= np.linalg.norm(dirs, axis=1)[:, None]
    starts = [(data["W"] / 2, data["H"] / 2, P["board_t"] + 6),    # über der Platine
              (data["rast"]["cx"], -P["chamber"] / 2, P["board_t"] + 8),  # Kabelraum
              (data["W"] / 2, data["H"] / 2, -2.0)]                # unter der Platine
    for s in starts:
        origins = np.tile(s, (len(dirs), 1))
        hit = allm.ray.intersects_any(origins, dirs)
        assert hit.all(), f"offen von {s}: {int((~hit).sum())} Strahlen entweichen"


def _magnet_pos(data):
    """Wie magnet_pos() in gehaeuse.scad."""
    P = data["P"]
    off = P["magnet_d"] / 2 + P["magnet_fit"] / 2 + P["magnet_web"]
    x0, x1 = -P["gap"], data["W"] + P["gap"]
    y0 = -P["gap"] - P["chamber"]
    y1 = max(data["H"], data["antenna_top"]) + P["antenna_clear"]
    ya, yb = y0 - P["wall"] + data["magnet_inset"], y1 + P["wall"] - data["magnet_inset"]
    return [(x0 - P["wall"] - off, ya), (x0 - P["wall"] - off, yb),
            (x1 + P["wall"] + off, ya), (x1 + P["wall"] + off, yb)]


def test_magnets_in_side_lugs(data, tray):
    """Wie BSH-Board: 5 x 5 mm Magnete in Laschen außen an den Längsseiten,
    durchgehende Bohrung, Magnet liegt bündig an der Unterseite (direkt am Blech)."""
    P = data["P"]
    assert (P["magnet_d"], P["magnet_h"]) == (5.0, 5.0)
    zb = -P["below"] - P["floor"]                    # Unterseite Gehäuse
    assert abs(tray.bounds[0][2] - zb) < 0.01
    W = data["W"]
    for x, y in _magnet_pos(data):
        mag = trimesh.creation.cylinder(radius=P["magnet_d"] / 2, height=P["magnet_h"])
        mag.apply_translation([x, y, zb + P["magnet_h"] / 2])
        assert overlap(mag, tray) < 0.01, (x, y)                      # passt hinein
        assert not inside(tray, (x, y, zb + 0.1))[0]                   # unten offen, bündig
        assert not inside(tray, (x, y, zb + P["magnet_h"] - 0.1))[0]   # durchgehend
        r = P["magnet_d"] / 2 + P["magnet_fit"] / 2 + 0.4
        assert inside(tray, (x, y + r, zb + 2.5))[0]                   # Lasche drumherum
        assert x < -P["gap"] - P["wall"] or x > W + P["gap"] + P["wall"]   # außerhalb


def test_magnets_spread(data):
    pos = _magnet_pos(data)
    ys = sorted({round(y, 2) for _, y in pos})
    assert ys[1] - ys[0] > 40                        # weit auseinander -> hält kippsicher


def test_led_light_pipes(data, lid):
    P = data["P"]
    top = P["board_t"] + P["hood_above"] + P["floor"]
    assert len(data["leds"]) == 3
    for ref in data["leds"]:
        x, y = data["parts"][ref]["x"], data["parts"][ref]["y"]
        assert inside(lid, (x, y, top - P["led_skin"] / 2))[0], ref      # dünne Restwand
        assert not inside(lid, (x, y, top - P["led_skin"] - 0.3))[0], ref  # darunter hohl
        assert not inside(lid, (x, y, P["board_t"] + 1.0))[0], ref        # über der LED frei
        assert not inside(lid, (x, y, P["board_t"] + P["led_tube_z"] + 1.0))[0], ref  # Bohrung
        r = (3.0 / 2 + P["led_tube_d"] / 2) / 2                           # Mitte der Röhrchenwand
        sx = -r if x > data["W"] / 2 else r                               # zur Gehäusemitte hin
        assert inside(lid, (x + sx, y, P["board_t"] + P["led_tube_z"] + 1.0))[0], ref


def test_antenna_area_free(data, tray, lid):
    x0, y0, x1, y1 = data["parts"]["U1"]["bbox"]
    t = data["P"]["board_t"]
    ant = box(x0, data["H"], t, x1, y1, t + 3.2)
    assert overlap(ant, tray) < 0.01
    assert overlap(ant, lid) < 0.01


def test_lid_and_tray_do_not_intersect(tray, lid):
    assert overlap(tray, lid) < 0.05


def test_usb_socket_flush_with_board_edge(data):
    # Buchse höchstens 0,2 mm hinter der Kante, sonst stößt die Umspritzung an
    assert data["usb"]["front_x"] <= 0.2


def test_wall_thickness_for_fdm(data):
    """JLC3DP-DFM: keine Wand unter 1,2 mm (FDM-Minimum); tragende Teile
    2 mm. Einzige gewollte Ausnahme: die 1,2-mm-Fenster über den LEDs."""
    import sys
    sys.path.insert(0, ENC)
    import wall_thickness as wt
    P = data["P"]
    assert P["min_wall"] >= 2.0 and P["wall"] >= 2.0 and P["lip_t2"] >= 2.0
    assert P["led_skin"] >= 1.2
    # Druck-Deckel ist um die X-Achse gedreht: y_druck = y_gesamt - y_entwurf
    y_tot = max(data["H"], data["antenna_top"]) + P["antenna_clear"] + P["wall"]
    leds = [(data["parts"][r]["x"], y_tot - data["parts"][r]["y"]) for r in data["leds"]]
    for name, f in wt.FILES.items():
        m = trimesh.load(f)
        assert not len(wt.thin_spots(m, 1.15)[0]), f"{name}: Stellen unter 1,2 mm"
        spots = wt.thin_spots(m, 1.9)[0]
        for x, y, _ in spots:
            # Deckel liegt um die X-Achse gedreht (Druckausrichtung), LED-Positionen oben schon umgerechnet
            assert name == "Deckel" and min((x - lx) ** 2 + (y - ly) ** 2 for lx, ly in leds) < 3.5 ** 2, \
                f"{name}: unter 2 mm bei x={x:.1f} y={y:.1f}"


def test_printed_lid_is_a_rotation_not_a_mirror(lid, lid_print):
    """Der Druck-Deckel muss der montierte Deckel sein, um die X-Achse gedreht. Ein Spiegelbild würde USB-Aussparung
    und Schrift beim Umdrehen auf die falsche Seite bringen."""
    import numpy as np
    rot = trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0])
    m = lid.copy()
    m.apply_transform(rot)
    m.apply_translation(lid_print.bounds[0] - m.bounds[0])         # beide auf dasselbe Minimum legen
    assert np.allclose(m.bounds, lid_print.bounds, atol=0.05)
    assert abs(m.volume - lid_print.volume) < 1.0
    assert overlap(m, lid_print) > 0.999 * lid_print.volume          # deckungsgleich
    assert lid_print.bounds[0][2] == pytest.approx(0.0, abs=0.01)    # Oberseite liegt auf dem Druckbett


def test_usb_notch_is_on_the_usb_side_of_the_assembled_lid(data, lid):
    """Aussparung im Steckrand nur an der Seite x < 0, wo die USB-Buchse sitzt (nicht an der RAST-/Gegenseite)."""
    y = (data["usb"]["y0"] + data["usb"]["y1"]) / 2
    z = 1.6 + 4.6 + 0.5                                              # im Steckrand knapp unter der Trennebene
    left = inside(lid, (-0.3 - 0.15 + 0.5, y, z))[0]                 # Steckrand-Bereich links, x = x0 + fit + 0.5
    right = inside(lid, (30.3 - 0.5, y, z))[0]                       # gleiche Stelle rechts
    assert (not left) and right

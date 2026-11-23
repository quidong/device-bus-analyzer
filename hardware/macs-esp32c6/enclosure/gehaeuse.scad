// Gehäuse für die MACS-ESP32-C6-Platine – abgedichtete Ausführung mit Magneten
// und Führung für den RAST-2.5-Direktstecker (Lumberg 3517 04 K01)
// Maße kommen aus params.scad (erzeugt von make_enclosure.py aus der KiCad-Platine).
// Rendern: openscad -D 'part="unterteil"' -o unterteil.stl gehaeuse.scad
//          openscad -D 'part="deckel"'    -o deckel.stl    gehaeuse.scad
include <params.scad>

part = "beide";          // "unterteil" | "deckel" | "deckel_montiert" | "beide"
$fn = 48;
e = 0.01;

// ---------------------------------------------------------------- Maße
x0 = -gap;               y0 = -gap - chamber;    // vorn: Kabelraum vor der Zunge
x1 = W + gap;            y1 = max(H, antenna_top) + antenna_clear;
z_floor = -below;                    // Oberkante Boden
z_top   = board_t + above;           // Trennebene Unterteil/Deckel
z_in    = board_t + hood_above;      // Innenoberkante Deckel (Stecker + Kabelbogen)
z_cab   = board_t + cable_z;         // Kabelmitte
// lip_t2, lip_h2 (Steckrand) kommen aus params.scad

// RAST-Stecker (Hüllkörper) – Platinenzunge endet bei y = rast_edge
plug_x0 = rast_cx - plug_w / 2;      plug_x1 = rast_cx + plug_w / 2;
plug_y0 = rast_edge - plug_out;      plug_y1 = rast_edge + plug_on_board;
plug_top = board_t + plug_above;
guide_in0 = plug_x0 - guide_play;    guide_in1 = plug_x1 + guide_play;

module rrect(xa, ya, xb, yb, za, zb, r) {
    hull() for (x = [xa + r, xb - r], y = [ya + r, yb - r])
        translate([x, y, za]) cylinder(r = r, h = zb - za);
}

module cavity_box(za, zb) { translate([x0, y0, za]) cube([x1 - x0, y1 - y0, zb - za]); }

// Rechteck-Ring auf der Wandmitte (für Nut und Feder)
module wall_ring(w, za, zb) {
    difference() {
        translate([x0 - wall / 2 - w / 2, y0 - wall / 2 - w / 2, za])
            cube([x1 - x0 + wall + w, y1 - y0 + wall + w, zb - za]);
        translate([x0 - wall / 2 + w / 2, y0 - wall / 2 + w / 2, za - 1])
            cube([x1 - x0 + wall - w, y1 - y0 + wall - w, zb - za + 2]);
    }
}

// Rastnasen an den langen Seiten
snap_y = [H * 0.35, H * 0.8];
snap_z = z_top - lip_h2 / 2;
module snap_bumps(r) {
    for (y = snap_y) {
        translate([x0 + fit, y - 4, snap_z]) rotate([-90, 0, 0]) cylinder(r = r, h = 8);
        translate([x1 - fit, y - 4, snap_z]) rotate([-90, 0, 0]) cylinder(r = r, h = 8);
    }
}

// Geteilte Kabeldurchführung in der Stirnwand (vor dem RAST-Stecker):
// Unterteil hat einen Finger bis zur Kabelmitte (untere Halbschale),
// der Deckel einen Schlitz mit oberer Halbschale.
gland_d = cable_d + 2 * cable_fit;   // < cable_d -> Kabel wird geklemmt (Zugentlastung)
slot_w  = gland_d + 2 * min_wall;    // Kabelfinger: links/rechts vom Kabel volle Wandstärke
module cable_slot(cx) {
    d = wall + lip_t2 + fit + 1.5;
    translate([cx - slot_w / 2, y0 - wall - 1, z_top - lip_h2 - 1])
        cube([slot_w, d, z_cab - (z_top - lip_h2 - 1)]);
    translate([cx, y0 - wall - 1, z_cab]) rotate([-90, 0, 0]) cylinder(d = gland_d, h = d);
}
module cable_finger(cx) {
    difference() {
        translate([cx - slot_w / 2, y0 - wall, z_top - e])
            cube([slot_w, wall, z_cab - z_top + e]);
        translate([cx, y0 - wall - 1, z_cab]) rotate([-90, 0, 0]) cylinder(d = gland_d, h = wall + 2);
    }
}

// Magnetlaschen: Bohrungsmitte so, dass zwischen Bohrung und Außenwand ein
// Steg von magnet_web bleibt; Lasche reicht bis an die Wand.
function magnet_pos() = let (
    off = magnet_d / 2 + magnet_fit / 2 + magnet_web,
    ya = y0 - wall + magnet_inset, yb = y1 + wall - magnet_inset)
    [[x0 - wall - off, ya, -1], [x0 - wall - off, yb, -1],
     [x1 + wall + off, ya, 1], [x1 + wall + off, yb, 1]];
module magnet_lug(m) {
    r = magnet_d / 2 + magnet_fit / 2 + lug_wall;
    translate([0, 0, z_floor - floor])
    hull() {
        translate([m[0], m[1], 0]) cylinder(r = r, h = magnet_h);
        translate([m[2] < 0 ? x0 - wall - e : x1 + wall - 1, m[1] - r, 0])
            cube([1 + e, 2 * r, magnet_h]);
    }
}

// ------------------------------------------------------------ Unterteil
module unterteil() {
    difference() {
        union() {
            difference() {
                rrect(x0 - wall, y0 - wall, x1 + wall, y1 + wall, z_floor - floor, z_top, wall);
                cavity_box(z_floor, z_top + e);
            }
            // Auflagesteg rund um die Platine (+ Antennenbereich bis z=0),
            // im Bereich des Steckers ausgespart
            difference() {
                translate([x0, -gap, z_floor - e]) cube([x1 - x0, y1 + gap, below + e]);
                translate([ledge, ledge, z_floor - 1]) cube([W - 2 * ledge, H - 2 * ledge, below + 2]);
                translate([guide_in0 - 0.2, -gap - 1, z_floor - 1])
                    cube([guide_in1 - guide_in0 + 0.4, plug_y1 + gap + 1.5, below + 2]);
            }
            // Führungswände links/rechts vom Stecker: kein seitliches Verrutschen,
            // gleichzeitig Anschlag für die Platinenwangen (Platine kann nicht nach vorn)
            for (gx = [guide_in0 - guide_t, guide_in1])
                translate([gx, plug_y0 - 1.0, z_floor - e])
                    cube([guide_t, -gap - (plug_y0 - 1.0), z_top - z_floor + e]);
            // Anschlag oberhalb der Platine (Längsrichtung)
            translate([x0, H + gap, 0]) cube([x1 - x0, min_wall, board_t]);
            // Stützsäulen
            for (p = [[W / 2, H * 0.47], [W / 2, H * 0.78]])
                translate([p[0], p[1], z_floor - e]) cylinder(d = 3, h = below + e);
            // Magnetlaschen außen an den Längsseiten
            for (m = magnet_pos()) magnet_lug(m);
            for (cx = cable_x) cable_finger(cx);
            if (tab) for (t = [[x0 - wall, H * 0.75, -1], [x1 + wall, H * 0.25, 1]])
                translate([t[0], t[1], z_floor - floor])
                difference() {
                    translate([t[2] < 0 ? -9 : 0, -6, 0]) cube([9, 12, floor]);
                    translate([t[2] < 0 ? -6.5 : 2.5, -2.5, -1]) cube([4, 5, floor + 2]);
                }
        }
        // Magnetbohrungen: durchgehend, Magnet bündig mit der Unterseite
        for (m = magnet_pos())
            translate([m[0], m[1], z_floor - floor - 1])
                cylinder(d = magnet_d + magnet_fit, h = magnet_h + 2);
        snap_bumps(snap + 0.12);
    }
}

// --------------------------------------------------------------- Deckel
module deckel() {
    difference() {
        union() {
            // Deckel als flache Haube (Oberseite eben -> ohne Stützen druckbar)
            difference() {
                rrect(x0 - wall, y0 - wall, x1 + wall, y1 + wall, z_top, z_in + floor, wall);
                cavity_box(z_top - e, z_in);
            }
            // Steckrand innen
            difference() {
                translate([x0 + fit, y0 + fit, z_top - lip_h2])
                    cube([x1 - x0 - 2 * fit, y1 - y0 - 2 * fit, lip_h2 + e]);
                translate([x0 + fit + lip_t2, y0 + fit + lip_t2, z_top - lip_h2 - 1])
                    cube([x1 - x0 - 2 * fit - 2 * lip_t2, y1 - y0 - 2 * fit - 2 * lip_t2, lip_h2 + 2]);
            }
            snap_bumps(snap);
            // Andrückrippen
            // Rippen an den Seiten reichen bis an die Innenwand (Spiel überbrückt)
            for (s = press) {
                xa = s[0] <= 0 ? x0 : s[0];       xb = s[2] >= W ? x1 : s[2];
                ya = s[1] <= 0 ? -gap : s[1];     yb = s[3] >= H ? H + gap : s[3];
                translate([xa, ya, board_t]) cube([xb - xa, yb - ya, z_in - board_t + e]);
            }
            // Niederhalter über den äußeren Enden des Steckers (Mitte bleibt frei
            // für die Adern) – Stecker kann nicht abheben
            // (reichen nach außen über die Führungswände -> 2 mm+ breit)
            for (hx = [[guide_in0 - guide_t, rast_cx - 4.6], [rast_cx + 4.6, guide_in1 + guide_t]])
                translate([hx[0], plug_y0 + 0.3, plug_top + hold_gap])
                    cube([hx[1] - hx[0], plug_out - 0.6, z_in - plug_top - hold_gap + e]);
            // Lichtleiter-Röhrchen über den LEDs
            // (beginnen an der Trennebene: dort gehen sie in die Deckelwand über,
            //  berühren weder Funkmodul noch Steckrand)
            for (l = leds)
                translate([l[0], l[1], board_t + led_tube_z]) cylinder(d = led_tube_d, h = z_in - board_t - led_tube_z + e);
        }
        for (cx = cable_x) cable_slot(cx);
        // Steckrand über der USB-Buchse aussparen (Buchse sitzt bündig an der Kante)
        translate([x0 - 1, usb_y0 - 0.5, board_t - e]) cube([lip_t2 + fit + 1.2, usb_y1 - usb_y0 + 1, z_top - board_t + 2 * e]);
        // LEDs: Röhrchen innen hohl, oben dünne Restwand
        for (l = leds)
            translate([l[0], l[1], board_t + led_tube_z - e]) cylinder(d = 3.0, h = z_in + floor - led_skin - board_t - led_tube_z + e);
        // Beschriftung (0,4 mm vertieft, fette Schrift: Strichbreite > Düsendurchmesser; Restwand bleibt 2 mm)
        lbl = z_in + floor - 0.4;
        // Beschriftung zur Gehäusemitte hin (sonst läuft sie über den Rand)
        for (i = [0 : len(leds) - 1]) {
            left = leds[i][0] < W / 2;
            translate([leds[i][0] + (left ? 3.2 : -3.2), leds[i][1], lbl]) linear_extrude(1)
                text(led_names[i], size = 2.6, font = "DejaVu Sans:style=Bold", halign = left ? "left" : "right", valign = "center");
        }
        translate([W / 2 - 2, H * 0.45, lbl]) linear_extrude(1)
            text("MACS", size = 5.0, font = "DejaVu Sans:style=Bold", halign = "center", valign = "center");
    }
}

if (part == "unterteil") unterteil();
// Druckausrichtung: Deckel um die X-Achse DREHEN (nicht spiegeln!), Oberseite liegt auf dem Druckbett.
// Zum Montieren wird er wieder um die X-Achse umgedreht; USB-Aussparung und Schrift sitzen dann richtig.
else if (part == "deckel") translate([0, y1 + wall, z_in + floor]) rotate([180, 0, 0]) deckel();
else if (part == "deckel_montiert") deckel();
else { unterteil(); color("SteelBlue", 0.6) translate([0, 0, 25]) deckel(); }

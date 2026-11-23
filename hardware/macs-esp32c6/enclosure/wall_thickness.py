"""
Wandstärken-Prüfung für die Gehäuse-STLs (wie die DFM-Prüfung von JLC3DP).

Für zufällige Punkte auf der Oberfläche wird ein Strahl senkrecht ins
Material geschickt; der Abstand bis zur gegenüberliegenden Oberfläche ist die
lokale Wandstärke. Kanten und Ecken liefern dabei kleine Scheinwerte, deshalb
zählen nur Stellen, an denen mehrere benachbarte Messpunkte dünn sind.

Aufruf: python3 enclosure/wall_thickness.py [min_mm]
"""
import os
import sys

import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = {"Unterteil": os.path.join(HERE, "macs_gehaeuse_unterteil.stl"),
         "Deckel": os.path.join(HERE, "macs_gehaeuse_deckel.stl")}


def thickness(mesh, n=40000, seed=2):
    """Gibt (Punkte, Wandstärken) zurück; inf, wo kein Gegenüber gefunden wurde."""
    pts, fi = trimesh.sample.sample_surface_even(mesh, n, seed=seed)
    nrm = mesh.face_normals[fi]
    origins = pts - nrm * 1e-3
    dirs = -nrm
    loc, ray_idx, tri_idx = mesh.ray.intersects_location(origins, dirs, multiple_hits=False)
    t = np.full(len(pts), np.inf)
    d = np.linalg.norm(loc - origins[ray_idx], axis=1)
    # Treffer auf dem eigenen Dreieck ignorieren
    ok = tri_idx != fi[ray_idx]
    t[ray_idx[ok]] = d[ok]
    return pts, t


def thin_spots(mesh, min_mm, cluster=0.6, min_hits=6):
    """Dünne Stellen: Punkte unter min_mm, die mindestens min_hits dünne
    Nachbarn im Umkreis 'cluster' haben (Kanten-Scheinwerte fallen weg)."""
    pts, t = thickness(mesh)
    thin = pts[t < min_mm]
    if len(thin) == 0:
        return np.empty((0, 3)), t
    tree = trimesh.proximity.cKDTree(thin) if hasattr(trimesh.proximity, "cKDTree") else None
    if tree is None:
        from scipy.spatial import cKDTree
        tree = cKDTree(thin)
    counts = np.array([len(tree.query_ball_point(p, cluster)) for p in thin])
    return thin[counts >= min_hits], t


def main():
    min_mm = float(sys.argv[1]) if len(sys.argv) > 1 else 1.2
    bad = False
    for name, f in FILES.items():
        m = trimesh.load(f)
        spots, t = thin_spots(m, min_mm)
        fin = t[np.isfinite(t)]
        print(f"{name}: Median {np.median(fin):.2f} mm, 1%-Quantil {np.percentile(fin, 1):.2f} mm, "
              f"dünne Stellen < {min_mm} mm: {len(spots)}")
        if len(spots):
            bad = True
            lo, hi = spots.min(0), spots.max(0)
            print(f"   Bereich x {lo[0]:.1f}..{hi[0]:.1f}  y {lo[1]:.1f}..{hi[1]:.1f}  z {lo[2]:.1f}..{hi[2]:.1f}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

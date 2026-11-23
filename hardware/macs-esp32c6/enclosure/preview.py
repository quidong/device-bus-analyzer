"""Vorschaubild der Gehäuseteile (matplotlib, ohne Grafikserver).
Aufruf: python3 enclosure/preview.py <ausgabe.png>"""
import os, sys
import numpy as np
import trimesh
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

HERE = os.path.dirname(os.path.abspath(__file__))

def show(ax, mesh, color, title, elev, azim):
    mesh = mesh.copy(); mesh.fix_normals()
    tri = mesh.vertices[mesh.faces]
    n = mesh.face_normals
    light = np.clip(n @ np.array([0.4, -0.5, 0.8]) / np.linalg.norm([0.4, -0.5, 0.8]), 0, 1)
    base = np.array(matplotlib.colors.to_rgb(color))
    cols = np.clip(base[None, :] * (0.35 + 0.65 * light[:, None]), 0, 1)
    ax.add_collection3d(Poly3DCollection(tri, facecolors=cols, linewidths=0))
    lo, hi = mesh.bounds
    c = (lo + hi) / 2; r = (hi - lo).max() / 2
    ax.set_xlim(c[0]-r, c[0]+r); ax.set_ylim(c[1]-r, c[1]+r); ax.set_zlim(c[2]-r, c[2]+r)
    ax.view_init(elev=elev, azim=azim); ax.set_axis_off(); ax.set_title(title)

def main(out):
    u = trimesh.load(os.path.join(HERE, "macs_gehaeuse_unterteil.stl"))
    d = trimesh.load(os.path.join(HERE, "macs_gehaeuse_deckel.stl"))
    m = trimesh.load(os.path.join(HERE, "test", "deckel_montiert.stl"))
    import json
    bd = json.load(open(os.path.join(HERE, "board.json")))
    P, R = bd["P"], bd["rast"]
    def box(x0, y0, z0, x1, y1, z1):
        b = trimesh.creation.box(extents=[x1 - x0, y1 - y0, z1 - z0])
        b.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2]); return b
    pcb = box(0, 0, 0, bd["W"], bd["H"], P["board_t"])
    plug = box(R["cx"] - P["plug_w"] / 2, R["edge"] - P["plug_out"], P["plug_z0"],
               R["cx"] + P["plug_w"] / 2, R["edge"] + P["plug_on_board"], P["board_t"] + P["plug_above"])
    fig = plt.figure(figsize=(20, 7))
    ax = fig.add_subplot(1, 4, 1, projection="3d")
    show(ax, u, "#9aa7b1", "Unterteil", 40, -125)
    for mesh, col in ((pcb, "#2e7d32"), (plug, "#555555")):
        mm_ = mesh.copy(); tri = mm_.vertices[mm_.faces]
        ax.add_collection3d(Poly3DCollection(tri, facecolors=col, linewidths=0, alpha=0.9))
    ax.set_title("Unterteil mit Platine + RAST-Stecker")
    show(fig.add_subplot(1, 4, 2, projection="3d"), u, "#9aa7b1", "Unterteil leer", 40, -125)
    show(fig.add_subplot(1, 4, 3, projection="3d"), m, "#c9a227", "Deckel (Oberseite)", 40, -125)
    show(fig.add_subplot(1, 4, 4, projection="3d"), d, "#c9a227", "Deckel (Innenseite)", 40, -125)
    plt.tight_layout(); fig.savefig(out, dpi=110)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "vorschau.png"))

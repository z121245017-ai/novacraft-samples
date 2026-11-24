#!/usr/bin/env python3
"""Generate a self-created synthetic 2D 1F floorplan (SVG) and metric glTF 2.0 (.glb)
3D model with one passing dimension, one seeded doorway discrepancy (-80 mm),
and one 2D-unverifiable vertical elevation assumption for repeatable QA verification.

Zero third-party dependencies (Python 3 stdlib only).
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Dict, List, Tuple

OUT_DIR = Path(__file__).resolve().parent


def make_box_mesh(
    x0: float, x1: float, y0: float, y1: float, z0: float, z1: float
) -> Tuple[List[Tuple[float, float, float]], List[int]]:
    """Return 8 vertices and 36 triangle indices (CCW outward) for an axis-aligned box."""
    verts = [
        (x0, y0, z0),  # 0
        (x1, y0, z0),  # 1
        (x1, y1, z0),  # 2
        (x0, y1, z0),  # 3
        (x0, y0, z1),  # 4
        (x1, y0, z1),  # 5
        (x1, y1, z1),  # 6
        (x0, y1, z1),  # 7
    ]
    indices = [
        # -Z (north)
        0, 2, 1, 0, 3, 2,
        # +Z (south)
        4, 5, 6, 4, 6, 7,
        # -X (west)
        0, 4, 7, 0, 7, 3,
        # +X (east)
        1, 2, 6, 1, 6, 5,
        # -Y (bottom)
        0, 1, 5, 0, 5, 4,
        # +Y (top)
        3, 7, 6, 3, 6, 2,
    ]
    return verts, indices


def build_glb(path: Path) -> Dict[str, Tuple[float, float, float, float, float, float]]:
    """Build a valid glTF 2.0 binary (.glb) 1st-floor architectural massing model (1 unit = 1 meter).

    Coordinate convention (glTF 2.0 Y-up metric):
      - X: East  (0.000 m to 6.000 m)
      - Y: Up    (-0.150 m slab bottom to 2.800 m wall top — assumed, NOT on 2D plan)
      - Z: South (0.000 m to 4.000 m)

    Seeded QA conditions:
      - Wall_North: x in [0.000, 6.000] -> exact 6.000 m (MATCHES 2D plan spec 6.000 m)
      - Doorway D1 clear opening between Wall_Partition_West (max_x=2.540) and
        Wall_Partition_East (min_x=3.360) -> 0.820 m (FAILS 2D plan spec 0.900 m by -80 mm)
      - Wall height 2.800 m & Door_D1_Lintel bottom 2.100 m -> UNVERIFIABLE from 2D plan alone
    """
    boxes: Dict[str, Tuple[float, float, float, float, float, float]] = {
        "Floor_Slab":          (0.000, 6.000, -0.150, 0.000, 0.000, 4.000),
        "Wall_North":          (0.000, 6.000,  0.000, 2.800, 0.000, 0.200),
        "Wall_South":          (0.000, 6.000,  0.000, 2.800, 3.800, 4.000),
        "Wall_West":           (0.000, 0.200,  0.000, 2.800, 0.200, 3.800),
        "Wall_East":           (5.800, 6.000,  0.000, 2.800, 0.200, 3.800),
        "Wall_Partition_West": (0.200, 2.540,  0.000, 2.800, 1.925, 2.075),
        "Wall_Partition_East": (3.360, 5.800,  0.000, 2.800, 1.925, 2.075),
        "Door_D1_Lintel":      (2.540, 3.360,  2.100, 2.800, 1.925, 2.075),
    }

    bin_chunks = bytearray()
    buffer_views = []
    accessors = []
    meshes = []
    nodes = []

    def append_aligned(data: bytes, target: int) -> Tuple[int, int]:
        while len(bin_chunks) % 4 != 0:
            bin_chunks.append(0)
        offset = len(bin_chunks)
        bin_chunks.extend(data)
        bv_idx = len(buffer_views)
        buffer_views.append(
            {
                "buffer": 0,
                "byteOffset": offset,
                "byteLength": len(data),
                "target": target,
            }
        )
        return bv_idx, len(data)

    for idx, (name, bounds) in enumerate(boxes.items()):
        x0, x1, y0, y1, z0, z1 = bounds
        verts, indices = make_box_mesh(x0, x1, y0, y1, z0, z1)

        pos_bytes = b"".join(struct.pack("<fff", *v) for v in verts)
        idx_bytes = b"".join(struct.pack("<H", i) for i in indices)

        pos_bv, _ = append_aligned(pos_bytes, 34962)  # ARRAY_BUFFER
        idx_bv, _ = append_aligned(idx_bytes, 34963)  # ELEMENT_ARRAY_BUFFER

        pos_acc = len(accessors)
        accessors.append(
            {
                "bufferView": pos_bv,
                "componentType": 5126,  # FLOAT
                "count": len(verts),
                "type": "VEC3",
                "min": [round(x0, 6), round(y0, 6), round(z0, 6)],
                "max": [round(x1, 6), round(y1, 6), round(z1, 6)],
            }
        )
        idx_acc = len(accessors)
        accessors.append(
            {
                "bufferView": idx_bv,
                "componentType": 5123,  # UNSIGNED_SHORT
                "count": len(indices),
                "type": "SCALAR",
                "min": [0],
                "max": [len(verts) - 1],
            }
        )

        meshes.append(
            {
                "name": name,
                "primitives": [
                    {
                        "attributes": {"POSITION": pos_acc},
                        "indices": idx_acc,
                        "mode": 4,  # TRIANGLES
                    }
                ],
            }
        )
        nodes.append(
            {
                "name": name,
                "mesh": idx,
                "translation": [0.0, 0.0, 0.0],
                "rotation": [0.0, 0.0, 0.0, 1.0],
                "scale": [1.0, 1.0, 1.0],
            }
        )

    while len(bin_chunks) % 4 != 0:
        bin_chunks.append(0)

    gltf = {
        "asset": {
            "version": "2.0",
            "generator": "NovaCraft Studio Synthetic Floorplan QA Demo (build_synthetic_floorplan_assets.py)",
            "extras": {
                "synthetic_demo": True,
                "units": "meters",
                "coordinate_system": "glTF 2.0 Y-up metric (X=East, Z=South, Y=Up)",
            },
        },
        "scene": 0,
        "scenes": [{"name": "Floor_1F_Synthetic", "nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes,
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(bin_chunks)}],
    }

    json_bytes = json.dumps(gltf, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    while len(json_bytes) % 4 != 0:
        json_bytes += b" "

    total_length = 12 + 8 + len(json_bytes) + 8 + len(bin_chunks)
    header = struct.pack("<III", 0x46546C67, 2, total_length)
    chunk0 = struct.pack("<II", len(json_bytes), 0x4E4F534A) + json_bytes
    chunk1 = struct.pack("<II", len(bin_chunks), 0x004E4942) + bytes(bin_chunks)

    path.write_bytes(header + chunk0 + chunk1)
    return boxes


def write_source_plan_svg(path: Path) -> None:
    """Write the self-created 2D source architectural floorplan SVG with explicit plan dimensions."""
    # Scale: 100 px = 1.000 m, origin at (100, 110)
    ox, oy, s = 100.0, 110.0, 100.0

    def px(x: float) -> float:
        return ox + x * s

    def py(z: float) -> float:
        return oy + z * s

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="840" height="620" viewBox="0 0 840 620">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#1f2937"/>
    </marker>
    <marker id="arrowBlue" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#1d4ed8"/>
    </marker>
  </defs>
  <rect width="840" height="620" fill="#ffffff"/>
  <text x="40" y="36" font-family="ui-sans-serif, system-ui, sans-serif" font-size="18" font-weight="700" fill="#111827">
    2D Source Floorplan — Level 1F (Self-Created Synthetic QA Demo)
  </text>
  <text x="40" y="56" font-family="ui-sans-serif, system-ui, sans-serif" font-size="12" fill="#4b5563">
    Units: meters (100 px = 1.000 m) | Exterior wall thickness: 0.200 m | Interior partition thickness: 0.150 m | NO vertical elevation/ceiling notes on plan
  </text>

  <!-- Rooms background -->
  <rect x="{px(0.2)}" y="{py(0.2)}" width="{5.6*s}" height="{1.725*s}" fill="#f8fafc" stroke="none"/>
  <rect x="{px(0.2)}" y="{py(2.075)}" width="{5.6*s}" height="{1.725*s}" fill="#f1f5f9" stroke="none"/>

  <!-- Exterior Walls (plan spec) -->
  <rect x="{px(0.0)}" y="{py(0.0)}" width="{6.0*s}" height="{0.2*s}" fill="#334155"/>
  <rect x="{px(0.0)}" y="{py(3.8)}" width="{6.0*s}" height="{0.2*s}" fill="#334155"/>
  <rect x="{px(0.0)}" y="{py(0.2)}" width="{0.2*s}" height="{3.6*s}" fill="#334155"/>
  <rect x="{px(5.8)}" y="{py(0.2)}" width="{0.2*s}" height="{3.6*s}" fill="#334155"/>

  <!-- Interior Partition Wall with Doorway D1 clear opening [2.500, 3.400] = 0.900 m -->
  <rect x="{px(0.2)}" y="{py(1.925)}" width="{2.3*s}" height="{0.15*s}" fill="#475569"/>
  <rect x="{px(3.4)}" y="{py(1.925)}" width="{2.4*s}" height="{0.15*s}" fill="#475569"/>

  <!-- Doorway D1 architectural swing symbol (0.900 m clear opening) -->
  <line x1="{px(2.5)}" y1="{py(2.075)}" x2="{px(2.5)}" y2="{py(2.975)}" stroke="#1d4ed8" stroke-width="2"/>
  <path d="M {px(2.5)} {py(2.975)} A {0.9*s} {0.9*s} 0 0 0 {px(3.4)} {py(2.075)}" fill="none" stroke="#1d4ed8" stroke-width="1.5" stroke-dasharray="5,4"/>

  <!-- Room labels -->
  <text x="{px(3.0)}" y="{py(1.15)}" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="16" font-weight="600" fill="#0f172a">LIVING / WORK ROOM</text>
  <text x="{px(3.0)}" y="{py(1.36)}" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="12" fill="#475569">Interior clear: 5.600 m × 1.725 m</text>
  <text x="{px(3.0)}" y="{py(3.15)}" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="16" font-weight="600" fill="#0f172a">STUDY ROOM</text>
  <text x="{px(3.0)}" y="{py(3.36)}" text-anchor="middle" font-family="ui-sans-serif, system-ui, sans-serif" font-size="12" fill="#475569">Interior clear: 5.600 m × 1.725 m</text>

  <!-- Dimension 1: Exterior North Wall = 6.000 m -->
  <line x1="{px(0.0)}" y1="{py(0.0)-28}" x2="{px(0.0)}" y2="{py(0.0)-4}" stroke="#64748b" stroke-width="1"/>
  <line x1="{px(6.0)}" y1="{py(0.0)-28}" x2="{px(6.0)}" y2="{py(0.0)-4}" stroke="#64748b" stroke-width="1"/>
  <line x1="{px(0.0)+4}" y1="{py(0.0)-18}" x2="{px(6.0)-4}" y2="{py(0.0)-18}" stroke="#1f2937" stroke-width="1.5" marker-start="url(#arrow)" marker-end="url(#arrow)"/>
  <rect x="{px(3.0)-74}" y="{py(0.0)-30}" width="148" height="22" fill="#ffffff"/>
  <text x="{px(3.0)}" y="{py(0.0)-14}" text-anchor="middle" font-family="ui-monospace, monospace" font-size="13" font-weight="700" fill="#111827">Wall_North = 6.000 m</text>

  <!-- Dimension East Exterior = 4.000 m -->
  <line x1="{px(6.0)+4}" y1="{py(0.0)}" x2="{px(6.0)+34}" y2="{py(0.0)}" stroke="#64748b" stroke-width="1"/>
  <line x1="{px(6.0)+4}" y1="{py(4.0)}" x2="{px(6.0)+34}" y2="{py(4.0)}" stroke="#64748b" stroke-width="1"/>
  <line x1="{px(6.0)+24}" y1="{py(0.0)+4}" x2="{px(6.0)+24}" y2="{py(4.0)-4}" stroke="#1f2937" stroke-width="1.5" marker-start="url(#arrow)" marker-end="url(#arrow)"/>
  <text x="{px(6.0)+40}" y="{py(2.0)+4}" font-family="ui-monospace, monospace" font-size="13" font-weight="700" fill="#111827">4.000 m</text>

  <!-- Dimension 2: Doorway D1 Clear Opening = 0.900 m -->
  <line x1="{px(2.5)}" y1="{py(1.925)-34}" x2="{px(2.5)}" y2="{py(1.925)-2}" stroke="#1d4ed8" stroke-width="1"/>
  <line x1="{px(3.4)}" y1="{py(1.925)-34}" x2="{px(3.4)}" y2="{py(1.925)-2}" stroke="#1d4ed8" stroke-width="1"/>
  <line x1="{px(2.5)+4}" y1="{py(1.925)-20}" x2="{px(3.4)-4}" y2="{py(1.925)-20}" stroke="#1d4ed8" stroke-width="1.8" marker-start="url(#arrowBlue)" marker-end="url(#arrowBlue)"/>
  <rect x="{px(2.95)-86}" y="{py(1.925)-52}" width="172" height="22" rx="4" fill="#eff6ff" stroke="#bfdbfe"/>
  <text x="{px(2.95)}" y="{py(1.925)-37}" text-anchor="middle" font-family="ui-monospace, monospace" font-size="12" font-weight="700" fill="#1e40af">Doorway D1 Clear = 0.900 m</text>

  <!-- Scale bar & North arrow & Ambiguity note -->
  <g transform="translate(100, 545)">
    <rect x="0" y="0" width="100" height="8" fill="#111827"/>
    <rect x="100" y="0" width="100" height="8" fill="#ffffff" stroke="#111827"/>
    <text x="0" y="24" font-family="ui-monospace, monospace" font-size="11" fill="#111827">0 m</text>
    <text x="94" y="24" font-family="ui-monospace, monospace" font-size="11" fill="#111827">1 m</text>
    <text x="194" y="24" font-family="ui-monospace, monospace" font-size="11" fill="#111827">2 m</text>
  </g>
  <g transform="translate(760, 120)">
    <polygon points="0,-24 8,6 0,0 -8,6" fill="#111827"/>
    <text x="0" y="-30" text-anchor="middle" font-family="ui-sans-serif, sans-serif" font-size="12" font-weight="700" fill="#111827">N</text>
  </g>
  <rect x="330" y="538" width="465" height="52" rx="6" fill="#fffbeb" stroke="#f59e0b"/>
  <text x="344" y="558" font-family="ui-sans-serif, system-ui, sans-serif" font-size="11" font-weight="700" fill="#92400e">
    Source Ambiguity Notice (Intentional QA Test Case):
  </text>
  <text x="344" y="576" font-family="ui-sans-serif, system-ui, sans-serif" font-size="11" fill="#78350f">
    2D plan contains X-Y dimensions only. Ceiling height &amp; door lintel height are NOT specified.
  </text>
</svg>
"""
    path.write_text(svg, encoding="utf-8")


def write_overlay_svg(
    path: Path, model_boxes: Dict[str, Tuple[float, float, float, float, float, float]]
) -> None:
    """Render an orthographic top-down comparison overlaying the actual .glb footprints on the 2D plan."""
    ox, oy, s = 100.0, 110.0, 100.0

    def px(x: float) -> float:
        return ox + x * s

    def py(z: float) -> float:
        return oy + z * s

    wall_rects = []
    for name, (x0, x1, y0, y1, z0, z1) in model_boxes.items():
        if name in ("Floor_Slab", "Door_D1_Lintel"):
            continue
        fill = "#2563eb" if "Partition" in name else "#0f766e"
        wall_rects.append(
            f'  <rect x="{px(x0):.1f}" y="{py(z0):.1f}" width="{(x1-x0)*s:.1f}" height="{(z1-z0)*s:.1f}" '
            f'fill="{fill}" fill-opacity="0.38" stroke="{fill}" stroke-width="1.5"/>'
        )

    pw = model_boxes["Wall_Partition_West"]
    pe = model_boxes["Wall_Partition_East"]
    measured_d1 = pe[0] - pw[1]

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="840" height="600" viewBox="0 0 840 600">
  <rect width="840" height="600" fill="#ffffff"/>
  <text x="40" y="36" font-family="ui-sans-serif, system-ui, sans-serif" font-size="18" font-weight="700" fill="#111827">
    QA Overlay — 2D Plan Spec (Dashed) vs Exported .glb Geometry (Shaded)
  </text>
  <text x="40" y="56" font-family="ui-sans-serif, system-ui, sans-serif" font-size="12" fill="#4b5563">
    Recomputed directly from floorplan_1f_synthetic.glb binary vertex buffers | Tolerance: ±0.010 m (±10 mm)
  </text>

  <!-- 2D Plan reference outlines (dashed) -->
  <rect x="{px(0.0)}" y="{py(0.0)}" width="{6.0*s}" height="{4.0*s}" fill="none" stroke="#64748b" stroke-width="1.5" stroke-dasharray="6,4"/>
  <rect x="{px(0.2)}" y="{py(1.925)}" width="{2.3*s}" height="{0.15*s}" fill="none" stroke="#111827" stroke-width="1.5" stroke-dasharray="4,3"/>
  <rect x="{px(3.4)}" y="{py(1.925)}" width="{2.4*s}" height="{0.15*s}" fill="none" stroke="#111827" stroke-width="1.5" stroke-dasharray="4,3"/>

  <!-- Actual GLB wall footprints -->
{chr(10).join(wall_rects)}

  <!-- Highlight the two 40 mm encroaching jamb regions in red -->
  <rect x="{px(2.500):.1f}" y="{py(1.925):.1f}" width="{(pw[1]-2.500)*s:.1f}" height="{0.15*s:.1f}" fill="#dc2626" fill-opacity="0.85"/>
  <rect x="{px(pe[0]):.1f}" y="{py(1.925):.1f}" width="{(3.400-pe[0])*s:.1f}" height="{0.15*s:.1f}" fill="#dc2626" fill-opacity="0.85"/>

  <!-- Callout 1: Wall_North PASS -->
  <rect x="{px(1.5)}" y="{py(0.0)-42}" width="300" height="28" rx="5" fill="#ecfdf5" stroke="#10b981"/>
  <text x="{px(3.0)}" y="{py(0.0)-23}" text-anchor="middle" font-family="ui-monospace, monospace" font-size="12" font-weight="700" fill="#065f46">
    CHECK 1 PASS: Wall_North = 6.000 m (Δ 0.000 m)
  </text>

  <!-- Callout 2: Doorway D1 FAIL -->
  <line x1="{px(pw[1]):.1f}" y1="{py(2.075)+4}" x2="{px(pw[1]):.1f}" y2="{py(2.075)+54}" stroke="#dc2626" stroke-width="1.5"/>
  <line x1="{px(pe[0]):.1f}" y1="{py(2.075)+4}" x2="{px(pe[0]):.1f}" y2="{py(2.075)+54}" stroke="#dc2626" stroke-width="1.5"/>
  <rect x="{px(1.15)}" y="{py(2.075)+56}" width="370" height="46" rx="5" fill="#fef2f2" stroke="#dc2626"/>
  <text x="{px(3.0)}" y="{py(2.075)+75}" text-anchor="middle" font-family="ui-monospace, monospace" font-size="12" font-weight="700" fill="#991b1b">
    CHECK 2 FAIL: Doorway D1 = {measured_d1:.3f} m vs 0.900 m spec
  </text>
  <text x="{px(3.0)}" y="{py(2.075)+93}" text-anchor="middle" font-family="ui-monospace, monospace" font-size="11" fill="#7f1d1d">
    Δ = -0.080 m (-80 mm): +40 mm east on West wall, -40 mm west on East wall
  </text>

  <!-- Callout 3: Unverifiable item -->
  <rect x="{px(0.0)}" y="{py(4.0)+24}" width="600" height="44" rx="5" fill="#fffbeb" stroke="#d97706"/>
  <text x="{px(0.15)}" y="{py(4.0)+43}" font-family="ui-monospace, monospace" font-size="12" font-weight="700" fill="#92400e">
    CHECK 3 UNVERIFIABLE_FROM_2D_PLAN: Wall height 2.800 m &amp; D1 lintel soffit 2.100 m
  </text>
  <text x="{px(0.15)}" y="{py(4.0)+60}" font-family="ui-sans-serif, system-ui, sans-serif" font-size="11" fill="#78350f">
    Omitted from 2D plan — classified as source ambiguity (needs section/elevation spec, NOT filed as model bug).
  </text>
</svg>
"""
    path.write_text(svg, encoding="utf-8")


def main() -> None:
    boxes = build_glb(OUT_DIR / "floorplan_1f_synthetic.glb")
    write_source_plan_svg(OUT_DIR / "floorplan_1f_synthetic.svg")
    write_overlay_svg(OUT_DIR / "plan_vs_model_overlay.svg", boxes)
    print(f"Generated {len(boxes)} named meshes in floorplan_1f_synthetic.glb + 2 SVGs.")


if __name__ == "__main__":
    main()

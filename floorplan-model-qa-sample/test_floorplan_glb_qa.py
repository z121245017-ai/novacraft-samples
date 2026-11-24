#!/usr/bin/env python3
"""Unit tests verifying independent recomputation of the synthetic 1F floorplan-to-GLB QA demo."""

import unittest
from pathlib import Path

from verify_floorplan_glb_qa import parse_glb, run_qa

HERE = Path(__file__).resolve().parent
GLB_PATH = HERE / "floorplan_1f_synthetic.glb"


class TestFloorplanGlbQa(unittest.TestCase):
    def test_glb_binary_header_and_mesh_count(self):
        gltf, bin_data = parse_glb(GLB_PATH)
        self.assertEqual(gltf["asset"]["version"], "2.0")
        self.assertEqual(len(gltf["nodes"]), 8)
        self.assertGreater(len(bin_data), 0)

    def test_rule_out_display_and_hidden_geometry(self):
        res = run_qa(GLB_PATH)
        ro = res["rule_out_display_and_hidden_geometry"]
        self.assertTrue(ro["all_nodes_unit_scale"])
        self.assertTrue(ro["all_nodes_identity_rotation"])
        self.assertEqual(ro["unexpected_meshes_inside_d1_opening_below_2m"], [])
        self.assertEqual(ro["floor_slab_span_m"], [6.0, 4.0])

    def test_chk01_north_wall_passes_exactly(self):
        res = run_qa(GLB_PATH)
        chk1 = res["checks"][0]
        self.assertEqual(chk1["id"], "CHK-01")
        self.assertEqual(chk1["status"], "PASS")
        self.assertAlmostEqual(chk1["model_measured_m"], 6.000, places=4)
        self.assertAlmostEqual(chk1["delta_m"], 0.000, places=4)

    def test_chk02_doorway_d1_catches_seeded_80mm_constriction(self):
        res = run_qa(GLB_PATH)
        chk2 = res["checks"][1]
        self.assertEqual(chk2["id"], "CHK-02")
        self.assertEqual(chk2["status"], "FAIL")
        self.assertAlmostEqual(chk2["model_measured_m"], 0.820, places=4)
        self.assertAlmostEqual(chk2["delta_m"], -0.080, places=4)
        self.assertEqual(chk2["evidence"]["west_jamb_max_x_m"], 2.54)
        self.assertEqual(chk2["evidence"]["east_jamb_min_x_m"], 3.36)

    def test_chk03_vertical_elevation_marked_unverifiable_not_pass_or_fail(self):
        res = run_qa(GLB_PATH)
        chk3 = res["checks"][2]
        self.assertEqual(chk3["id"], "CHK-03")
        self.assertEqual(chk3["status"], "UNVERIFIABLE_FROM_2D_PLAN")
        self.assertIsNone(chk3["plan_spec_m"])
        self.assertEqual(chk3["model_assumed_values_m"]["wall_extrusion_height_m"], 2.8)
        self.assertEqual(chk3["model_assumed_values_m"]["door_d1_lintel_soffit_m"], 2.1)


if __name__ == "__main__":
    unittest.main()

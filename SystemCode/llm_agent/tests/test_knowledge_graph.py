"""Tests for knowledge_graph.py — SceneKnowledgeGraph."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from knowledge_graph import (
    SceneKnowledgeGraph,
    ObjectNode,
    build_default_scene,
    REL_ON,
    REL_STACKED,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def empty_kg():
    return SceneKnowledgeGraph()


@pytest.fixture
def simple_kg():
    kg = SceneKnowledgeGraph()
    kg.add_robot("franka")
    kg.add_location("zone_a")
    kg.add_location("zone_b")
    kg.add_object(ObjectNode("red_cube"))
    kg.set_on("red_cube", "zone_a")
    kg.set_robot_at("franka", "zone_a")
    return kg


# ── Node management ───────────────────────────────────────────────────────────

class TestNodeManagement:
    def test_add_robot(self, empty_kg):
        empty_kg.add_robot("franka")
        assert "franka" in empty_kg.robots()

    def test_add_location(self, empty_kg):
        empty_kg.add_location("zone_a")
        assert "zone_a" in empty_kg.locations()

    def test_add_object(self, empty_kg):
        empty_kg.add_robot("franka")
        empty_kg.add_object(ObjectNode("cube"))
        assert "cube" in empty_kg.objects()

    def test_object_properties(self, empty_kg):
        empty_kg.add_robot("franka")
        empty_kg.add_object(ObjectNode("glass", fragile=True, heavy=False))
        assert empty_kg.is_fragile("glass")
        assert not empty_kg.is_heavy("glass")

    def test_heavy_object(self, empty_kg):
        empty_kg.add_robot("franka")
        empty_kg.add_object(ObjectNode("brick", heavy=True))
        assert empty_kg.is_heavy("brick")


# ── Spatial relations ─────────────────────────────────────────────────────────

class TestSpatialRelations:
    def test_set_on(self, simple_kg):
        assert simple_kg.get_location_of("red_cube") == "zone_a"

    def test_missing_node_raises(self, simple_kg):
        with pytest.raises(ValueError):
            simple_kg.set_on("nonexistent", "zone_a")

    def test_clear_default(self, simple_kg):
        assert simple_kg.is_clear("red_cube")

    def test_stack_marks_bottom_not_clear(self, empty_kg):
        empty_kg.add_robot("franka")
        empty_kg.add_location("zone_a")
        empty_kg.add_object(ObjectNode("bottom"))
        empty_kg.add_object(ObjectNode("top"))
        empty_kg.set_on("bottom", "zone_a")
        empty_kg.set_on("top", "zone_a")
        empty_kg.set_stacked("top", "bottom")
        assert not empty_kg.is_clear("bottom")
        assert empty_kg.is_clear("top")

    def test_unstack_restores_clear(self, empty_kg):
        empty_kg.add_robot("franka")
        empty_kg.add_location("zone_a")
        empty_kg.add_object(ObjectNode("bottom"))
        empty_kg.add_object(ObjectNode("top"))
        empty_kg.set_on("bottom", "zone_a")
        empty_kg.set_on("top", "zone_a")
        empty_kg.set_stacked("top", "bottom")
        empty_kg.unset_stacked("top", "bottom")
        assert empty_kg.is_clear("bottom")


# ── scene_context export / import roundtrip ───────────────────────────────────

class TestSceneContext:
    def test_to_scene_context_keys(self, simple_kg):
        ctx = simple_kg.to_scene_context()
        assert "robot" in ctx
        assert "objects" in ctx
        assert "locations" in ctx

    def test_to_scene_context_robot(self, simple_kg):
        ctx = simple_kg.to_scene_context()
        assert ctx["robot"] == "franka"

    def test_to_scene_context_objects(self, simple_kg):
        ctx = simple_kg.to_scene_context()
        names = [o["name"] for o in ctx["objects"]]
        assert "red_cube" in names

    def test_to_scene_context_location(self, simple_kg):
        ctx = simple_kg.to_scene_context()
        obj = next(o for o in ctx["objects"] if o["name"] == "red_cube")
        assert obj["at"] == "zone_a"

    def test_roundtrip(self, simple_kg):
        ctx = simple_kg.to_scene_context()
        kg2 = SceneKnowledgeGraph.from_scene_context(ctx)
        assert kg2.get_location_of("red_cube") == "zone_a"
        assert "franka" in kg2.robots()

    def test_fragile_propagated(self):
        ctx = {
            "robot": "franka",
            "objects": [{"name": "glass", "fragile": True, "at": "zone_a"}],
            "locations": ["zone_a"],
        }
        kg = SceneKnowledgeGraph.from_scene_context(ctx)
        assert kg.is_fragile("glass")

    def test_heavy_propagated(self):
        ctx = {
            "robot": "franka",
            "objects": [{"name": "brick", "heavy": True, "at": "zone_a"}],
            "locations": ["zone_a"],
        }
        kg = SceneKnowledgeGraph.from_scene_context(ctx)
        assert kg.is_heavy("brick")


# ── apply_action ──────────────────────────────────────────────────────────────

class TestApplyAction:
    @pytest.fixture
    def action_kg(self):
        kg = SceneKnowledgeGraph()
        kg.add_robot("franka")
        kg.add_location("zone_a")
        kg.add_location("zone_b")
        kg.add_object(ObjectNode("red_cube"))
        kg.set_on("red_cube", "zone_a")
        kg.set_robot_at("franka", "zone_a")
        return kg

    def test_pick_clears_location(self, action_kg):
        action_kg.apply_action("pick(franka,red_cube,zone_a)")
        assert action_kg.get_location_of("red_cube") is None

    def test_place_sets_location(self, action_kg):
        action_kg.apply_action("pick(franka,red_cube,zone_a)")
        action_kg.apply_action("place(franka,red_cube,zone_b)")
        assert action_kg.get_location_of("red_cube") == "zone_b"

    def test_stack_marks_bottom_occupied(self, action_kg):
        action_kg.add_object(ObjectNode("blue_cylinder"))
        action_kg.set_on("blue_cylinder", "zone_b")
        action_kg.apply_action("pick(franka,red_cube,zone_a)")
        action_kg.apply_action("stack(franka,red_cube,blue_cylinder,zone_b)")
        assert not action_kg.is_clear("blue_cylinder")

    def test_unstack_frees_bottom(self, action_kg):
        action_kg.add_object(ObjectNode("blue_cylinder"))
        action_kg.set_on("blue_cylinder", "zone_b")
        action_kg.apply_action("pick(franka,red_cube,zone_a)")
        action_kg.apply_action("stack(franka,red_cube,blue_cylinder,zone_b)")
        action_kg.apply_action("unstack(franka,red_cube,blue_cylinder,zone_b)")
        assert action_kg.is_clear("blue_cylinder")


# ── build_default_scene ───────────────────────────────────────────────────────

class TestBuildDefaultScene:
    def test_has_three_objects(self):
        kg = build_default_scene()
        assert len(kg.objects()) == 3

    def test_has_three_zones(self):
        kg = build_default_scene()
        assert len(kg.locations()) == 3

    def test_fragile_sphere(self):
        kg = build_default_scene()
        assert kg.is_fragile("green_sphere")

    def test_robot_present(self):
        kg = build_default_scene()
        assert "franka" in kg.robots()

    def test_repr(self):
        kg = build_default_scene()
        r = repr(kg)
        assert "SceneKnowledgeGraph" in r
        assert "nodes=" in r

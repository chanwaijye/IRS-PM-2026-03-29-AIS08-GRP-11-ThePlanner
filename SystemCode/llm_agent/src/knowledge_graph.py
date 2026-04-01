"""knowledge_graph.py — Scene Knowledge Graph for ThePlanner.

Maintains a NetworkX directed graph of objects, locations, and the robot.
Nodes: objects (cube/cylinder/sphere), locations (zones, table), robot.
Edges: affordances (graspable, stackable), properties (heavy, fragile),
       and spatial relations (on, at, in_zone, stacked_on).

Used by Agent 1 to build the scene_context dict for nl_to_pddl.py,
and by Agent 3 (monitor) to track world-state changes post-execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import networkx as nx


# ── Node types ────────────────────────────────────────────────────────────

ROBOT_TYPE    = "robot"
OBJECT_TYPE   = "object"
LOCATION_TYPE = "location"

# ── Edge relation labels ──────────────────────────────────────────────────

REL_ON        = "on"          # object → location
REL_IN_ZONE   = "in_zone"     # object → location
REL_AT        = "at"          # robot  → location
REL_STACKED   = "stacked_on"  # obj_top → obj_bottom
REL_GRASPABLE = "graspable"   # object → robot (affordance)
REL_STACKABLE = "stackable"   # obj_top → obj_bottom (affordance)


@dataclass
class ObjectNode:
    name: str
    obj_type: str = OBJECT_TYPE          # robot | object | location
    heavy: bool   = False
    fragile: bool = False
    clear: bool   = True
    extra: dict[str, Any] = field(default_factory=dict)


class SceneKnowledgeGraph:
    """Directed knowledge graph for one scene snapshot."""

    def __init__(self) -> None:
        self._g: nx.DiGraph = nx.DiGraph()

    # ── Node management ───────────────────────────────────────────────────

    def add_robot(self, name: str) -> None:
        self._g.add_node(name, obj_type=ROBOT_TYPE, hand_empty=True)

    def add_location(self, name: str) -> None:
        self._g.add_node(name, obj_type=LOCATION_TYPE)

    def add_object(self, node: ObjectNode) -> None:
        self._g.add_node(
            node.name,
            obj_type=node.obj_type,
            heavy=node.heavy,
            fragile=node.fragile,
            clear=node.clear,
            **node.extra,
        )

    # ── Spatial relation edges ────────────────────────────────────────────

    def set_on(self, obj: str, loc: str) -> None:
        self._require(obj, loc)
        self._g.add_edge(obj, loc, rel=REL_ON)
        self._g.add_edge(obj, loc, rel=REL_IN_ZONE)

    def set_robot_at(self, robot: str, loc: str) -> None:
        self._require(robot, loc)
        self._g.add_edge(robot, loc, rel=REL_AT)

    def set_stacked(self, obj_top: str, obj_bottom: str) -> None:
        self._require(obj_top, obj_bottom)
        self._g.add_edge(obj_top, obj_bottom, rel=REL_STACKED)
        self._g.nodes[obj_bottom]["clear"] = False

    def unset_stacked(self, obj_top: str, obj_bottom: str) -> None:
        if self._g.has_edge(obj_top, obj_bottom):
            self._g.remove_edge(obj_top, obj_bottom)
        self._g.nodes[obj_bottom]["clear"] = True

    # ── Affordance edges ──────────────────────────────────────────────────

    def mark_graspable(self, obj: str, robot: str) -> None:
        self._require(obj, robot)
        self._g.add_edge(obj, robot, rel=REL_GRASPABLE)

    def mark_stackable(self, top: str, bottom: str) -> None:
        self._require(top, bottom)
        self._g.add_edge(top, bottom, rel=REL_STACKABLE)

    # ── Queries ───────────────────────────────────────────────────────────

    def objects(self) -> list[str]:
        return [n for n, d in self._g.nodes(data=True)
                if d.get("obj_type") == OBJECT_TYPE]

    def locations(self) -> list[str]:
        return [n for n, d in self._g.nodes(data=True)
                if d.get("obj_type") == LOCATION_TYPE]

    def robots(self) -> list[str]:
        return [n for n, d in self._g.nodes(data=True)
                if d.get("obj_type") == ROBOT_TYPE]

    def get_location_of(self, obj: str) -> str | None:
        for _, tgt, data in self._g.out_edges(obj, data=True):
            if data.get("rel") == REL_ON:
                return tgt
        return None

    def is_clear(self, obj: str) -> bool:
        return bool(self._g.nodes[obj].get("clear", True))

    def is_fragile(self, obj: str) -> bool:
        return bool(self._g.nodes[obj].get("fragile", False))

    def is_heavy(self, obj: str) -> bool:
        return bool(self._g.nodes[obj].get("heavy", False))

    # ── Export: scene_context dict (input for nl_to_pddl) ─────────────────

    def to_scene_context(self) -> dict[str, Any]:
        robots = self.robots()
        robot  = robots[0] if robots else "franka"

        objects_list: list[dict[str, Any]] = []
        for name in self.objects():
            entry: dict[str, Any] = {"name": name, "type": "object"}
            loc = self.get_location_of(name)
            if loc:
                entry["at"] = loc
            nd = self._g.nodes[name]
            if nd.get("fragile"):
                entry["fragile"] = True
            if nd.get("heavy"):
                entry["heavy"] = True
            if not nd.get("clear", True):
                entry["clear"] = False
            objects_list.append(entry)

        return {
            "robot": robot,
            "objects": objects_list,
            "locations": self.locations(),
        }

    # ── Import: build graph from scene_context dict ───────────────────────

    @classmethod
    def from_scene_context(cls, ctx: dict[str, Any]) -> "SceneKnowledgeGraph":
        kg = cls()
        robot = ctx.get("robot", "franka")
        kg.add_robot(robot)
        for loc in ctx.get("locations", []):
            kg.add_location(loc)
        for obj in ctx.get("objects", []):
            node = ObjectNode(
                name=obj["name"],
                heavy=obj.get("heavy", False),
                fragile=obj.get("fragile", False),
                clear=obj.get("clear", True),
            )
            kg.add_object(node)
            if "at" in obj:
                kg.set_on(obj["name"], obj["at"])
            kg.mark_graspable(obj["name"], robot)
        return kg

    # ── State update: apply a planner action ─────────────────────────────

    def apply_action(self, action_name: str) -> None:
        """Update graph state after a planner action string like 'pick(franka,red_cube,zone_a)'."""
        m_pick    = action_name.startswith("pick(")
        m_place   = action_name.startswith("place(")
        m_stack   = action_name.startswith("stack(")
        m_unstack = action_name.startswith("unstack(")

        args = action_name.split("(", 1)[-1].rstrip(")").split(",")

        if m_pick and len(args) >= 3:
            robot, obj, loc = args[0], args[1], args[2]
            # Remove on/in_zone edges
            if self._g.has_edge(obj, loc):
                self._g.remove_edge(obj, loc)
            if robot in self._g.nodes:
                self._g.nodes[robot]["hand_empty"] = False

        elif m_place and len(args) >= 3:
            robot, obj, loc = args[0], args[1], args[2]
            self.set_on(obj, loc)
            self._g.nodes[obj]["clear"] = True
            if robot in self._g.nodes:
                self._g.nodes[robot]["hand_empty"] = True

        elif m_stack and len(args) >= 4:
            robot, top, bottom, loc = args[0], args[1], args[2], args[3]
            self.set_stacked(top, bottom)
            self.set_on(top, loc)
            if robot in self._g.nodes:
                self._g.nodes[robot]["hand_empty"] = True

        elif m_unstack and len(args) >= 4:
            robot, top, bottom, _loc = args[0], args[1], args[2], args[3]
            self.unset_stacked(top, bottom)
            if robot in self._g.nodes:
                self._g.nodes[robot]["hand_empty"] = False

    # ── Internal helpers ──────────────────────────────────────────────────

    def _require(self, *names: str) -> None:
        for n in names:
            if n not in self._g.nodes:
                raise ValueError(f"Node '{n}' not found in knowledge graph")

    def __repr__(self) -> str:
        return (f"SceneKnowledgeGraph("
                f"nodes={self._g.number_of_nodes()}, "
                f"edges={self._g.number_of_edges()})")


# ── Convenience factory ───────────────────────────────────────────────────

def build_default_scene() -> SceneKnowledgeGraph:
    """Build the default three-zone tabletop scene used in unit tests."""
    kg = SceneKnowledgeGraph()
    kg.add_robot("franka")
    for zone in ["zone_a", "zone_b", "zone_c"]:
        kg.add_location(zone)
    kg.add_object(ObjectNode("red_cube"))
    kg.add_object(ObjectNode("blue_cylinder"))
    kg.add_object(ObjectNode("green_sphere", fragile=True))
    kg.set_on("red_cube", "zone_a")
    kg.set_on("blue_cylinder", "zone_b")
    kg.set_on("green_sphere", "zone_c")
    kg.set_robot_at("franka", "zone_a")
    for obj in ["red_cube", "blue_cylinder", "green_sphere"]:
        kg.mark_graspable(obj, "franka")
    return kg


if __name__ == "__main__":
    import json
    kg = build_default_scene()
    print(kg)
    print(json.dumps(kg.to_scene_context(), indent=2))

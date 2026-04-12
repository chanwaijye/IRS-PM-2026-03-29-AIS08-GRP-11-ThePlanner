"""Tests for nl_to_pddl.py — NL goal → PDDL problem generation."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import json
import pytest
from unittest.mock import patch, MagicMock

from nl_to_pddl import (
    nl_to_pddl_problem,
    _is_valid_pddl,
    _build_fallback_pddl,
)


# ── Shared fixtures ───────────────────────────────────────────────────────────

SIMPLE_SCENE = {
    "robot": "franka",
    "objects": [{"name": "red_cube", "type": "object", "at": "zone_a"}],
    "locations": ["zone_a", "zone_b", "zone_c"],
}

VALID_PDDL = """\
(define (problem tabletop-task)
  (:domain tabletop)
  (:objects
    franka - robot
    red_cube - object
    zone_a zone_b zone_c - location
  )
  (:init
    (hand_empty franka)
    (at franka zone_a)
    (on_table red_cube)
    (clear red_cube)
    (on red_cube zone_a)
    (in_zone red_cube zone_a)
  )
  (:goal (and (in_zone red_cube zone_c)))
)"""


# ── _is_valid_pddl ────────────────────────────────────────────────────────────

class TestIsValidPddl:
    def test_valid_pddl_passes(self):
        assert _is_valid_pddl(VALID_PDDL)

    def test_missing_define_fails(self):
        assert not _is_valid_pddl("(:domain tabletop) (:objects) (:init) (:goal)")

    def test_missing_objects_fails(self):
        bad = VALID_PDDL.replace("(:objects", "(:obj-TYPO")
        assert not _is_valid_pddl(bad)

    def test_missing_init_fails(self):
        bad = VALID_PDDL.replace("(:init", "(:init-TYPO")
        assert not _is_valid_pddl(bad)

    def test_missing_goal_fails(self):
        bad = VALID_PDDL.replace("(:goal", "(:goal-TYPO")
        assert not _is_valid_pddl(bad)

    def test_unbalanced_open_paren_fails(self):
        assert not _is_valid_pddl(VALID_PDDL + "(")

    def test_unbalanced_close_paren_fails(self):
        assert not _is_valid_pddl(")" + VALID_PDDL)

    def test_empty_string_fails(self):
        assert not _is_valid_pddl("")

    def test_whitespace_only_fails(self):
        assert not _is_valid_pddl("   \n  ")

    def test_markdown_fence_fails(self):
        assert not _is_valid_pddl("```pddl\n" + VALID_PDDL + "\n```")


# ── _build_fallback_pddl ──────────────────────────────────────────────────────

class TestBuildFallbackPddl:
    def test_produces_valid_pddl(self):
        result = _build_fallback_pddl(SIMPLE_SCENE)
        assert _is_valid_pddl(result)

    def test_contains_robot(self):
        result = _build_fallback_pddl(SIMPLE_SCENE)
        assert "franka" in result

    def test_contains_object(self):
        result = _build_fallback_pddl(SIMPLE_SCENE)
        assert "red_cube" in result

    def test_contains_locations(self):
        result = _build_fallback_pddl(SIMPLE_SCENE)
        for loc in ["zone_a", "zone_b", "zone_c"]:
            assert loc in result

    def test_fragile_flag_included(self):
        scene = {
            "robot": "franka",
            "objects": [{"name": "glass", "fragile": True, "at": "zone_a"}],
            "locations": ["zone_a", "zone_b"],
        }
        result = _build_fallback_pddl(scene)
        assert "(fragile glass)" in result

    def test_heavy_flag_included(self):
        scene = {
            "robot": "franka",
            "objects": [{"name": "brick", "heavy": True, "at": "zone_a"}],
            "locations": ["zone_a", "zone_b"],
        }
        result = _build_fallback_pddl(scene)
        assert "(heavy brick)" in result

    def test_empty_objects(self):
        scene = {"robot": "franka", "objects": [], "locations": ["zone_a"]}
        result = _build_fallback_pddl(scene)
        assert _is_valid_pddl(result)

    def test_multiple_objects(self):
        scene = {
            "robot": "franka",
            "objects": [
                {"name": "obj_a", "at": "zone_a"},
                {"name": "obj_b", "at": "zone_b"},
            ],
            "locations": ["zone_a", "zone_b", "zone_c"],
        }
        result = _build_fallback_pddl(scene)
        assert "obj_a" in result
        assert "obj_b" in result
        assert _is_valid_pddl(result)


# ── nl_to_pddl_problem — with mocked Ollama ──────────────────────────────────

class TestNlToPddlProblem:
    def _mock_ollama(self, pddl_response: str):
        """Return a context manager that mocks requests.post to return pddl_response."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"response": pddl_response}
        return patch("nl_to_pddl.requests.post", return_value=mock_resp)

    def test_valid_llm_response_returned(self):
        with self._mock_ollama(VALID_PDDL):
            result = nl_to_pddl_problem("Move red cube to zone C", SIMPLE_SCENE)
        assert _is_valid_pddl(result)
        assert "in_zone" in result

    def test_markdown_fences_stripped(self):
        fenced = "```pddl\n" + VALID_PDDL + "\n```"
        with self._mock_ollama(fenced):
            result = nl_to_pddl_problem("Move red cube to zone C", SIMPLE_SCENE)
        assert _is_valid_pddl(result)

    def test_invalid_llm_response_triggers_fallback(self):
        with self._mock_ollama("This is not PDDL at all."):
            result = nl_to_pddl_problem("Move red cube to zone C", SIMPLE_SCENE)
        assert _is_valid_pddl(result)
        assert "red_cube" in result

    def test_ollama_unavailable_triggers_fallback(self):
        with patch("nl_to_pddl.requests.post", side_effect=ConnectionError("offline")):
            result = nl_to_pddl_problem("Move red cube to zone C", SIMPLE_SCENE)
        assert _is_valid_pddl(result)

    def test_ollama_timeout_triggers_fallback(self):
        import requests as req_mod
        with patch("nl_to_pddl.requests.post", side_effect=req_mod.Timeout):
            result = nl_to_pddl_problem("Move red cube to zone C", SIMPLE_SCENE)
        assert _is_valid_pddl(result)

    def test_http_error_triggers_fallback(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("500 Server Error")
        with patch("nl_to_pddl.requests.post", return_value=mock_resp):
            result = nl_to_pddl_problem("Move red cube to zone C", SIMPLE_SCENE)
        assert _is_valid_pddl(result)

    def test_fragile_scene_produces_valid_pddl(self):
        fragile_scene = {
            "robot": "franka",
            "objects": [{"name": "glass_sphere", "fragile": True, "at": "zone_c"}],
            "locations": ["zone_a", "zone_b", "zone_c"],
        }
        with self._mock_ollama(VALID_PDDL):
            result = nl_to_pddl_problem(
                "Place the fragile glass sphere in zone A", fragile_scene
            )
        assert _is_valid_pddl(result)

    def test_empty_llm_response_triggers_fallback(self):
        with self._mock_ollama(""):
            result = nl_to_pddl_problem("Move red cube to zone C", SIMPLE_SCENE)
        assert _is_valid_pddl(result)

    def test_result_contains_domain_name(self):
        with self._mock_ollama(VALID_PDDL):
            result = nl_to_pddl_problem("Move red cube to zone C", SIMPLE_SCENE)
        assert "tabletop" in result

#pragma once
#include "state.hpp"
#include <string>
#include <vector>

namespace planner {

// A grounded action: preconditions and effects as predicate IDs.
struct GroundedAction {
    std::string name;                       // e.g. "pick(franka,red_cube,zone_a)"
    std::vector<PredicateId> pos_pre;       // must be true
    std::vector<PredicateId> neg_pre;       // must be false
    std::vector<PredicateId> add_eff;       // set to true
    std::vector<PredicateId> del_eff;       // set to false
    double cost{1.0};                       // used by A* g-cost

    // Returns true if the action is applicable in the given state.
    bool applicable(const State& s) const {
        for (auto id : pos_pre) if (!s.facts[id]) return false;
        for (auto id : neg_pre) if ( s.facts[id]) return false;
        return true;
    }

    // Returns the successor state after applying this action.
    State apply(const State& s) const {
        State next = s;
        for (auto id : del_eff) next.facts.reset(id);
        for (auto id : add_eff) next.facts.set(id);
        return next;
    }
};

// Lifted (schema) action, parameterised — instantiated into GroundedActions
// by the grounder inside PddlParser.
struct ActionSchema {
    std::string name;
    std::vector<std::string> param_names;   // ?robot ?obj ?from_loc ...
    std::vector<std::string> param_types;

    // Raw PDDL strings for pre/effect — resolved during grounding
    std::vector<std::string> pos_pre_raw;
    std::vector<std::string> neg_pre_raw;
    std::vector<std::string> add_eff_raw;
    std::vector<std::string> del_eff_raw;
};

}  // namespace planner

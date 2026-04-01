#pragma once
#include "action.hpp"
#include "state.hpp"
#include <string>
#include <unordered_map>
#include <vector>

namespace planner {

// Typed object registry: type name → list of object names
using TypedObjects = std::unordered_map<std::string, std::vector<std::string>>;

struct ParsedDomain {
    std::string name;
    TypedObjects types;             // type hierarchy (flat for now)
    std::vector<std::string> predicates_raw;
    std::vector<ActionSchema> actions;
};

struct ParsedProblem {
    std::string name;
    std::string domain_name;
    TypedObjects objects;
    std::vector<std::string> init_facts;    // ground predicates, positive
    std::vector<std::string> goal_facts;    // positive conjuncts only
};

// Parses a PDDL 2.1 domain and problem file, then grounds all actions
// into the flat GroundedAction representation used by the planner.
class PddlParser {
public:
    ParsedDomain parse_domain(const std::string& path);
    ParsedProblem parse_problem(const std::string& path);

    // Ground all action schemas against the problem objects, build initial
    // state and goal state using the shared PredicateIndex.
    void ground(const ParsedDomain& domain,
                const ParsedProblem& problem,
                PredicateIndex& index,
                State& init_state,
                State& goal_state,
                std::vector<GroundedAction>& actions_out);

private:
    // Tokenises/normalises one PDDL s-expression.
    std::vector<std::string> tokenise(const std::string& src);

    // Instantiates one schema with a concrete binding.
    GroundedAction ground_action(const ActionSchema& schema,
                                 const std::vector<std::string>& binding,
                                 PredicateIndex& index);
};

}  // namespace planner

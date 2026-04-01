#include "astar_planner.hpp"
#include "ga_ranker.hpp"
#include "pddl_parser.hpp"
#include "plan.hpp"
#include "state.hpp"

#include <iostream>
#include <string>

// Usage: planner_node <domain.pddl> <problem.pddl> [--verbose]
int main(int argc, char** argv) {
    if (argc < 3) {
        std::cerr << "Usage: planner_node <domain.pddl> <problem.pddl> [--verbose]\n";
        return 1;
    }

    const std::string domain_path  = argv[1];
    const std::string problem_path = argv[2];
    const bool verbose = (argc >= 4 && std::string(argv[3]) == "--verbose");

    planner::PddlParser parser;
    planner::PredicateIndex index;
    planner::State init_state, goal_state;
    std::vector<planner::GroundedAction> actions;

    try {
        auto domain  = parser.parse_domain(domain_path);
        auto problem = parser.parse_problem(problem_path);
        parser.ground(domain, problem, index, init_state, goal_state, actions);
    } catch (const std::exception& e) {
        std::cerr << "[parser] " << e.what() << "\n";
        return 2;
    }

    if (verbose) {
        std::cerr << "[info] predicates=" << index.size()
                  << " actions=" << actions.size() << "\n";
    }

    planner::AStarPlanner astar({.max_nodes = 500'000, .verbose = verbose});
    auto result = astar.search(init_state, goal_state, actions);

    if (!result) {
        std::cerr << "[planner] No plan found after "
                  << astar.nodes_expanded() << " expansions.\n";
        return 3;
    }

    // Optionally re-rank via GA (useful when multiple plans exist)
    planner::GaRanker ranker;
    planner::Plan best = ranker.rank({*result}, init_state, goal_state);

    // Output JSON plan to stdout for downstream consumers
    std::cout << best.to_json().dump(2) << "\n";
    return 0;
}

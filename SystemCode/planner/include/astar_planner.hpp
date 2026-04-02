#pragma once
#include "action.hpp"
#include "plan.hpp"
#include "state.hpp"
#include <optional>
#include <vector>

namespace planner {

// Admissible heuristic: count unsatisfied goal predicates (h_add lower bound).
double h_unsatisfied(const State& current, const State& goal);

// A* forward search over the STRIPS state space.
// Returns an optimal (min-cost) plan, or nullopt if no plan exists.
class AStarPlanner {
public:
    struct Config {
        std::size_t max_nodes{500'000};   // node expansion budget
        bool verbose{false};
    };

    AStarPlanner() : cfg_(Config{}) {}
    explicit AStarPlanner(Config cfg) : cfg_(cfg) {}

    std::optional<Plan> search(const State& init,
                               const State& goal,
                               const std::vector<GroundedAction>& actions);

    std::size_t nodes_expanded() const { return nodes_expanded_; }

private:
    Config cfg_;
    std::size_t nodes_expanded_{0};
};

}  // namespace planner

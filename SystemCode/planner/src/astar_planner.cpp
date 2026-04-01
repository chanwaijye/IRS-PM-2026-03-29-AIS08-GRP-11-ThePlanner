#include "astar_planner.hpp"
#include <queue>
#include <unordered_map>

namespace planner {

// ── Heuristic ──────────────────────────────────────────────────────────────

double h_unsatisfied(const State& current, const State& goal) {
    // Count bits set in goal but not in current — admissible relaxation.
    return static_cast<double>((goal.facts & ~current.facts).count());
}

// ── A* ────────────────────────────────────────────────────────────────────

struct Node {
    State state;
    double g{0.0};
    double f{0.0};
    std::string action_name;
    std::size_t parent_idx{SIZE_MAX};
};

struct NodeCmp {
    bool operator()(const std::pair<double, std::size_t>& a,
                    const std::pair<double, std::size_t>& b) const {
        return a.first > b.first;  // min-heap on f
    }
};

std::optional<Plan> AStarPlanner::search(
        const State& init,
        const State& goal,
        const std::vector<GroundedAction>& actions) {

    nodes_expanded_ = 0;
    std::vector<Node> nodes;
    nodes.reserve(4096);

    std::unordered_map<State, double, StateHash> best_g;
    std::priority_queue<std::pair<double, std::size_t>,
                        std::vector<std::pair<double, std::size_t>>,
                        NodeCmp> open;

    nodes.push_back({init, 0.0, h_unsatisfied(init, goal), "", SIZE_MAX});
    open.push({nodes[0].f, 0});
    best_g[init] = 0.0;

    while (!open.empty()) {
        auto [f_val, idx] = open.top();
        open.pop();

        const Node& cur = nodes[idx];

        // Stale entry check
        if (f_val > cur.f + 1e-9) continue;

        // Goal check: all goal predicates satisfied
        if ((goal.facts & cur.state.facts) == goal.facts) {
            // Reconstruct plan
            Plan plan;
            std::vector<std::size_t> path;
            std::size_t i = idx;
            while (i != SIZE_MAX) {
                path.push_back(i);
                i = nodes[i].parent_idx;
            }
            std::reverse(path.begin(), path.end());
            for (std::size_t pi = 1; pi < path.size(); ++pi) {
                const Node& n = nodes[path[pi]];
                GroundedAction dummy;
                dummy.name = n.action_name;
                dummy.cost = n.g - nodes[n.parent_idx].g;
                plan.steps.push_back(dummy);
                plan.total_cost += dummy.cost;
            }
            return plan;
        }

        if (nodes_expanded_ >= cfg_.max_nodes) break;
        ++nodes_expanded_;

        for (const auto& action : actions) {
            if (!action.applicable(cur.state)) continue;
            State next = action.apply(cur.state);
            double new_g = cur.g + action.cost;

            auto it = best_g.find(next);
            if (it != best_g.end() && it->second <= new_g) continue;
            best_g[next] = new_g;

            double h = h_unsatisfied(next, goal);
            double new_f = new_g + h;

            nodes.push_back({next, new_g, new_f, action.name, idx});
            open.push({new_f, nodes.size() - 1});
        }
    }

    return std::nullopt;  // no plan found
}

}  // namespace planner

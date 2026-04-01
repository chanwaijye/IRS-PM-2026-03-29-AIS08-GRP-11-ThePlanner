#pragma once
#include "action.hpp"
#include <nlohmann/json.hpp>
#include <vector>

namespace planner {

// A Plan is an ordered sequence of grounded actions.
struct Plan {
    std::vector<GroundedAction> steps;
    double total_cost{0.0};

    bool empty() const { return steps.empty(); }
    std::size_t size() const { return steps.size(); }

    // Serialise to JSON for consumption by FastAPI hub / ROS2 bridge.
    nlohmann::json to_json() const {
        nlohmann::json j;
        j["cost"] = total_cost;
        j["length"] = steps.size();
        j["actions"] = nlohmann::json::array();
        for (std::size_t i = 0; i < steps.size(); ++i) {
            j["actions"].push_back({{"step", i}, {"name", steps[i].name},
                                    {"cost", steps[i].cost}});
        }
        return j;
    }
};

}  // namespace planner

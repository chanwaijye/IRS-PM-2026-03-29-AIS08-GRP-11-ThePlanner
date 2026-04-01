#include "ga_ranker.hpp"
#include "pddl_parser.hpp"
#include <gtest/gtest.h>

using namespace planner;

static Plan make_plan(const std::vector<std::string>& names, double cost_per = 1.0) {
    Plan p;
    for (auto& n : names) {
        GroundedAction a;
        a.name = n;
        a.cost = cost_per;
        p.steps.push_back(a);
        p.total_cost += cost_per;
    }
    return p;
}

TEST(GaRanker, SinglePlanReturnedUnchanged) {
    Plan p = make_plan({"pick", "place"});
    State init, goal;
    GaRanker ranker;
    Plan result = ranker.rank({p}, init, goal);
    EXPECT_EQ(result.size(), p.size());
}

TEST(GaRanker, ShortPlanRanksHigherThanLongPlan) {
    Plan short_plan = make_plan({"pick", "place"});
    Plan long_plan  = make_plan({"pick", "move", "move", "place"});
    State init, goal;

    GaRanker::Config cfg;
    cfg.generations = 50;
    GaRanker ranker(cfg);
    Plan best = ranker.rank({short_plan, long_plan}, init, goal);
    EXPECT_LE(best.size(), short_plan.size());
}

TEST(GaRanker, ThrowsOnEmptyCandidates) {
    State init, goal;
    GaRanker ranker;
    EXPECT_THROW(ranker.rank({}, init, goal), std::invalid_argument);
}

TEST(GaRanker, FitnessIsPositive) {
    Plan p = make_plan({"pick", "place"});
    State init, goal;
    GaRanker ranker;
    ranker.rank({p}, init, goal);
    EXPECT_GT(ranker.last_best_fitness(), 0.0);
}

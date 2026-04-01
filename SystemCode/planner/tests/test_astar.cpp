#include "astar_planner.hpp"
#include "pddl_parser.hpp"
#include <gtest/gtest.h>

using namespace planner;

// Helpers to build minimal test fixtures.
static PredicateIndex g_idx;

static GroundedAction make_action(const std::string& name,
                                   const std::vector<std::string>& pos_pre,
                                   const std::vector<std::string>& neg_pre,
                                   const std::vector<std::string>& add_eff,
                                   const std::vector<std::string>& del_eff,
                                   double cost = 1.0) {
    GroundedAction a;
    a.name = name;
    a.cost = cost;
    for (auto& p : pos_pre) a.pos_pre.push_back(g_idx.intern(p));
    for (auto& p : neg_pre) a.neg_pre.push_back(g_idx.intern(p));
    for (auto& p : add_eff) a.add_eff.push_back(g_idx.intern(p));
    for (auto& p : del_eff) a.del_eff.push_back(g_idx.intern(p));
    return a;
}

static State make_state(const std::vector<std::string>& facts) {
    State s;
    for (auto& f : facts) s.facts.set(g_idx.intern(f));
    return s;
}

TEST(AStarPlanner, FindsTrivialOnestepPlan) {
    // Init: hand_empty. Goal: holding_cube.
    // Action pick: pre=hand_empty, add=holding_cube, del=hand_empty.
    auto pick = make_action("pick",
                            {"hand_empty"}, {},
                            {"holding_cube"}, {"hand_empty"});
    State init = make_state({"hand_empty"});
    State goal = make_state({"holding_cube"});

    AStarPlanner planner;
    auto result = planner.search(init, goal, {pick});
    ASSERT_TRUE(result.has_value());
    EXPECT_EQ(result->size(), 1u);
    EXPECT_EQ(result->steps[0].name, "pick");
}

TEST(AStarPlanner, FindsTwoStepPlan) {
    auto pick  = make_action("pick",
                             {"hand_empty", "cube_on_table"}, {},
                             {"holding_cube"}, {"hand_empty", "cube_on_table"});
    auto place = make_action("place",
                             {"holding_cube"}, {},
                             {"cube_in_zone_b"}, {"holding_cube"});

    State init = make_state({"hand_empty", "cube_on_table"});
    State goal = make_state({"cube_in_zone_b"});

    AStarPlanner planner;
    auto result = planner.search(init, goal, {pick, place});
    ASSERT_TRUE(result.has_value());
    EXPECT_EQ(result->size(), 2u);
}

TEST(AStarPlanner, ReturnsNulloptWhenGoalUnreachable) {
    auto noop = make_action("noop", {}, {}, {}, {});
    State init = make_state({"A"});
    State goal = make_state({"B"});  // B never produced

    AStarPlanner::Config cfg;
    cfg.max_nodes = 10;
    AStarPlanner planner(cfg);
    auto result = planner.search(init, goal, {noop});
    EXPECT_FALSE(result.has_value());
}

TEST(AStarPlanner, GoalAlreadySatisfied) {
    State init = make_state({"A", "B"});
    State goal = make_state({"A"});

    AStarPlanner planner;
    auto result = planner.search(init, goal, {});
    ASSERT_TRUE(result.has_value());
    EXPECT_TRUE(result->empty());
}

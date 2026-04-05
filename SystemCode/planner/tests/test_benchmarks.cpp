// IPC Benchmark integration tests for ThePlanner
// Each test parses a real PDDL domain+problem, runs A*, and validates the plan.
//
// Domains used (all IPC-1998 / classic AI planning):
//   - Blocksworld : pick-up / put-down / stack / unstack
//   - Gripper     : move / pick / drop
//   - Logistics   : load-truck / unload-truck / drive-truck

#include "astar_planner.hpp"
#include "pddl_parser.hpp"
#include <gtest/gtest.h>
#include <chrono>
#include <iostream>
#include <string>

using namespace planner;

// BENCHMARK_DIR is injected by CMake as an absolute path string.
#ifndef BENCHMARK_DIR
#  define BENCHMARK_DIR "tests/benchmarks"
#endif

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

struct BenchResult {
    bool     solved{false};
    std::size_t plan_length{0};
    std::size_t nodes_expanded{0};
    double   elapsed_ms{0.0};
};

static BenchResult run_planner(const std::string& domain_path,
                                const std::string& problem_path,
                                std::size_t max_nodes = 500'000) {
    PddlParser parser;
    PredicateIndex index;
    State init_state, goal_state;
    std::vector<GroundedAction> actions;

    auto domain  = parser.parse_domain(domain_path);
    auto problem = parser.parse_problem(problem_path);
    parser.ground(domain, problem, index, init_state, goal_state, actions);

    AStarPlanner::Config cfg;
    cfg.max_nodes = max_nodes;
    AStarPlanner astar(cfg);

    auto t0 = std::chrono::steady_clock::now();
    auto result = astar.search(init_state, goal_state, actions);
    auto t1 = std::chrono::steady_clock::now();

    BenchResult br;
    br.nodes_expanded = astar.nodes_expanded();
    br.elapsed_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();

    if (result) {
        br.solved      = true;
        br.plan_length = result->size();
        // Print plan for human inspection
        std::cout << "[plan] ";
        for (auto& step : result->steps)
            std::cout << step.name << "  ";
        std::cout << "\n";
    }
    std::cout << "[stats] nodes=" << br.nodes_expanded
              << "  length=" << br.plan_length
              << "  time=" << br.elapsed_ms << " ms\n";
    return br;
}

// Convenience macro: domain and problem are relative to BENCHMARK_DIR
#define BENCH(domain_rel, problem_rel) \
    run_planner(std::string(BENCHMARK_DIR) + "/" + (domain_rel), \
                std::string(BENCHMARK_DIR) + "/" + (problem_rel))

// ---------------------------------------------------------------------------
// Blocksworld
// ---------------------------------------------------------------------------

TEST(IPC_Blocksworld, P01_Swap2Blocks) {
    // Init: a on b. Goal: b on a. Optimal plan length: 4.
    auto r = BENCH("blocksworld/domain.pddl", "blocksworld/p01.pddl");
    ASSERT_TRUE(r.solved) << "Planner failed to find a plan";
    EXPECT_EQ(r.plan_length, 4u) << "Expected optimal plan of length 4";
}

TEST(IPC_Blocksworld, P02_Build3Tower) {
    // Init: a,b,c on table. Goal: on(a,b), on(b,c). Optimal: 4 steps.
    auto r = BENCH("blocksworld/domain.pddl", "blocksworld/p02.pddl");
    ASSERT_TRUE(r.solved);
    EXPECT_EQ(r.plan_length, 4u) << "Expected optimal plan of length 4";
}

TEST(IPC_Blocksworld, P03_Build4Tower) {
    // Init: a,b,c,d on table. Goal: on(b,a), on(c,b), on(d,c). Optimal: 6 steps.
    auto r = BENCH("blocksworld/domain.pddl", "blocksworld/p03.pddl");
    ASSERT_TRUE(r.solved);
    EXPECT_EQ(r.plan_length, 6u) << "Expected optimal plan of length 6";
}

// ---------------------------------------------------------------------------
// Gripper
// ---------------------------------------------------------------------------

TEST(IPC_Gripper, P01_Move2Balls) {
    // Init: 2 balls in room1. Goal: both in room2. Optimal: 5 steps.
    auto r = BENCH("gripper/domain.pddl", "gripper/p01.pddl");
    ASSERT_TRUE(r.solved);
    EXPECT_EQ(r.plan_length, 5u) << "Expected optimal plan of length 5";
}

TEST(IPC_Gripper, P02_Move4Balls) {
    // Init: 4 balls in room1. Goal: all in room2. Optimal: 11 steps (2 trips).
    auto r = BENCH("gripper/domain.pddl", "gripper/p02.pddl");
    ASSERT_TRUE(r.solved);
    EXPECT_EQ(r.plan_length, 11u) << "Expected optimal plan of length 11";
}

// ---------------------------------------------------------------------------
// Logistics
// ---------------------------------------------------------------------------

TEST(IPC_Logistics, P01_Deliver2Packages) {
    // Init: pkg1,pkg2 at loc1; truck at loc1. Goal: both at loc2. Optimal: 5 steps.
    auto r = BENCH("logistics/domain.pddl", "logistics/p01.pddl");
    ASSERT_TRUE(r.solved);
    EXPECT_EQ(r.plan_length, 5u) << "Expected optimal plan of length 5";
}

// ---------------------------------------------------------------------------
// Scalability smoke test: verify planner stays within node budget
// ---------------------------------------------------------------------------

TEST(IPC_NodeBudget, AllBenchmarksUnder10k) {
    std::vector<std::pair<std::string, std::string>> cases = {
        {"blocksworld/domain.pddl", "blocksworld/p01.pddl"},
        {"blocksworld/domain.pddl", "blocksworld/p02.pddl"},
        {"blocksworld/domain.pddl", "blocksworld/p03.pddl"},
        {"gripper/domain.pddl",     "gripper/p01.pddl"},
        {"gripper/domain.pddl",     "gripper/p02.pddl"},
        {"logistics/domain.pddl",   "logistics/p01.pddl"},
    };
    for (auto& [dom, prob] : cases) {
        auto r = BENCH(dom, prob);
        EXPECT_TRUE(r.solved) << "Not solved: " << prob;
        EXPECT_LT(r.nodes_expanded, 10'000u)
            << "Too many nodes for: " << prob
            << " (expanded=" << r.nodes_expanded << ")";
    }
}

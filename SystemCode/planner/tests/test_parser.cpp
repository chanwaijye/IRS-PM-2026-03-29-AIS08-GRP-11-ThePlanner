#include "pddl_parser.hpp"
#include <gtest/gtest.h>
#include <fstream>
#include <sstream>

using namespace planner;

// Write a minimal valid domain/problem to a temp file for testing.
static std::string write_temp(const std::string& content, const std::string& suffix) {
    std::string path = "/tmp/planner_test_" + suffix;
    std::ofstream f(path);
    f << content;
    return path;
}

TEST(PddlParser, ParseDomainReturnsName) {
    std::string domain_src = R"(
        (define (domain tabletop)
          (:requirements :strips :typing)
          (:types robot object location - object)
          (:predicates (on_table ?o - object))
        )
    )";
    std::string path = write_temp(domain_src, "domain.pddl");
    PddlParser parser;
    auto d = parser.parse_domain(path);
    EXPECT_EQ(d.name, "tabletop");
}

TEST(PddlParser, ParseProblemReturnsName) {
    std::string prob_src = R"(
        (define (problem tabletop-task)
          (:domain tabletop)
          (:objects franka - robot)
          (:init (hand_empty franka))
          (:goal (and (on_table red_cube)))
        )
    )";
    std::string path = write_temp(prob_src, "problem.pddl");
    PddlParser parser;
    auto p = parser.parse_problem(path);
    EXPECT_EQ(p.domain_name, "tabletop");
}

TEST(PddlParser, PredicateIndexInternsUnique) {
    PredicateIndex idx;
    auto id1 = idx.intern("on_table(red_cube)");
    auto id2 = idx.intern("on_table(blue_cube)");
    auto id3 = idx.intern("on_table(red_cube)");
    EXPECT_NE(id1, id2);
    EXPECT_EQ(id1, id3);
    EXPECT_EQ(idx.size(), 2u);
}

TEST(PddlParser, GroundingProducesEmptyActionsForEmptyDomain) {
    PddlParser parser;
    ParsedDomain domain;
    domain.name = "tabletop";
    ParsedProblem problem;
    problem.init_facts = {"hand_empty(franka)"};
    problem.goal_facts = {"on_table(red_cube)"};
    problem.objects["robot"] = {"franka"};

    PredicateIndex index;
    State init, goal;
    std::vector<GroundedAction> actions;
    parser.ground(domain, problem, index, init, goal, actions);

    EXPECT_TRUE(actions.empty());
    EXPECT_TRUE(init.facts[index.intern("hand_empty(franka)")]);
    EXPECT_TRUE(goal.facts[index.intern("on_table(red_cube)")]);
}

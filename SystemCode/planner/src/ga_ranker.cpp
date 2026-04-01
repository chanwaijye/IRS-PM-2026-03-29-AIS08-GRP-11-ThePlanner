#include "ga_ranker.hpp"
#include <algorithm>
#include <random>
#include <stdexcept>

namespace planner {

// ── Fitness ────────────────────────────────────────────────────────────────

double GaRanker::fitness(const Plan& plan,
                          const State& /*init*/,
                          const State& /*goal*/) const {
    if (plan.empty()) return 0.0;

    // Normalise each criterion to [0,1] (lower cost = higher fitness)
    double f_steps = 1.0 / (1.0 + static_cast<double>(plan.size()));
    double f_time  = 1.0 / (1.0 + plan.total_cost);

    // Collision risk proxy: count actions whose names contain "stack"
    double risky = 0.0;
    for (auto& step : plan.steps)
        if (step.name.find("stack") != std::string::npos) risky += 1.0;
    double f_collision = 1.0 / (1.0 + risky);

    return cfg_.weights.w_steps * f_steps
         + cfg_.weights.w_time  * f_time
         + cfg_.weights.w_collision_risk * f_collision;
}

// ── Crossover (order-preserving) ───────────────────────────────────────────

std::vector<Plan> GaRanker::crossover(const Plan& a, const Plan& b) const {
    if (a.size() != b.size() || a.empty()) return {a, b};
    std::mt19937 rng(std::random_device{}());
    std::uniform_int_distribution<std::size_t> dist(0, a.size() - 1);
    std::size_t cut = dist(rng);

    Plan child1, child2;
    for (std::size_t i = 0; i <= cut; ++i)  child1.steps.push_back(a.steps[i]);
    for (std::size_t i = cut + 1; i < b.size(); ++i) child1.steps.push_back(b.steps[i]);
    for (std::size_t i = 0; i <= cut; ++i)  child2.steps.push_back(b.steps[i]);
    for (std::size_t i = cut + 1; i < a.size(); ++i) child2.steps.push_back(a.steps[i]);

    for (auto& s : child1.steps) child1.total_cost += s.cost;
    for (auto& s : child2.steps) child2.total_cost += s.cost;
    return {child1, child2};
}

// ── Mutation (swap adjacent commutative steps) ─────────────────────────────

void GaRanker::mutate(Plan& plan) const {
    if (plan.size() < 2) return;
    std::mt19937 rng(std::random_device{}());
    std::uniform_int_distribution<std::size_t> dist(0, plan.size() - 2);
    std::size_t i = dist(rng);
    std::swap(plan.steps[i], plan.steps[i + 1]);
}

// ── Main rank interface ────────────────────────────────────────────────────

Plan GaRanker::rank(const std::vector<Plan>& candidates,
                     const State& init,
                     const State& goal) {
    if (candidates.empty()) throw std::invalid_argument("No candidate plans");
    if (candidates.size() == 1) {
        last_best_fitness_ = fitness(candidates[0], init, goal);
        return candidates[0];
    }

    std::mt19937 rng(std::random_device{}());
    std::uniform_real_distribution<double> prob(0.0, 1.0);

    // Seed population by replicating/mixing candidates
    std::vector<Plan> population;
    while (population.size() < cfg_.population_size) {
        population.push_back(candidates[rng() % candidates.size()]);
    }

    for (std::size_t gen = 0; gen < cfg_.generations; ++gen) {
        // Sort by fitness descending
        std::sort(population.begin(), population.end(),
                  [&](const Plan& x, const Plan& y) {
                      return fitness(x, init, goal) > fitness(y, init, goal);
                  });

        // Elitism: keep top half, replace bottom half with offspring
        std::size_t half = population.size() / 2;
        for (std::size_t i = 0; i < half; ++i) {
            std::size_t j = rng() % half;
            if (prob(rng) < cfg_.crossover_rate) {
                auto children = crossover(population[i], population[j]);
                population[half + i] = children[0];
            }
            if (prob(rng) < cfg_.mutation_rate)
                mutate(population[half + i]);
        }
    }

    // Return best
    std::sort(population.begin(), population.end(),
              [&](const Plan& x, const Plan& y) {
                  return fitness(x, init, goal) > fitness(y, init, goal);
              });
    last_best_fitness_ = fitness(population[0], init, goal);
    return population[0];
}

}  // namespace planner

#pragma once
#include "plan.hpp"
#include "state.hpp"
#include <vector>

namespace planner {

// Fitness criteria for the GA ranker.
struct FitnessWeights {
    double w_steps{0.4};           // minimise number of steps
    double w_time{0.3};            // minimise estimated execution time
    double w_collision_risk{0.3};  // minimise proximity to fragile objects
};

// Genetic Algorithm ranker: given a set of candidate plans (e.g. from beam
// search variants), evolves a population to find the highest-fitness plan.
// For the MVP the population is seeded with plan permutations; mutation swaps
// adjacent commutative steps.
class GaRanker {
public:
    struct Config {
        std::size_t population_size{50};
        std::size_t generations{100};
        double mutation_rate{0.1};
        double crossover_rate{0.7};
        FitnessWeights weights{};
    };

    GaRanker() : cfg_(Config{}) {}
    explicit GaRanker(Config cfg) : cfg_(cfg) {}

    // Rank a set of candidate plans; return the best-fitness plan.
    // If only one plan is given, returns it unchanged.
    Plan rank(const std::vector<Plan>& candidates,
              const State& init,
              const State& goal);

    double last_best_fitness() const { return last_best_fitness_; }

private:
    Config cfg_;
    double last_best_fitness_{0.0};

    double fitness(const Plan& plan, const State& init, const State& goal) const;
    std::vector<Plan> crossover(const Plan& a, const Plan& b) const;
    void mutate(Plan& plan) const;
};

}  // namespace planner

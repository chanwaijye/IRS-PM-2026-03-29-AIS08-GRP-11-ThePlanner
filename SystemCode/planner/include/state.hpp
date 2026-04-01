#pragma once
#include <bitset>
#include <cstdint>
#include <functional>
#include <string>
#include <unordered_map>
#include <vector>

namespace planner {

// Maximum number of ground predicates supported per problem instance.
// Increase if domain grows beyond this.
static constexpr std::size_t MAX_PREDICATES = 512;

using PredicateId = uint32_t;

// Maps "predicate_name(arg1,arg2,...)" strings ↔ integer IDs.
class PredicateIndex {
public:
    PredicateId intern(const std::string& ground_pred);
    const std::string& name(PredicateId id) const;
    std::size_t size() const { return id_to_name_.size(); }

private:
    std::unordered_map<std::string, PredicateId> name_to_id_;
    std::vector<std::string> id_to_name_;
};

// A world state is a bitset over ground predicates.
struct State {
    std::bitset<MAX_PREDICATES> facts;

    bool operator==(const State& other) const { return facts == other.facts; }
    bool operator!=(const State& other) const { return facts != other.facts; }
};

struct StateHash {
    std::size_t operator()(const State& s) const {
        // FNV-1a over the bitset storage words
        const auto& bs = s.facts;
        std::size_t h = 0xcbf29ce484222325ULL;
        for (std::size_t i = 0; i < MAX_PREDICATES; i += 64) {
            uint64_t word = 0;
            for (std::size_t b = 0; b < 64 && i + b < MAX_PREDICATES; ++b) {
                if (bs[i + b]) word |= (1ULL << b);
            }
            h ^= word;
            h *= 0x100000001b3ULL;
        }
        return h;
    }
};

}  // namespace planner

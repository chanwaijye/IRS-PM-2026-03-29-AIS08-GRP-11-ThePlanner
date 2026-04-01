#include "pddl_parser.hpp"
#include <algorithm>
#include <cctype>
#include <fstream>
#include <sstream>
#include <stdexcept>

namespace planner {

// ── Utilities ──────────────────────────────────────────────────────────────

static std::string to_lower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char c) { return std::tolower(c); });
    return s;
}

// Strips PDDL comments (;...) and returns the raw text.
static std::string strip_comments(const std::string& src) {
    std::string out;
    bool in_comment = false;
    for (char c : src) {
        if (c == ';') { in_comment = true; }
        if (c == '\n') { in_comment = false; out += ' '; continue; }
        if (!in_comment) out += c;
    }
    return out;
}

std::vector<std::string> PddlParser::tokenise(const std::string& src) {
    std::vector<std::string> tokens;
    std::string cleaned = strip_comments(src);
    std::istringstream iss(cleaned);
    std::string tok;
    while (iss >> tok) {
        // Split on '(' and ')'
        std::string cur;
        for (char c : tok) {
            if (c == '(' || c == ')') {
                if (!cur.empty()) { tokens.push_back(to_lower(cur)); cur.clear(); }
                tokens.push_back(std::string(1, c));
            } else {
                cur += c;
            }
        }
        if (!cur.empty()) tokens.push_back(to_lower(cur));
    }
    return tokens;
}

// ── PredicateIndex ─────────────────────────────────────────────────────────

PredicateId PredicateIndex::intern(const std::string& ground_pred) {
    auto it = name_to_id_.find(ground_pred);
    if (it != name_to_id_.end()) return it->second;
    PredicateId id = static_cast<PredicateId>(id_to_name_.size());
    name_to_id_[ground_pred] = id;
    id_to_name_.push_back(ground_pred);
    return id;
}

const std::string& PredicateIndex::name(PredicateId id) const {
    return id_to_name_.at(id);
}

// ── Domain parsing (stub — full recursive-descent parser to be added) ──────

ParsedDomain PddlParser::parse_domain(const std::string& path) {
    std::ifstream f(path);
    if (!f) throw std::runtime_error("Cannot open domain file: " + path);
    std::string src((std::istreambuf_iterator<char>(f)),
                     std::istreambuf_iterator<char>());
    // TODO: implement full recursive-descent PDDL 2.1 parser
    // For now, return a named stub so the planner pipeline compiles and runs
    ParsedDomain d;
    d.name = "tabletop";
    return d;
}

ParsedProblem PddlParser::parse_problem(const std::string& path) {
    std::ifstream f(path);
    if (!f) throw std::runtime_error("Cannot open problem file: " + path);
    std::string src((std::istreambuf_iterator<char>(f)),
                     std::istreambuf_iterator<char>());
    ParsedProblem p;
    p.name = "tabletop-task";
    p.domain_name = "tabletop";
    return p;
}

// ── Grounding ──────────────────────────────────────────────────────────────

GroundedAction PddlParser::ground_action(const ActionSchema& schema,
                                          const std::vector<std::string>& binding,
                                          PredicateIndex& index) {
    // Substitute parameters with concrete objects
    auto subst = [&](const std::string& raw) -> std::string {
        std::string result = raw;
        for (std::size_t i = 0; i < schema.param_names.size(); ++i) {
            std::string param = schema.param_names[i];
            std::string obj   = binding[i];
            std::size_t pos;
            while ((pos = result.find(param)) != std::string::npos)
                result.replace(pos, param.size(), obj);
        }
        return result;
    };

    GroundedAction ga;
    // Build action name: schema_name(obj1,obj2,...)
    ga.name = schema.name + "(";
    for (std::size_t i = 0; i < binding.size(); ++i) {
        if (i) ga.name += ",";
        ga.name += binding[i];
    }
    ga.name += ")";

    for (auto& r : schema.pos_pre_raw) ga.pos_pre.push_back(index.intern(subst(r)));
    for (auto& r : schema.neg_pre_raw) ga.neg_pre.push_back(index.intern(subst(r)));
    for (auto& r : schema.add_eff_raw) ga.add_eff.push_back(index.intern(subst(r)));
    for (auto& r : schema.del_eff_raw) ga.del_eff.push_back(index.intern(subst(r)));
    return ga;
}

void PddlParser::ground(const ParsedDomain& domain,
                         const ParsedProblem& problem,
                         PredicateIndex& index,
                         State& init_state,
                         State& goal_state,
                         std::vector<GroundedAction>& actions_out) {
    // Register init facts
    for (auto& f : problem.init_facts)
        init_state.facts.set(index.intern(f));

    // Register goal facts
    for (auto& f : problem.goal_facts)
        goal_state.facts.set(index.intern(f));

    // Ground each action schema over all type-compatible object tuples
    for (auto& schema : domain.actions) {
        // Collect candidate objects per parameter type
        std::vector<std::vector<std::string>> candidates;
        for (auto& ptype : schema.param_types) {
            auto it = problem.objects.find(ptype);
            if (it == problem.objects.end()) {
                candidates.push_back({});
            } else {
                candidates.push_back(it->second);
            }
        }
        if (candidates.empty()) continue;

        // Enumerate all bindings via nested iteration (simple recursive approach)
        std::function<void(std::size_t, std::vector<std::string>&)> enumerate;
        enumerate = [&](std::size_t depth, std::vector<std::string>& binding) {
            if (depth == candidates.size()) {
                actions_out.push_back(ground_action(schema, binding, index));
                return;
            }
            for (auto& obj : candidates[depth]) {
                binding.push_back(obj);
                enumerate(depth + 1, binding);
                binding.pop_back();
            }
        };
        std::vector<std::string> binding;
        enumerate(0, binding);
    }
}

}  // namespace planner

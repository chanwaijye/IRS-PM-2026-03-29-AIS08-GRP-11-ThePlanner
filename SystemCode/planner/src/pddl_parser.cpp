#include "pddl_parser.hpp"
#include <algorithm>
#include <cctype>
#include <fstream>
#include <functional>
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

// ── Token cursor ───────────────────────────────────────────────────────────

class Cursor {
public:
    explicit Cursor(const std::vector<std::string>& tokens) : tokens_(tokens) {}

    bool at_end() const { return pos_ >= tokens_.size(); }

    const std::string& peek() const {
        static const std::string empty;
        return at_end() ? empty : tokens_[pos_];
    }

    std::string consume() {
        if (at_end()) throw std::runtime_error("Unexpected end of PDDL token stream");
        return tokens_[pos_++];
    }

    void expect(const std::string& s) {
        std::string t = consume();
        if (t != s)
            throw std::runtime_error("Expected '" + s + "' but got '" + t + "'");
    }

private:
    const std::vector<std::string>& tokens_;
    std::size_t pos_{0};
};

// ── Parser helpers ─────────────────────────────────────────────────────────

// Format a ground/parametric predicate as "name(arg1,arg2,...)" or "name" if
// there are no arguments. This is the canonical string fed to PredicateIndex.
static std::string format_pred(const std::string& name,
                                const std::vector<std::string>& args) {
    if (args.empty()) return name;
    std::string s = name + "(";
    for (std::size_t i = 0; i < args.size(); ++i) {
        if (i) s += ',';
        s += args[i];
    }
    s += ')';
    return s;
}

// Parse a typed name list: name1 name2 - type  name3 - type2 ...
// Appends (name, type) pairs to out_names / out_types.
static void parse_typed_list(Cursor& cur,
                              std::vector<std::string>& out_names,
                              std::vector<std::string>& out_types,
                              const std::string& default_type = "object") {
    std::vector<std::string> pending;
    while (cur.peek() != ")") {
        std::string tok = cur.consume();
        if (tok == "-") {
            std::string type = cur.consume();
            for (auto& n : pending) {
                out_names.push_back(n);
                out_types.push_back(type);
            }
            pending.clear();
        } else {
            pending.push_back(tok);
        }
    }
    // Names with no explicit type marker
    for (auto& n : pending) {
        out_names.push_back(n);
        out_types.push_back(default_type);
    }
}

// Recursively parse a PDDL condition/effect s-expression.
// Positive atoms go into pos, negated atoms into neg.
static void parse_condition(Cursor& cur,
                             std::vector<std::string>& pos,
                             std::vector<std::string>& neg) {
    cur.expect("(");
    if (cur.peek() == ")") { cur.consume(); return; } // empty ()

    const std::string head = cur.peek();

    if (head == "and") {
        cur.consume();
        while (cur.peek() != ")")
            parse_condition(cur, pos, neg);

    } else if (head == "not") {
        cur.consume();
        cur.expect("(");
        std::string pred = cur.consume();
        std::vector<std::string> args;
        while (cur.peek() != ")") args.push_back(cur.consume());
        cur.expect(")");
        neg.push_back(format_pred(pred, args));

    } else {
        // Positive atom: (predicate arg1 arg2 ...)
        std::string pred = cur.consume();
        std::vector<std::string> args;
        while (cur.peek() != ")") args.push_back(cur.consume());
        pos.push_back(format_pred(pred, args));
    }

    cur.expect(")");
}

// Parse a goal expression, collecting only the positive ground atoms.
static void parse_goal(Cursor& cur, std::vector<std::string>& goal_facts) {
    cur.expect("(");
    if (cur.peek() == ")") { cur.consume(); return; }

    const std::string head = cur.peek();

    if (head == "and") {
        cur.consume();
        while (cur.peek() != ")")
            parse_goal(cur, goal_facts);

    } else {
        std::string pred = cur.consume();
        std::vector<std::string> args;
        while (cur.peek() != ")") args.push_back(cur.consume());
        goal_facts.push_back(format_pred(pred, args));
    }

    cur.expect(")");
}

// Skip a balanced sub-expression when pos_ is just AFTER the opening '('.
// Returns after consuming the matching ')'.
static void skip_section(Cursor& cur) {
    int depth = 1;
    while (depth > 0) {
        std::string t = cur.consume();
        if (t == "(") ++depth;
        else if (t == ")") --depth;
    }
}

// ── Domain parsing ─────────────────────────────────────────────────────────

ParsedDomain PddlParser::parse_domain(const std::string& path) {
    std::ifstream f(path);
    if (!f) throw std::runtime_error("Cannot open domain file: " + path);
    std::string src((std::istreambuf_iterator<char>(f)),
                     std::istreambuf_iterator<char>());

    auto tokens = tokenise(src);
    Cursor cur(tokens);

    // (define (domain <name>) ...)
    cur.expect("(");
    cur.expect("define");
    cur.expect("(");
    cur.expect("domain");
    ParsedDomain d;
    d.name = cur.consume();
    cur.expect(")");

    // Domain sections
    while (!cur.at_end() && cur.peek() != ")") {
        cur.expect("(");
        std::string section = cur.consume();

        if (section == ":requirements") {
            // Skip all requirement keywords
            while (cur.peek() != ")") cur.consume();

        } else if (section == ":types") {
            // Typed list: name1 name2 - parent  name3 - parent2 ...
            std::vector<std::string> names, types;
            parse_typed_list(cur, names, types, "");
            for (std::size_t i = 0; i < names.size(); ++i)
                d.types[types[i]].push_back(names[i]);

        } else if (section == ":predicates") {
            // Each predicate: (name ?p1 - type ...)
            while (cur.peek() != ")") {
                cur.expect("(");
                d.predicates_raw.push_back(cur.consume());
                while (cur.peek() != ")") cur.consume(); // skip typed params
                cur.expect(")");
            }

        } else if (section == ":action") {
            ActionSchema schema;
            schema.name = cur.consume();

            while (cur.peek() != ")") {
                std::string kw = cur.consume();

                if (kw == ":parameters") {
                    cur.expect("(");
                    parse_typed_list(cur, schema.param_names, schema.param_types);
                    cur.expect(")");

                } else if (kw == ":precondition") {
                    parse_condition(cur, schema.pos_pre_raw, schema.neg_pre_raw);

                } else if (kw == ":effect") {
                    parse_condition(cur, schema.add_eff_raw, schema.del_eff_raw);

                } else {
                    // Unknown keyword — skip its value (one balanced s-expr)
                    if (cur.peek() == "(") {
                        cur.consume(); // consume opening (
                        skip_section(cur);
                    } else {
                        cur.consume();
                    }
                }
            }
            d.actions.push_back(schema);

        } else {
            // Unknown section — skip balanced content then fall through to expect(")")
            skip_section(cur);
            continue; // skip_section already consumed the closing )
        }

        cur.expect(")");
    }
    cur.expect(")"); // closes (define ...)
    return d;
}

// ── Problem parsing ────────────────────────────────────────────────────────

ParsedProblem PddlParser::parse_problem(const std::string& path) {
    std::ifstream f(path);
    if (!f) throw std::runtime_error("Cannot open problem file: " + path);
    std::string src((std::istreambuf_iterator<char>(f)),
                     std::istreambuf_iterator<char>());

    auto tokens = tokenise(src);
    Cursor cur(tokens);

    // (define (problem <name>) ...)
    cur.expect("(");
    cur.expect("define");
    cur.expect("(");
    cur.expect("problem");
    ParsedProblem p;
    p.name = cur.consume();
    cur.expect(")");

    // Problem sections
    while (!cur.at_end() && cur.peek() != ")") {
        cur.expect("(");
        std::string section = cur.consume();

        if (section == ":domain") {
            p.domain_name = cur.consume();

        } else if (section == ":objects") {
            // Typed object list: name1 name2 - type ...
            std::vector<std::string> names, types;
            parse_typed_list(cur, names, types);
            for (std::size_t i = 0; i < names.size(); ++i)
                p.objects[types[i]].push_back(names[i]);

        } else if (section == ":init") {
            // Flat list of ground atoms: (pred arg1 arg2 ...)
            while (cur.peek() != ")") {
                cur.expect("(");
                std::string pred = cur.consume();
                std::vector<std::string> args;
                while (cur.peek() != ")") args.push_back(cur.consume());
                cur.expect(")");
                p.init_facts.push_back(format_pred(pred, args));
            }

        } else if (section == ":goal") {
            parse_goal(cur, p.goal_facts);

        } else {
            // Unknown section
            skip_section(cur);
            continue;
        }

        cur.expect(")");
    }
    cur.expect(")"); // closes (define ...)
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

#!/usr/bin/env bash
# Run all IPC benchmark problems through the planner_node binary and report
# plan length, node expansions, and wall-clock time.
#
# Usage (from repo root or from planner/):
#   ./tests/run_benchmarks.sh [path/to/planner_node] [--verbose]
#
# Defaults:  planner_node = ./build/planner_node
#            PDDL files   = ./tests/benchmarks/

set -euo pipefail

PLANNER=${1:-"$(dirname "$0")/../build/planner_node"}
BENCH_DIR="$(dirname "$0")/benchmarks"
VERBOSE=${2:-""}

if [[ ! -x "$PLANNER" ]]; then
    echo "ERROR: planner_node not found at $PLANNER"
    echo "Build first:  cd build && cmake .. && make -j"
    exit 1
fi

PASS=0
FAIL=0

run_case() {
    local label=$1
    local domain=$2
    local problem=$3
    local expected_len=$4

    local extra_args=""
    [[ -n "$VERBOSE" ]] && extra_args="--verbose"

    local t_start t_end elapsed_ms plan_len nodes_exp
    t_start=$(date +%s%N)
    local output
    if output=$("$PLANNER" "$domain" "$problem" $extra_args 2>&1); then
        t_end=$(date +%s%N)
        elapsed_ms=$(( (t_end - t_start) / 1000000 ))

        # parse JSON: extract "length" and implicitly count from "actions"
        plan_len=$(echo "$output" | python3 -c \
            "import sys,json; d=json.load(sys.stdin); print(d['length'])" 2>/dev/null || echo "?")
        nodes_exp=$(echo "$output" | grep -oP '(?<=nodes_expanded\s*=?\s*)\d+' 2>/dev/null \
                    || echo "?")

        local status="OK"
        if [[ "$plan_len" == "$expected_len" ]]; then
            status="OK (optimal)"
        elif [[ "$plan_len" != "?" ]] && (( plan_len > expected_len )); then
            status="SUBOPTIMAL (got $plan_len, expected $expected_len)"
        fi

        printf "  %-35s  len=%-4s  time=%-6s ms  %s\n" \
               "$label" "$plan_len" "$elapsed_ms" "$status"
        PASS=$((PASS + 1))
    else
        printf "  %-35s  FAILED\n" "$label"
        FAIL=$((FAIL + 1))
    fi
}

echo "========================================"
echo " ThePlanner — IPC Benchmark Suite"
echo " binary: $PLANNER"
echo "========================================"
echo ""

echo "[ Blocksworld ]"
run_case "p01  2-block swap"       "$BENCH_DIR/blocksworld/domain.pddl" "$BENCH_DIR/blocksworld/p01.pddl"  4
run_case "p02  3-block tower"      "$BENCH_DIR/blocksworld/domain.pddl" "$BENCH_DIR/blocksworld/p02.pddl"  4
run_case "p03  4-block tower"      "$BENCH_DIR/blocksworld/domain.pddl" "$BENCH_DIR/blocksworld/p03.pddl"  6

echo ""
echo "[ Gripper ]"
run_case "p01  2 balls → room2"    "$BENCH_DIR/gripper/domain.pddl"     "$BENCH_DIR/gripper/p01.pddl"      5
run_case "p02  4 balls → room2"    "$BENCH_DIR/gripper/domain.pddl"     "$BENCH_DIR/gripper/p02.pddl"     11

echo ""
echo "[ Logistics ]"
run_case "p01  2 packages → loc2"  "$BENCH_DIR/logistics/domain.pddl"   "$BENCH_DIR/logistics/p01.pddl"    5

echo ""
echo "========================================"
echo " Results: $PASS passed, $FAIL failed"
echo "========================================"

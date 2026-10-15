"""Evaluate the text-to-SQL system on a test set of questions with known answers.

Usage (from the project root):
    python src/evaluate.py --check-gold     # check that every reference query runs
    python src/evaluate.py                  # evaluate WITHOUT the business glossary
    python src/evaluate.py --glossary       # evaluate WITH the business glossary
    python src/evaluate.py --agent          # evaluate the LangGraph agent (glossary + check-and-fix loop)
"""
import argparse
import math
import numbers
import time
from pathlib import Path

import duckdb
import pandas as pd
import yaml

from agent import run_agent
from text_to_sql import DB_PATH, generate_sql

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_PATH = ROOT / "eval" / "questions.yaml"
RESULTS_DIR = ROOT / "eval" / "results"


# ---------- Comparing two query results ----------

def to_number(value):
    """Return the value as a float if it is a number, otherwise None."""
    if isinstance(value, bool) or not isinstance(value, numbers.Number):
        return None
    value = float(value)
    return None if math.isnan(value) else value


def values_match(gold, generated, scale):
    """Compare two cells: numbers with a small tolerance, text case-insensitively."""
    g, n = to_number(gold), to_number(generated)
    if g is not None and n is not None:
        return math.isclose(g * scale, n, rel_tol=1e-3, abs_tol=1e-6)
    if g is None and n is None:
        return str(gold).strip().lower() == str(generated).strip().lower()
    return False


def row_contained(gold_row, generated_row, scale):
    """True if every value of the gold row is found in the generated row.
    Extra columns in the generated row are allowed."""
    remaining = list(generated_row)
    for gold_value in gold_row:
        for k, generated_value in enumerate(remaining):
            if values_match(gold_value, generated_value, scale):
                remaining.pop(k)
                break
        else:
            return False
    return True


def results_match(gold_df, generated_df):
    """Compare two results, ignoring column names, column order and row order.
    A ratio (0.03) and a percentage (3.0) are considered equivalent."""
    if len(gold_df) != len(generated_df):
        return False
    gold_rows = [tuple(row) for row in gold_df.itertuples(index=False)]
    generated_rows = [tuple(row) for row in generated_df.itertuples(index=False)]

    for scale in (1, 100, 0.01):
        unused = list(range(len(generated_rows)))
        all_found = True
        for gold_row in gold_rows:
            for j in unused:
                if row_contained(gold_row, generated_rows[j], scale):
                    unused.remove(j)
                    break
            else:
                all_found = False
                break
        if all_found:
            return True
    return False



# ---------- Getting the SQL (simple chain or agent) ----------
# only SQL, no response needed for evaluation
def get_sql(question, con, mode):
    """Return (sql, number of SQL attempts) for the chosen mode."""
    if mode == "agent":
        state = run_agent(question, con, write_answer=False)
        return state.get("sql", ""), state.get("attempts", 1)
    return generate_sql(question, con, with_glossary=(mode == "with_glossary")), 1

# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser(description="Evaluate the text-to-SQL system.")
    parser.add_argument("--glossary", action="store_true", help="give the business glossary to the LLM")
    parser.add_argument("--agent", action="store_true", help="evaluate the LangGraph agent (always uses the glossary)")
    parser.add_argument("--check-gold", action="store_true", help="only check that every reference query runs")
    parser.add_argument("--delay", type=float, default=6.0, help="seconds between LLM calls (free-tier rate limit)")
    args = parser.parse_args()

    questions = yaml.safe_load(QUESTIONS_PATH.read_text(encoding="utf-8"))
    con = duckdb.connect(str(DB_PATH), read_only=True)

    # Step 1: check that the reference queries themselves are valid
    if args.check_gold:
        for q in questions:
            try:
                df = con.sql(q["gold_sql"]).df()
                print(f"[OK]    {q['id']:>2}  {len(df)} row(s)  {q['question']}")
            except Exception as error:
                print(f"[ERROR] {q['id']:>2}  {q['question']}\n        {error}")
        return

    # Step 2: ask every question to the LLM and compare with the expected answer
    if args.agent:
        mode = "agent"
    elif args.glossary:
        mode = "with_glossary"
    else:
        mode = "without_glossary"
    
    print(f"Evaluating {len(questions)} questions ({mode})...\n")
    rows = []
    for q in questions:
        gold_df = con.sql(q["gold_sql"]).df()
        generated_sql, error, passed, attempts = "", "", False, 0
        start = time.time()
        try:
            generated_sql, attempts = get_sql(q["question"], con, mode)
            generated_df = con.sql(generated_sql).df()
            passed = results_match(gold_df, generated_df)
        except Exception as e:
            error = str(e)[:300]
        latency = round(time.time() - start, 2)

        status = "PASS" if passed else ("ERROR" if error else "FAIL")
        fixed = f"  (fixed after {attempts} attempts)" if attempts > 1 else ""
        print(f"[{status:5}] {q['id']:>2} ({q['level']:8}) {q['question']}{fixed}")        
        rows.append({
            "id": q["id"],
            "level": q["level"],
            "question": q["question"],
            "mode": mode,
            "passed": passed,
            "status": status,
            "latency_s": latency,
            "attempts": attempts,
            "generated_sql": generated_sql,
            "error": error,
        })
        time.sleep(args.delay)

    results = pd.DataFrame(rows)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / f"results_{mode}.csv"
    results.to_csv(output_path, index=False)

    print("\n" + "=" * 50)
    print(f"Overall accuracy: {results['passed'].mean():.0%} ({results['passed'].sum()}/{len(results)})")
    for level, group in results.groupby("level", sort=False):
        print(f"  {level:9} {group['passed'].mean():.0%} ({group['passed'].sum()}/{len(group)})")
    print(f"\nDetailed results saved to {output_path}")


if __name__ == "__main__":
    main()

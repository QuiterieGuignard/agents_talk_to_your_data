"""Text-to-SQL agent v2 (LangGraph).

The agent works like a careful analyst:
    write the SQL -> run it -> check the result -> fix it if needed (max 3 attempts) -> write the answer
"""
import argparse
from typing import Optional, TypedDict

import duckdb
import pandas as pd
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph

import text_to_sql as t2s

MAX_ATTEMPTS = 3

# ---------- 1. The state: the "notebook" the agent fills in as it works ----------

class AgentState(TypedDict, total=False):
    question: str                    # the user's question
    write_answer: bool               # False during evaluation (we only need the SQL)
    sql: str                         # the latest SQL query
    result: Optional[pd.DataFrame]   # the result of the latest query
    error: str                       # the SQL error, if the query failed
    feedback: str                    # what is wrong with the latest attempt ("" = all good)
    attempts: int                    # number of SQL attempts so far
    answer: str                      # the final answer in natural language
    trace: list                      # log of the steps, to see what the agent did


    # ---------- 2. The checks: rules that detect a suspicious result ----------

def expects_single_number(question):
    """True for questions like "How many orders...?" (but not "how many ... does EACH state have?")."""
    q = question.lower().strip()
    return q.startswith("how many") and not any(word in q for word in (" each", " per ", " by "))


def find_problem(question, result, error):
    """Return a description of the problem, or "" if the result looks fine."""
    if error:
        return f"The query failed with this error: {error}"
    if result is None or len(result) == 0:
        return "The query returned no rows. Check the filters, the join conditions and the values used (e.g. category names, status values)."
    if expects_single_number(question) and len(result) > 1:
        return (f"The question asks for a single number, but the query returned {len(result)} rows. "
                "Aggregate the result into one number (for example: group in a CTE, then COUNT(*) its rows).")
    if len(result) == 1 and result.isna().all(axis=None):
        return ("The query returned only NULL values. If no rows match because there is genuinely no data "
                "(e.g. no sales in the period), keep the same filters and wrap the aggregate in COALESCE(..., 0). "
                "Otherwise, check the filters.")
    return ""

# ---------- 3. The prompt used to write the final answer ----------

ANSWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a data analyst at Olist, presenting results to a business manager.
Answer the question in 2 to 4 sentences, in the same language as the question.
- Use only the figures in the query result. Never invent a figure.
- Round numbers sensibly and give units: amounts are in Brazilian reais (BRL), rates in %, durations in days.
- If the question is about "this month" (the current month), warn that this month is incomplete and not comparable with complete months.
- State the exact period the figures refer to (e.g. "in August 2018") ONLY if it appears in the query result. Never deduce or guess a period from the SQL query.- A result of 0 is a valid answer (e.g. no sales in the period): state it clearly. Only say that you could not answer if the query failed."""
     ),
    ("human", "Question: {question}\n\nSQL query used:\n{sql}\n\nQuery result (first rows):\n{result}"),
])
# ---------- 4. The graph ----------

def build_agent(con):
    """Build the LangGraph agent for a given database connection."""

    def generate_sql(state: AgentState):
        """Node 1: ask the LLM to write the SQL (or to fix the previous one)."""
        question = state["question"]
        if state.get("feedback"):
            question += (
                f"\n\nYour previous query was:\n{state['sql']}\n\n"
                f"Problem: {state['feedback']}\n"
                "Write a corrected query."
            )
        response = (t2s.PROMPT | t2s.llm).invoke({
            "schema": t2s.get_schema(con),
            "knowledge": "Business documentation:\n" + t2s.load_knowledge(),
            "question": question,
        })
        attempts = state.get("attempts", 0) + 1
        return {
            "sql": t2s.clean_sql(response.text),
            "attempts": attempts,
            "trace": state.get("trace", []) + [f"generate_sql (attempt {attempts})"],
        }

    def execute_sql(state: AgentState):
        """Node 2: run the SQL on the database (read-only)."""
        try:
            result, error = con.sql(state["sql"]).df(), ""
        except Exception as e:
            result, error = None, str(e)[:500]
        status = "error" if error else f"{len(result)} row(s)"
        return {"result": result, "error": error,
                "trace": state.get("trace", []) + [f"execute_sql -> {status}"]}

    def check_result(state: AgentState):
        """Node 3: look for a problem in the result."""
        feedback = find_problem(state["question"], state.get("result"), state.get("error"))
        status = f"problem: {feedback}" if feedback else "OK"
        return {"feedback": feedback,
                "trace": state.get("trace", []) + [f"check_result -> {status}"]}

    def write_answer(state: AgentState):
        """Node 4: turn the result into a short answer for a business user."""
        result = state.get("result")
        result_text = result.head(20).to_string(index=False) if result is not None else f"ERROR: {state.get('error')}"
        response = (ANSWER_PROMPT | t2s.llm).invoke({
            "question": state["question"],
            "sql": state["sql"],
            "result": result_text,
        })
        return {"answer": response.text.strip(),
                "trace": state.get("trace", []) + ["write_answer"]}

    def route_after_check(state: AgentState):
        """The decision after the check: fix the SQL, write the answer, or stop."""
        if state.get("feedback") and state.get("attempts", 0) < MAX_ATTEMPTS:
            return "generate_sql"      # loop back and fix the query
        if state.get("write_answer", True):
            return "write_answer"
        return END                     # evaluation mode: the SQL is all we need

    graph = StateGraph(AgentState)
    graph.add_node("generate_sql", generate_sql)
    graph.add_node("execute_sql", execute_sql)
    graph.add_node("check_result", check_result)
    graph.add_node("write_answer", write_answer)

    graph.add_edge(START, "generate_sql")
    graph.add_edge("generate_sql", "execute_sql")
    graph.add_edge("execute_sql", "check_result")
    graph.add_conditional_edges("check_result", route_after_check,
                                ["generate_sql", "write_answer", END])
    graph.add_edge("write_answer", END)
    return graph.compile()


def run_agent(question, con, write_answer=True):
    """Run the agent on one question and return its final state."""
    agent = build_agent(con)
    return agent.invoke({"question": question, "write_answer": write_answer,
                         "attempts": 0, "trace": []})


# ---------- 5. Command line ----------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ask a question to the text-to-SQL agent.")
    parser.add_argument("--question", help="question to ask")
    parser.add_argument("--show-graph", action="store_true", help="print the agent graph as a Mermaid diagram")
    args = parser.parse_args() #lit ce que j'ai tapé

    con = duckdb.connect(str(t2s.DB_PATH), read_only=True)

    if args.show_graph:
        print(build_agent(con).get_graph().draw_mermaid())
    else:
        question = args.question or "How many customers in the South region have ordered more than once?"
        state = run_agent(question, con)
        print(f"Question: {question}\n")
        print("Steps:")
        for step in state["trace"]:
            print(f"  - {step}")
        print(f"\nFinal SQL:\n{state['sql']}\n")
        if state.get("result") is not None:
            print(f"Result:\n{state['result'].head(10).to_string(index=False)}\n")
        print(f"Answer:\n{state.get('answer', '')}")
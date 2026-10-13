"""Text-to-SQL v1: natural-language question -> SQL query -> result.

Usage (from the project root):
    python src/text_to_sql.py                                   # 3 test questions, without glossary
    python src/text_to_sql.py --glossary                        # 3 test questions, with glossary
    python src/text_to_sql.py --glossary --question "..."       # your own question
"""
import argparse
from pathlib import Path

import duckdb
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_mistralai import ChatMistralAI

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "olist.duckdb"
KNOWLEDGE_DIR = ROOT / "knowledge"

llm = ChatMistralAI(model="mistral-medium-latest", temperature=0, max_retries=2)


def get_schema(con):
    """Describe the database tables and columns as text for the LLM."""
    df = con.sql("""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        ORDER BY table_name, ordinal_position
    """).df()
    lines = []
    for table, group in df.groupby("table_name"):
        columns = ", ".join(f"{c} ({t})" for c, t in zip(group["column_name"], group["data_type"]))
        lines.append(f"- {table}: {columns}")
    return "\n".join(lines)


def load_knowledge():
    """Read the data dictionary and the business glossary."""
    files = sorted(KNOWLEDGE_DIR.glob("*.md"))
    return "\n\n".join(f.read_text(encoding="utf-8") for f in files)


PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a SQL expert. You write queries for a DuckDB database.

Database schema:
{schema}

{knowledge}

Rules:
- Answer ONLY with the SQL query, with no explanation and no markdown fences.
- Only write SELECT queries (read-only).
- Limit results to 50 rows maximum.
- When the question asks "how many", return a single number. If you need to group first, do it in a CTE (WITH ...) and count its rows in the final SELECT."""),
    ("human", "{question}"),
])


def clean_sql(text):
    """Remove ```sql ... ``` fences if the LLM added them despite the instructions."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]     # drop the first line (```sql)
        text = text.rsplit("```", 1)[0]   # drop the closing ```
    return text.strip()


def generate_sql(question, con, with_glossary=False):
    """Ask the LLM to write the SQL query that answers the question."""
    knowledge = "Business documentation:\n" + load_knowledge() if with_glossary else ""
    chain = PROMPT | llm
    response = chain.invoke({
        "schema": get_schema(con),
        "knowledge": knowledge,
        "question": question,
    })
    return clean_sql(response.text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ask a question to the database in natural language.")
    parser.add_argument("--glossary", action="store_true", help="give the business glossary to the LLM")
    parser.add_argument("--question", help="question to ask (otherwise, runs the default test questions)")
    args = parser.parse_args()

    con = duckdb.connect(str(DB_PATH), read_only=True)

    questions = [args.question] if args.question else [
        "How many distinct customers does Olist have?",
        "What percentage of customers ordered more than once?",
        "What is the total revenue?",
    ]

    print("WITH GLOSSARY" if args.glossary else "WITHOUT GLOSSARY")
    for question in questions:
        sql = generate_sql(question, con, with_glossary=args.glossary)
        print(f"\nQuestion: {question}\nSQL:\n{sql}")
        try:
            print("Result:\n", con.sql(sql).df())
        except Exception as error:
            print("ERROR:", error)

"""Text-to-SQL v1: natural-language question -> SQL query -> result."""
from pathlib import Path

import duckdb
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "olist.duckdb"
KNOWLEDGE_DIR = ROOT / "knowledge"

llm = ChatGoogleGenerativeAI(model="gemini-3.8-flash", temperature=0)


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
- Limit results to 50 rows maximum."""),
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
    """Ask Gemini to write the SQL query that answers the question."""
    knowledge = "Business documentation:\n" + load_knowledge() if with_glossary else ""
    chain = PROMPT | llm
    response = chain.invoke({
        "schema": get_schema(con),
        "knowledge": knowledge,
        "question": question,
    })
    return clean_sql(response.text)


if __name__ == "__main__":
    con = duckdb.connect(str(DB_PATH), read_only=True)

    questions = [
        "How many distinct customers does Olist have?",
        "What percentage of customers ordered more than once?",
        "What is the total revenue?",
    ]

    for with_glossary in [False, True]:
        print("\n" + "=" * 70)
        print("WITH GLOSSARY" if with_glossary else "WITHOUT GLOSSARY")
        print("=" * 70)
        for question in questions:
            sql = generate_sql(question, con, with_glossary=with_glossary)
            print(f"\nQuestion: {question}\nSQL:\n{sql}")
            try:
                print("Result:\n", con.sql(sql).df())
            except Exception as error:
                print("ERROR:", error)

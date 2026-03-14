"""
Proof of concept: RAG-powered budget chat.

Seeds a local SQLite database with sample transactions,
then lets you ask questions answered using your real spending data.

Run:
    pip install anthropic
    python budget_chat.py
"""

import anthropic
import sqlite3
import json
from datetime import datetime
from pathlib import Path


# ── Sample data to seed the demo ──
SAMPLE_TRANSACTIONS = [
    ("2026-03-01", "income",  1800.00, "income",         "monthly salary"),
    ("2026-03-02", "expense",   14.50, "food",           "lunch"),
    ("2026-03-02", "expense",   16.00, "subscriptions",  "Netflix"),
    ("2026-03-03", "expense",   67.00, "food",           "grocery run"),
    ("2026-03-04", "expense",   12.00, "transport",      "Uber"),
    ("2026-03-05", "expense",   85.00, "entertainment",  "dinner out with friends"),
    ("2026-03-06", "expense",    5.50, "food",           "coffee"),
    ("2026-03-07", "expense",  850.00, "rent",           "monthly rent"),
    ("2026-03-08", "expense",   34.00, "transport",      "gas"),
    ("2026-03-09", "expense",   22.00, "food",           "takeout"),
    ("2026-03-10", "expense",   16.00, "subscriptions",  "Spotify"),
    ("2026-03-11", "expense",   48.00, "food",           "groceries"),
    ("2026-03-12", "expense",   60.00, "entertainment",  "concert tickets"),
    ("2026-03-13", "expense",   11.00, "food",           "coffee and bagel"),
]


def setup_demo_db(db_path: str = "demo_budget.db"):
    """Create a demo SQLite database seeded with sample transactions."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT,
            type        TEXT,
            amount      REAL,
            category    TEXT,
            description TEXT
        )
    """)
    conn.execute("DELETE FROM transactions")  # reset on each run
    conn.executemany(
        "INSERT INTO transactions (date, type, amount, category, description) VALUES (?,?,?,?,?)",
        SAMPLE_TRANSACTIONS
    )
    conn.commit()
    return conn


def build_context(conn) -> str:
    """
    Summarize transaction history into a readable text block.
    This is the 'retrieval' step in RAG — pulling real data
    before passing it to the AI.
    """
    rows = conn.execute(
        "SELECT type, amount, category FROM transactions"
    ).fetchall()

    total_income  = sum(r[1] for r in rows if r[0] == "income")
    total_expense = sum(r[1] for r in rows if r[0] == "expense")

    by_category = {}
    for r in rows:
        if r[0] == "expense":
            by_category[r[2]] = by_category.get(r[2], 0) + r[1]

    category_lines = "\n".join(
        f"  {cat}: ${amt:.2f}"
        for cat, amt in sorted(by_category.items(), key=lambda x: -x[1])
    )

    return f"""Total income:   ${total_income:.2f}
Total expenses: ${total_expense:.2f}
Net balance:    ${total_income - total_expense:.2f}

Spending by category:
{category_lines}"""


def ask(question: str, context: str, api_key: str) -> str:
    """
    Inject spending context into the system prompt, then answer the question.
    This is the 'augmented generation' step in RAG.
    """
    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=400,
        system=f"""You are Budget Brain, a personal finance assistant.
Answer questions using ONLY the data below. Be direct. Reference actual numbers.
Do not give generic advice — ground everything in the user's real spending.

USER'S SPENDING DATA:
{context}""",
        messages=[{"role": "user", "content": question}]
    )

    return response.content[0].text


if __name__ == "__main__":
    API_KEY = input("Enter your Anthropic API key: ").strip()

    print("\nSetting up demo database with sample transactions...")
    conn = setup_demo_db()
    context = build_context(conn)

    print("\n--- Your spending data ---")
    print(context)

    print("\n--- Budget Brain Chat POC ---")
    print("Type a question about your finances. Press Ctrl+C to quit.\n")

    demo_questions = [
        "Where is most of my money going?",
        "Am I spending too much on food?",
        "Am I on track to save anything this month?",
    ]

    for q in demo_questions:
        print(f"Q: {q}")
        answer = ask(q, context, API_KEY)
        print(f"A: {answer}\n")
        print("-" * 50 + "\n")

    # Interactive mode
    while True:
        try:
            user_q = input("Ask your own question (or Ctrl+C to quit): ").strip()
            if user_q:
                print(ask(user_q, context, API_KEY))
                print()
        except KeyboardInterrupt:
            print("\nDone.")
            break

    conn.close()
    Path("demo_budget.db").unlink(missing_ok=True)  # clean up demo db

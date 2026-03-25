# Vados

> Log your spending in plain English. Get AI-powered warnings before you overspend — not after.

---

## The Problem

Every budgeting app shows you a pie chart of last month's spending. That's not helpful. By the time you see it, the money is already gone.

**Vados warns you while you can still do something about it.**

---

## How It Works

You type how you spend money the same way you'd text a friend:

```
"spent $14 on lunch"
"paid $850 rent"  
"got paid $1200"
"Netflix $16"
```

The app figures out the rest — amount, category, whether it's income or an expense. No forms, no dropdowns, no manual tagging.

Once you've logged a few transactions, you can ask it anything:

> *"Am I on track to save money this month?"*
> *"What am I spending the most on?"*
> *"Should I be worried about my dining budget?"*

And it answers using your actual numbers, not generic advice.

---

## The Three Core Ideas

### 1. Natural language input
You log transactions by typing normally. An AI reads what you wrote and converts it into a structured record — amount, category, date, type. No friction.

### 2. Everything stored locally
Every transaction goes into a lightweight database on your own machine. Your data never leaves your computer (except the text you type, which gets sent to the AI to be parsed).

### 3. AI that knows your actual numbers
When you ask a question, the app first pulls a summary of your spending history, then passes that summary to the AI alongside your question. The AI answers based on your real data — not generic budgeting advice pulled from the internet.

This pattern (retrieve real data → inject into AI prompt → get grounded answer) is called **RAG (Retrieval-Augmented Generation)**. It's the same technique used in enterprise AI tools to make LLMs answer questions about specific documents or databases.

---

## What It Looks Like

**Logging a transaction:**
```
You type:   "grabbed coffee and a bagel, $11"

AI parses:
  type     → expense
  amount   → $11.00
  category → food
  date     → 2026-03-13
```

**Asking a question:**
```
You ask:  "Where is most of my money going this month?"

AI sees your data:
  food: $180, rent: $850, transport: $45, entertainment: $90 ...

AI answers:
  "Rent is your biggest expense at $850, which is expected.
   After that, food is $180 — you're averaging $12/day,
   which is on the higher side if you're trying to save.
   Consider cooking a few more meals at home."
```

---

## Feasibility

Everything in Vados is built on tools that exist today and are free to use.

| Piece | Tool | Why it works |
|---|---|---|
| Natural language parsing | Anthropic Claude API | State-of-the-art language understanding |
| Local database | SQLite | Built into Python, zero setup |
| RAG context layer | Python + Claude API | Summarize DB → inject into prompt |
| Web interface | Streamlit | Python-native UI, runs locally in browser |

No external servers. No paid subscriptions beyond the AI API. Runs on any laptop.

---

## Proof of Concept

The two hardest pieces to believe — natural language parsing and RAG-powered chat — work today with a small amount of code. Here's the core logic for both.

### Piece 1: Parsing a transaction from plain text

This is the function that takes whatever you type and converts it into a structured record.

```python
import anthropic
import json
from datetime import datetime

def parse_transaction(user_input: str, api_key: str) -> dict:
    """
    Takes free-text like "spent $14 on lunch" and returns:
    {
        "type": "expense",
        "amount": 14.0,
        "category": "food",
        "description": "lunch",
        "date": "2026-03-13"
    }
    """
    client = anthropic.Anthropic(api_key=api_key)
    today  = datetime.today().strftime("%Y-%m-%d")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        system=f"""You are a transaction parser. Extract info from natural language
and return ONLY a JSON object with these fields:
  type        → "expense" or "income"
  amount      → positive number
  category    → one of: food, transport, rent, subscriptions, health, entertainment, shopping, income, other
  description → short clean label
  date        → "{today}"
Return only the JSON. No explanation.""",
        messages=[{"role": "user", "content": user_input}]
    )

    return json.loads(response.content[0].text.strip())


# --- Try it ---
result = parse_transaction("grabbed coffee and a bagel, $11", api_key="YOUR_KEY")
print(result)
# → {'type': 'expense', 'amount': 11.0, 'category': 'food', 'description': 'coffee and bagel', 'date': '2026-03-13'}
```

**Why this works:** Claude is trained on enormous amounts of text and understands natural language extremely well. Asking it to extract structured fields from a sentence is a task it handles reliably, even with messy or ambiguous input.

---

### Piece 2: Answering questions using your real spending data (RAG)

This is the function that pulls your transaction history, summarizes it, and injects it into the AI's context before answering your question.

```python
import sqlite3
import anthropic

def ask_vados(question: str, api_key: str) -> str:
    """
    Pulls spending summary from the database, injects it as context,
    and returns an AI answer grounded in the user's real numbers.
    """

    # Step 1: Pull spending data from SQLite
    conn = sqlite3.connect("data/vados.db")
    rows = conn.execute(
        "SELECT type, amount, category, description, date FROM transactions ORDER BY date DESC LIMIT 100"
    ).fetchall()
    conn.close()

    # Step 2: Summarize it into a readable block (the "retrieval" in RAG)
    total_income  = sum(r[1] for r in rows if r[0] == "income")
    total_expense = sum(r[1] for r in rows if r[0] == "expense")

    by_category = {}
    for r in rows:
        if r[0] == "expense":
            by_category[r[2]] = by_category.get(r[2], 0) + r[1]

    category_summary = ", ".join(
        f"{cat}: ${amt:.2f}"
        for cat, amt in sorted(by_category.items(), key=lambda x: -x[1])
    )

    context = f"""
    Total income:   ${total_income:.2f}
    Total expenses: ${total_expense:.2f}
    Net balance:    ${total_income - total_expense:.2f}
    By category:    {category_summary}
    """

    # Step 3: Inject context into the AI prompt (the "augmented generation" in RAG)
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=400,
        system=f"""You are Vados, a personal finance assistant.
Answer questions using ONLY the data below. Be specific. Reference actual numbers.

USER'S SPENDING DATA:
{context}""",
        messages=[{"role": "user", "content": question}]
    )

    return response.content[0].text


# --- Try it ---
answer = ask_vados("Am I spending too much on food?", api_key="YOUR_KEY")
print(answer)
# → "Your food spending is $180 this month, which works out to about $12/day.
#    If your goal is to save more, that's one of the easier categories to trim —
#    even cutting $3/day gets you $90 back by end of month."
```

**Why this works:** The AI doesn't guess. It reads your actual numbers before answering. The context block is rebuilt fresh on every question, so answers always reflect your current data.

---
## Test Results

These are real outputs from running the POC — not mock data.

### Transaction parser

The parser correctly identified the type, amount, category, and description from plain English input across all 5 test cases.

Input:  "grabbed coffee and a bagel, $11"
Output: { "type": "expense", "amount": 11, "category": "food", "description": "coffee and bagel", "date": "2026-03-25" }

Input:  "paid $850 rent"
Output: { "type": "expense", "amount": 850, "category": "rent", "description": "rent payment", "date": "2026-03-25" }

Input:  "got paid $1200 from freelance project"
Output: { "type": "income", "amount": 1200, "category": "income", "description": "freelance project payment", "date": "2026-03-25" }

Input:  "Uber to the airport $34"
Output: { "type": "expense", "amount": 34, "category": "transport", "description": "Uber to airport", "date": "2026-03-25" }

Input:  "Netflix subscription $16"
Output: { "type": "expense", "amount": 16, "category": "subscriptions", "description": "Netflix subscription", "date": "2026-03-25" }

Key observations:
- Correctly distinguished income vs expense without being told explicitly
- Pulled the exact dollar amount from varied input formats
- Assigned the right category every time with no manual tagging
- Cleaned up descriptions into short, consistent labels

---

### RAG chat

The chat was seeded with sample transaction data and asked 3 questions. All answers reference real numbers from the data — no generic advice.

Spending data used:
  Total income:   $1800.00
  Total expenses: $1241.00
  Net balance:    $559.00
  rent: $850 | food: $168 | entertainment: $145 | transport: $46 | subscriptions: $32

Q: Where is most of my money going?
A: Rent at $850 accounts for 68% of total expenses. Food is second at $168 (14%),
   followed by entertainment at $145 (12%), transport at $46 (4%), and subscriptions
   at $32 (3%). Rent takes up nearly half (47%) of total income.

Q: Am I spending too much on food?
A: Food spending of $168 is about 9.3% of income — within the recommended 10-15%
   range. Food appears well-controlled. The bigger budget pressure is rent at 47%
   of income.

Q: Am I on track to save anything this month?
A: Yes. Income of $1,800 exceeds expenses of $1,241, leaving a net balance of $559
   — about 31% of income going toward savings.

Key observations:
- Every answer cited specific dollar amounts from the actual data
- The AI correctly calculated percentages on its own
- Answers were comparative — contextualizing each number against the others
- No generic advice — everything was grounded in the numbers provided

## What's Next

This POC demonstrates the two hardest pieces. A full version would add:

- **A proper UI** (Streamlit — a Python library that turns scripts into web apps)
- **Persistent storage** (SQLite — already shown above, zero setup)
- **A spending dashboard** — bar chart of categories, running monthly totals
- **Proactive weekly insight** — the AI surfaces one finding without you having to ask
- **ML models (v2)** — once enough personal data is collected:
  - A regression model that predicts your end-of-month balance
  - A classifier that flags categories at risk of going over budget mid-month

---

## Running the POC yourself

You need Python and an Anthropic API key (free tier available at [console.anthropic.com](https://console.anthropic.com)).

```bash
pip install anthropic
```

Then copy either function above into a `.py` file, swap in your API key, and run it. Both work independently — no database setup needed to test the parser.

---

## Tech Stack

- Python
- Anthropic Claude API
- SQLite
- Streamlit (for the full UI)

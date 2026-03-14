"""
Proof of concept: natural language transaction parser.

Takes free-text input like "spent $14 on lunch" and returns
a structured record with amount, category, type, and date.

Run:
    pip install anthropic
    python parse_transaction.py
"""

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
  type        -> "expense" or "income"
  amount      -> positive number
  category    -> one of: food, transport, rent, subscriptions, health, entertainment, shopping, income, other
  description -> short clean label
  date        -> "{today}"
Return only the JSON. No explanation.""",
        messages=[{"role": "user", "content": user_input}]
    )

    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


if __name__ == "__main__":
    API_KEY = input("Enter your Anthropic API key: ").strip()

    test_inputs = [
        "grabbed coffee and a bagel, $11",
        "paid $850 rent",
        "got paid $1200 from freelance project",
        "Uber to the airport $34",
        "Netflix subscription $16",
    ]

    print("\n--- Transaction Parser POC ---\n")
    for text in test_inputs:
        print(f"Input:  {text}")
        result = parse_transaction(text, API_KEY)
        print(f"Output: {json.dumps(result, indent=2)}\n")

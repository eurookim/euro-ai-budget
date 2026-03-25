# Vados — Technical Design Document
**MVP Specification**

Author: Euro Kim
Version: 1.0 — March 2026

---

## Table of Contents

1. [Overview](#1-overview)
2. [MVP Feature List](#2-mvp-feature-list)
3. [User Flow](#3-user-flow)
4. [Feature Details](#4-feature-details)
5. [Out of Scope for MVP](#5-out-of-scope-for-mvp)
6. [Tech Stack](#6-tech-stack)

---

## 1. Overview

Vados is an AI-powered personal finance assistant that lets users log income and expenses in plain English. A single conversational AI handles both transaction parsing and financial Q&A — no forms, no dropdowns, no manual categorization. The MVP is a locally-run web application built in Python.

> **Core premise:** Most budgeting apps tell you where your money went. Vados warns you before it happens — answering questions and surfacing insights grounded in your actual spending data, not generic advice.

---

## 2. MVP Feature List

| Feature | Description | Behavior |
|---|---|---|
| Onboarding flow | First-run setup wizard | Collects spending goals, budget targets, and optional historical averages before first use |
| Unified AI bot | Single chat interface for all interactions | One bot handles transaction logging, categorization, and Q&A — no separate scripts |
| NLP transaction parser | Plain English input → structured record | Extracts amount, type, category, and description; confirms with user before saving |
| Manual correction | Edit or re-categorize any transaction | User can flag a wrong category; bot re-categorizes and updates the record |
| Local database | SQLite storage on user's machine | All transaction data stored locally; never sent to external servers |
| Dashboard | Monthly financial overview | Income, expenses, net balance, spending bars by category, and one AI-generated insight |
| Transaction history | Full log of all entries | Scrollable list with category badges and color-coded amounts |
| Budget targets | Per-category monthly limits | Set in onboarding or anytime; dashboard shows progress toward each limit |
| AI chat | RAG-powered financial Q&A | Answers grounded in real transaction data; multi-turn conversation with context memory |
| Weekly insight | Proactive AI-generated summary | Surfaces one key finding per week without the user having to ask |

---

## 3. User Flow

### 3.1 First-time onboarding

When a user opens Vados for the first time, they are taken through a short onboarding wizard before reaching the main app. The goal is to seed the AI with enough context to give useful answers immediately — without making onboarding feel like a chore.

---

#### Step 1 — Spending goals

The user is asked one open question in plain text:

> *"What are you trying to do with your money? (e.g. save more, pay off debt, build an emergency fund, stop overspending on food)"*

The AI reads the response and stores it as a goals string attached to the user's profile. This is injected into every subsequent AI prompt so answers are always contextualized against what the user actually wants.

---

#### Step 2 — Budget targets

The user is shown the standard spending categories and asked to optionally set a monthly limit for each. This can be skipped entirely and filled in later. Defaults are left blank — Vados does not assume a budget the user did not set.

| Category | Monthly budget | Status |
|---|---|---|
| Food | User inputs or skips | Optional |
| Transport | User inputs or skips | Optional |
| Entertainment | User inputs or skips | Optional |
| Shopping | User inputs or skips | Optional |
| Subscriptions | User inputs or skips | Optional |
| Health | User inputs or skips | Optional |

---

#### Step 3 — Historical spending (optional)

The user is asked if they want to seed the app with previous months' averages. This is optional and fully manual — the user types something like:

> *"Last month I spent about $200 on food, $800 on rent, $50 on transport, and made $1,800."*

The AI parses this the same way it parses individual transactions and stores them as a historical baseline. This allows the app to give useful comparative answers ("you're spending 20% more on food than last month") from day one rather than waiting weeks to accumulate data.

---

#### Step 4 — Enter the app

After completing or skipping onboarding, the user lands on the Dashboard. The AI sends a short welcome message in the chat panel acknowledging their goals and summarizing any budget targets they set.

---

### 3.2 Main app — page structure

The app has four pages accessible from a persistent sidebar.

**Dashboard**
The default landing page. Shows the current month's financial snapshot: total income, total expenses, net balance, a spending bar chart by category, budget progress indicators for any categories with limits set, and one AI-generated insight card. Updated in real time as transactions are logged.

**Log / Chat**
A single unified interface — a chat window where the user types anything. The AI responds in conversational language. If the input looks like a transaction, the AI parses it, confirms with the user, and saves it. If it looks like a question, the AI answers it using the user's spending data as context. The user never has to decide which mode they're in.

**Transaction history**
A full, scrollable list of all logged transactions. Each row shows date, description, category badge, and amount (color-coded green for income, red for expense). Clicking any transaction opens an edit panel where the user can correct the category or description.

**Settings**
Where the user can update their spending goals, adjust monthly budget targets per category, and view or clear their stored historical baseline.

---

### 3.3 Transaction logging flow

The following steps describe what happens from the moment a user types a transaction to the moment it is saved.

1. User types a transaction in the chat window.
2. The AI classifies the message as a transaction or a question. If ambiguous, the AI asks for clarification.
3. The AI parses the transaction and responds with a confirmation card showing the extracted fields: type, amount, category, and description.
4. The user confirms ("yes" or any affirmative) or corrects ("no, that should be entertainment").
5. On confirmation, the record is written to SQLite and the dashboard updates.

> **Design note:** Confirmation before saving is intentional. It gives the user a chance to catch miscategorizations before they hit the database, reducing the need for the correction flow entirely.

---

### 3.4 Exception: incorrect categorization

If the AI categorizes a transaction incorrectly and the user does not catch it at confirmation time, there are two ways to correct it.

**Via chat**
The user can type "that last one should be entertainment, not food" and the AI will find the most recent transaction, update its category, and confirm the change.

**Via transaction history**
Every transaction row has an edit button. Clicking it opens a small panel where the user can change the category from a dropdown or update the description. The change is saved immediately.

> **Future improvement:** In a post-MVP version, user corrections can be logged as labeled examples to fine-tune the categorization model over time — so the same mistake is less likely to recur.

---

## 4. Feature Details

### 4.1 Unified AI bot

The POC split transaction parsing and financial Q&A into two separate scripts. In the MVP these are handled by a single AI with a single chat interface. The bot uses intent classification to decide how to respond:

- If the message contains an amount and describes an action (spent, paid, bought, got paid), it is treated as a transaction to be parsed.
- If the message is a question or request for analysis, it is treated as a Q&A query and answered using the RAG context layer.
- If the message is ambiguous, the bot asks: "Did you want to log that as a transaction, or are you asking about your spending?"

Both paths use the same Claude API call under the hood — the system prompt determines which behavior is triggered. The user never sees the distinction.

---

### 4.2 NLP transaction parser

When the bot identifies a transaction, it sends the user's message to Claude with a structured system prompt that extracts:

- **type** — "income" or "expense"
- **amount** — positive number, no currency symbol
- **category** — one of the fixed category set
- **description** — short clean label generated by the AI
- **date** — today's date unless the user specifies otherwise

The output is returned as JSON, validated against expected types and allowed category values, then shown to the user as a confirmation card before writing to the database.

---

### 4.3 RAG context layer

Every AI response that involves the user's finances — Q&A, insights, budget warnings — is grounded by a context block built fresh from the database before each call. The block contains:

- Total income and total expenses for the current month
- Spending by category for the current month
- Net balance and savings rate
- The 15 most recent transactions
- The user's stated spending goals from onboarding
- Any budget targets set per category and current progress toward them

This block is injected into the system prompt so the AI answers based on the user's real numbers, not general financial knowledge. The context is rebuilt on every call so it always reflects the latest data.

---

### 4.4 Dashboard

The dashboard is the default view and the main way users passively monitor their finances. It contains the following elements:

**Summary cards**
Three metric cards at the top: Total income, Total spent, and Net balance for the current month. Net balance is color-coded green (positive) or red (negative).

**Category spending bars**
A bar chart showing spending per category relative to the largest category. If a budget target is set for a category, the bar shows progress against that limit and turns red if the user has exceeded 80% of their budget with more than a week left in the month.

**AI insight card**
A single sentence surfaced by the AI after analyzing the current month's data. Generated automatically when the user opens the dashboard. Examples: "You're on pace to overspend on dining by $60 this month" or "Your savings rate this month (31%) is the highest it's been in three months."

---

### 4.5 Budget targets and warnings

Budget targets are optional per-category monthly limits set during onboarding or in Settings. When a target is set for a category:

- The dashboard bar for that category shows a limit line and a percentage-used label.
- When spending exceeds 80% of the limit, the bar turns amber.
- When spending exceeds 100%, the bar turns red and the AI insight card flags it proactively.
- The AI chat is aware of all budget targets and references them when answering questions about spending.

---

### 4.6 Data storage

All data is stored locally in a SQLite database on the user's machine. The database has three tables:

| Table | Key fields | Purpose |
|---|---|---|
| transactions | id, date, type, amount, category, description | Every logged income and expense entry |
| user_profile | goals, created_at | Onboarding goals string and app creation date |
| budget_targets | category, monthly_limit | Per-category monthly budget limits set by the user |

No user data is sent to external servers. The only data that leaves the user's machine is the text sent to the Anthropic API for parsing and Q&A.

---

## 5. Out of Scope for MVP

The following features are intentionally excluded from the MVP to keep scope manageable. They are candidates for a v2 release once the core product is validated.

- **ML savings forecaster** — regression model predicting end-of-month balance (requires several months of personal data to train)
- **Overspend risk scorer** — per-category classifier predicting probability of exceeding budget mid-month
- **Subscription detector** — pattern matching to surface recurring charges automatically
- **Bank/card integration** — connecting to financial institutions via Plaid or similar
- **Multi-user support** — shared budgets, household accounts
- **Mobile app** — iOS or Android version
- **Data export** — CSV download of transaction history

---

## 6. Tech Stack

| Layer | Technology | Reason |
|---|---|---|
| UI | Streamlit | Python-native, runs locally in browser, minimal boilerplate |
| AI | Anthropic Claude API | Best-in-class language understanding for parsing and Q&A |
| Database | SQLite | Built into Python, zero setup, local-only storage |
| Language | Python 3.10+ | Single language across all layers, fast iteration |

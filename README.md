🌍 Language: English | 繁體中文

🚀 Automated Marketing Data Pipeline, LLM Sentiment & Risk Profiling System
📌 Overview
This repository contains a comprehensive automated data processing workflow designed to streamline marketing operations, customer sentiment analysis, and user risk profiling. By integrating Python, Large Language Models (Gemini via Poe API), and Google Workspace APIs, this system transforms unstructured daily WhatsApp conversational data into structured, actionable business intelligence across three core modules.

💼 Business Impact
Efficiency Leap: Automated data cleaning, API requests, and dashboard updates reduce daily operational processing time from 2-3 hours to just 15 minutes (over 80% time saved).

Proactive Crisis Management: Leverages LLM to perform advanced sentiment analysis, categorizing feedback (Negative/Positive/Neutral) to instantly flag PR risks for immediate customer service intervention.

Automated Risk Profiling: Analyzes 30-day historical user behavior to automatically identify, score, and flag suspicious accounts (e.g., spam, competitor "seeders", unauthorized business promotions).

Dynamic Management Dashboards: Eliminates manual data entry by programmatically aggregating metrics and pushing them directly to executive Google Sheets dashboards via BatchUpdate APIs.

🛠️ Tech Stack
Language: Python 3.11 (pandas, regex, datetime)

AI & NLP: Gemini-2.5-Flash (via Poe API), Prompt Engineering

Cloud & Integration: Google Drive API (File fetching), Google Sheets API / gspread (Config reading, Data export, & batch formatting)

Performance & Reliability: concurrent.futures (Multi-threading), Custom Exponential Backoff Decorators (API rate-limit handling)

CI/CD & Automation: GitHub Actions (CRON Jobs, Dependency Caching, and granular workflow_dispatch manual triggers)

⚙️ Core Architecture & Modules
1. main.py (Data Pipeline & LLM Engine)
Data Ingestion: Authenticates via a modularized Google Service Account to dynamically search and download daily raw chat logs (.csv/.xlsx) from Google Drive.

Filtering & Deduplication: Reads dynamic configuration from a master Google Sheet, performing strict text deduplication and keyword matching based on time tolerances and user identity scores.

LLM Processing (Multi-threaded): Sends filtered data to the LLM to classify user intent (Spam detection) and perform granular brand sentiment analysis. Writes cleaned data back to daily logs.

2. risk_analysis.py (User Behavior & Risk Engine)
Behavioral Aggregation: Backtracks 30 days of conversational data to construct behavioral profiles for active users (e.g., group join counts, brand mention frequency).

Rule-Based Scoring: Applies a proprietary scoring algorithm to evaluate user risk.

Categorization: Automatically updates the "Sim Master" database, tagging users as Real, Watch, Business, or IFT Seeder for community management.

3. dashboard.py (Dashboard Automation)
Data Synthesis: Aggregates daily group activities, categorizes discussion topics, and calculates brand sentiment ratios.

Batch Updates: Uses the sheets_service.spreadsheets().batchUpdate() API to efficiently overwrite specific dashboard cells, keeping management charts up-to-date without human intervention.

🔒 Security & Reliability Note
Data Privacy: For security and compliance reasons, all sensitive configurations (Google Service Account credentials, API keys, Folder IDs, and Sheet URLs) are strictly managed via Environment Variables and GitHub Secrets. No real customer data or proprietary keys are exposed in this public repository.

Fault Tolerance: All Google API calls are wrapped in a custom @with_retry decorator implementing Exponential Backoff, ensuring the pipeline remains robust against API quota limits and 429 Too Many Requests errors.

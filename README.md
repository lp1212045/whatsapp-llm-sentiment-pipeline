> 🌍 **Language:** English | [繁體中文](README_zh-HK.md)

<br>

# 🚀 Automated Marketing Data Pipeline, LLM Sentiment & Risk Profiling System

## 📌 Overview
This repository contains a comprehensive automated data processing workflow designed to streamline marketing operations, customer sentiment analysis, and user risk profiling. By integrating Python, Large Language Models (Gemini via Poe API), Google Workspace APIs, and AI Agents (Manus AI), this system transforms unstructured daily WhatsApp conversational data into structured, actionable business intelligence across four core modules.

## 💼 Business Impact
* **Efficiency Leap:** Automated data cleaning, API requests, and dashboard updates reduce daily operational processing time from 2-3 hours to just **15 minutes** (over 80% time saved).
* **Proactive Crisis Management:** Leverages LLM to perform advanced sentiment analysis, categorizing feedback (Negative/Positive/Neutral) to instantly flag PR risks for immediate customer service intervention.
* **Automated Risk Profiling:** Analyzes 30-day historical user behavior to automatically identify, score, and flag suspicious accounts (e.g., spam, competitor "seeders", unauthorized business promotions).
* **Zero-Touch Executive Reporting:** Implemented an autonomous AI agent (Manus AI) to validate daily data freshness and push tailored email summaries to stakeholders, ensuring immediate visibility of PR crises without requiring manual dashboard check-ins.

## 🛠️ Tech Stack
* **Language:** Python 3.11 (`pandas`, `regex`, `datetime`)
* **AI & NLP:** Gemini-2.5-Flash (via Poe API), Prompt Engineering
* **Cloud & Integration:** Google Drive API (File fetching), Google Sheets API / `gspread` (Config reading & Data export), Manus AI Agent, Gmail API Connector
* **Performance & Reliability:** `concurrent.futures` (Multi-threading), Custom Exponential Backoff Decorators (API rate-limit handling)
* **CI/CD & Automation:** GitHub Actions (CRON Jobs, Dependency Caching, `workflow_dispatch` manual triggers)

## ⚙️ Core Architecture & Modules

```mermaid
graph TD
    %% 定義節點樣式
    classDef llm fill:#f9f0ff,stroke:#d8b4e2,stroke-width:2px;
    classDef sheet fill:#e6f4ea,stroke:#81c995,stroke-width:2px;
    classDef alert fill:#fce8e6,stroke:#f28b82,stroke-width:2px;

    A[WhatsApp Chat Data] -->|N8N / Auto-sync| B(Google Drive Raw Logs)
    
    subgraph Data Pipeline & AI Engine
    B --> C{main.py<br>Data Processing}
    C <-->|Poe API / Gemini 2.5| D[LLM Sentiment & Spam Analysis]:::llm
    end

    C -->|Batch Upload| E[(Google Sheets<br>Central Database)]:::sheet
    
    subgraph Analytics & Profiling
    F(risk_analysis.py<br>User Risk Profiling) <--> E
    G(dashboard.py<br>Metrics Aggregation) <--> E
    end

    subgraph Autonomous Alerting
    E --> H{Manus AI Agent<br>Email Automation}
    H -->|Date Validation & Filtering| I[Negative Sentiment Alerts]:::alert
    I -->|Gmail API| J(Customer Service & Executives)
    end

### 1. `main.py` (Data Pipeline & LLM Engine)
* **Data Ingestion:** Authenticates via a modularized Google Service Account to dynamically search and download daily raw chat logs (`.csv`/`.xlsx`) from Google Drive.
* **Filtering & Deduplication:** Reads dynamic configuration from a master Google Sheet, performing strict text deduplication and keyword matching based on time tolerances and user identity scores.
* **LLM Processing:** Sends filtered data to the LLM to classify user intent (Spam detection) and perform granular brand sentiment analysis.

### 2. `risk_analysis.py` (User Behavior & Risk Engine)
* **Behavioral Aggregation:** Backtracks 30 days of conversational data to construct behavioral profiles for active users (e.g., group join counts, brand mention frequency).
* **Rule-Based Scoring:** Applies a proprietary scoring algorithm to evaluate user risk and updates the "Sim Master" database, tagging users as `Real`, `Watch`, `Business`, or `IFT Seeder`.

### 3. `dashboard.py` (Dashboard Automation)
* **Data Synthesis:** Aggregates daily group activities, categorizes discussion topics, and calculates brand sentiment ratios.
* **Batch Updates:** Uses the `sheets_service.spreadsheets().batchUpdate()` API to efficiently overwrite specific dashboard cells, keeping management charts up-to-date without human intervention.

### 4. Email Automation & Crisis Alerting Engine (via Manus AI)
* **Autonomous Execution:** A fully automated CRON job triggers daily at 09:00 HKT using Manus AI to orchestrate data extraction from Google Sheets.
* **Smart Data Validation:** Incorporates a fail-safe pause mechanism; it cross-references the dashboard's latest recorded date with the current date, halting execution and notifying admins if the pipeline data is delayed.
* **Targeted Alerting:** Scans the daily data for negative brand sentiment ("N") specifically for core brands. It extracts crucial context (Group, Time, User Phone, Quoted Messages) and synthesizes an urgent alert section in the email payload for the Customer Service team.

## 🔒 Security & Reliability Note
* **Data Privacy:** For security and compliance reasons, all sensitive configurations (Google Service Account credentials, API keys, Folder IDs) are strictly managed via Environment Variables and GitHub Secrets. No real customer data is exposed in this public repository.
* **Fault Tolerance:** All Google API calls are wrapped in a custom `@with_retry` decorator implementing **Exponential Backoff**, ensuring the pipeline remains robust against API quota limits and `429 Too Many Requests` errors.

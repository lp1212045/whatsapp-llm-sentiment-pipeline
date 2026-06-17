> 🌍 **Language:** English | [繁體中文](README_zh-HK.md)

<br>

# 🚀 Automated Marketing Data Pipeline & LLM Sentiment Analysis

## 📌 Overview
This repository contains an automated data processing workflow designed to streamline marketing operations and customer sentiment analysis. By integrating Python, Large Language Models (Gemini via Poe API), and Google Workspace APIs, this pipeline transforms unstructured daily WhatsApp conversational data into structured, actionable business intelligence.

## 💼 Business Impact
* **Efficiency Leap:** Automated data cleaning and API requests reduce daily operational processing time from 2-3 hours to just **15 minutes** (over 80% time saved).
* **High-Volume Processing:** Capable of downloading, deduplicating, and extracting data from **~30,000** daily conversational interactions.
* **Proactive Crisis Management:** Leverages LLM to perform advanced sentiment analysis, categorizing feedback (Negative/Positive/Neutral) to instantly flag PR risks for immediate customer service intervention.

## 🛠️ Tech Stack
* **Language:** Python 3.x (pandas, regex)
* **AI & NLP:** Gemini-2.5-Flash (via Poe API), Prompt Engineering
* **Cloud & Integration:** Google Drive API (File fetching), Google Sheets API / gspread (Config reading & Data export)
* **Performance:** `concurrent.futures` (Multi-threading for accelerated API requests)
* **Automation:** GitHub Actions (CRON Jobs configured in `schedule.yml`)

## ⚙️ How It Works
1. **Data Ingestion:** Authenticates via Google Service Account to dynamically search and download daily raw chat logs (.csv/.xlsx) from Google Drive.
2. **Rule-Based Filtering:** Reads dynamic Keyword and Group configurations from a master Google Sheet, performing initial text deduplication and keyword matching.
3. **LLM Processing (Multi-threaded):** Sends filtered conversational data to the LLM to classify user intent (`isSpam`) and perform granular brand sentiment analysis.
4. **Automated Reporting:** Cleans and formats the final AI-processed data, appending it directly to a centralized Google Sheet for management dashboard visualization.

## 🔒 Security Note
*For security and compliance reasons, all sensitive configurations (Google Service Account credentials, API keys, Folder IDs, and Sheet URLs) are strictly managed via Environment Variables and GitHub Secrets. No real customer data or proprietary keys are exposed in this public repository.*

# 🚀 Automated Marketing Data Pipeline & LLM Analysis

## 📌 Overview
This repository contains an automated data processing workflow designed to streamline marketing operations and customer sentiment analysis. By integrating Python, Large Language Models (LLMs), and cloud database solutions, this pipeline eliminates manual data handling and provides real-time, actionable insights for commercial decision-making.

## 💼 Business Impact
* **Efficiency Leap:** Reduced daily operational processing time from 2-3 hours to just **15 minutes** (over 80% time saved).
* **High-Volume Processing:** Capable of handling and extracting structured data from **~30,000** daily conversational records (e.g., WhatsApp raw data).
* **Proactive Crisis Management:** Enables advanced sentiment analysis to instantly flag negative feedback and potential PR risks.

## 🛠️ Tech Stack
* **Language:** Python 3.x
* **AI & NLP:** LLMs (Prompt Engineering & Keyword Extraction)
* **Automation:** GitHub Actions (CRON Jobs configured in `schedule.yml`)
* **Database & BaaS:** Supabase / PostgreSQL (for structured data storage)

## ⚙️ How It Works
1. **Data Ingestion:** `main.py` fetches raw, unstructured conversational data.
2. **LLM Processing:** Feeds data into language models to perform sentiment analysis, keyword extraction, and data structuring.
3. **Automated Execution:** Powered by GitHub Actions (`schedule.yml`), the script runs autonomously on a pre-defined schedule without manual intervention.
4. **Reporting:** Outputs cleaned, structured data ready for monthly/quarterly business analytics dashboards.

## 🔒 Security Note
*For security and compliance reasons, all sensitive customer data, proprietary business logic, and API keys (OpenAI/Anthropic, Supabase, etc.) have been removed or masked in this public repository. This code serves as a structural demonstration of the automation pipeline.*

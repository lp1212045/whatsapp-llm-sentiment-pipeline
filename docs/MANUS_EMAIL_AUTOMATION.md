# Daily Dashboard Email — Workflow Documentation

> **Version:** 2026-07-17  
> **Maintainer:** Manus AI  
> **Purpose:** Automatically extracts daily IFT Cloud Dashboard data, filters negative sentiment alerts for core brands, and dispatches a summary email to designated stakeholders.

---

## 1. System Overview

This workflow is fully automated and executed by the **Manus AI Scheduling System**, triggering daily at 09:00 HKT without manual intervention. The entire pipeline consists of five steps:

`Read Dashboard` → `Date Validation` → `Read DailyData` → `Compose Email` → `Dispatch Email`

---

## 2. Schedule Configuration

| Item | Details |
|---|---|
| **Schedule Name** | IFT Cloud Daily Dashboard Email - 09:00 HKT |
| **Execution Time** | Daily at 09:00 (Asia/Hong_Kong) |
| **Cron Expression** | `0 0 9 * * *` (Sec Min Hour Day Month Week) |
| **Execution Mode** | `full_auto` (Fully automated, no confirmation required) |
| **Status** | `active` |
| **Connector** | Gmail + Google Workspace |
| **Task ID** | `YOUR_MANUS_TASK_ID` |

---

## 3. Data Sources

### 3.1 IFT Cloud - Daily Dashboard

| Item | Details |
|---|---|
| **Spreadsheet ID** | `YOUR_DASHBOARD_SPREADSHEET_ID` |
| **Sheet Naming Convention** | YYMM (e.g., `2607` for July 2026) |
| **Read Range** | `A1:AF100` |

### 3.2 DailyData

| Item | Details |
|---|---|
| **Google Drive Folder ID** | `YOUR_DRIVE_FOLDER_ID` |
| **Naming Convention** | `yymm_DailyData_Part1` / `yymm_DailyData_Part2` |
| **Part1 Applicable Dates** | 1st — 15th of the month |
| **Part2 Applicable Dates** | 16th — 31st of the month |
| **Part1 Spreadsheet ID** | `YOUR_PART1_SPREADSHEET_ID` |
| **Part2 Spreadsheet ID** | `YOUR_PART2_SPREADSHEET_ID` |

> **Note:** DailyData updates dynamically. The system fetches the latest version directly from Google Drive upon every execution.

---

## 4. Execution Flow Details

### Step 1: Read Dashboard
Uses the `gws` CLI to read the current month's Dashboard Sheet (e.g., `2607!A1:AF100`), extracts the Total Reach row (Row 2), and auto-detects the last non-empty, non-zero column to determine the target date.

### Step 2: Date Validation (Fail-Safe Pause Mechanism)
**Core Logic:** Compares the detected target date with **yesterday (HKT)**.
- **Match (Target Date = Yesterday):** Proceeds to the next step.
- **Mismatch (Target Date ≠ Yesterday):** **Immediately halts execution, aborts email dispatch**, and notifies the admin: *"Dashboard data has not been updated to yesterday. Email dispatch paused. Please verify before manual trigger."*

### Step 3: Read DailyData
Determines whether to fetch Part1 or Part2 based on the target date. Searches the Google Drive folder for the corresponding file (e.g., `2607_DailyData_Part2`), reads all data, and filters rows where any core brand column contains an `N` (Negative Sentiment) on the target date.
*Extracted fields for alerts:* `Group`, `Time`, `userPhone`, `quotedMessage`, `messageBody`.

### Step 4: Compose Email
The email format includes the following sections:
1. Key Metrics (Total Reach, Total Reach Unique)
2. Group Classification Breakdown (Total Group and sub-categories)
3. Brand Mention / Sentiment (P/I/N metrics)
4. Competitor Brand Data
5. 🚨 Urgent: Brand related with Warning (Negative sentiment alerts with User Phone)
6. Data Source Links

*If no negative sentiment is detected, Section 5 displays:* `No negative sentiment alerts for this date.`

### Step 5: Dispatch Email

| Item | Details |
|---|---|
| **Subject Format** | `IFT Cloud - Daily Dashboard #WOM #MI #CoreBrand - {target_date}` |
| **To** | `manager@yourcompany.com` |
| **CC** | `team1@yourcompany.com`, `team2@yourcompany.com` |
| **Method** | Direct dispatch (Bypasses drafts) |
| **Sender Account** | `system-alert@yourcompany.com` |

---

## 5. Schedule Trigger Prompt (Manus AI Prompt)

The following instruction set is stored within the Manus AI scheduling system to orchestrate the workflow:

```text
Execute the daily Dashboard email dispatch workflow based on the documentation:

1) Read the latest Dashboard data (A1:AF100) from Google Sheets (Spreadsheet ID: YOUR_DASHBOARD_SPREADSHEET_ID, Sheet format: YYMM). Auto-detect the target date by finding the last non-empty, non-zero column in the Total Reach row.

2) [CRITICAL] If the detected target date is NOT yesterday (HKT), the dashboard is outdated. You MUST halt the workflow immediately, do not send any emails, and notify the user: "Dashboard data has not been updated to yesterday. Email dispatch paused. Please verify before manual trigger."

3) If the target date is yesterday, determine whether to use Part1 (1st-15th) or Part2 (16th-31st) DailyData. Fetch the correct file from Google Drive (Folder ID: YOUR_DRIVE_FOLDER_ID) matching the YYMM_DailyData_Part1/2 format. Always fetch the latest version dynamically.

4) Filter rows matching the target date where any core brand column (Brand_A/Brand_B/etc.) contains 'N'. Extract Group, Time, userPhone, quotedMessage, and messageBody.

5) Compose the email following the standard template: Key Metrics, Group Classification Breakdown, Sentiment Breakdown, Urgent Alerts (including userPhone, or "No negative sentiment alerts for this date."), and data source links.

6) Dispatch directly via Gmail connector without saving to drafts. 
   Subject: IFT Cloud - Daily Dashboard #WOM #MI #CoreBrand - {target_date}
   To: manager@yourcompany.com
   CC: team_members@yourcompany.com

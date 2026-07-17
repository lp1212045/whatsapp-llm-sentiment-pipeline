import pandas as pd
import json
import re
import unicodedata
import argparse
import os
from datetime import datetime, timedelta
import pytz

# Import shared modules and configurations
from google_auth import get_google_clients, with_retry
from config import BRAND_MAPPING, FRISO_SUB_BRANDS, FRISO_MAIN

# ==========================================
# ⚙️ Manual Testing Block
# Format: ["yymmdd"], e.g., ["260705"]
# If [] is empty, it automatically fetches yesterday's data
MANUAL_TARGET_DATES = [] 
# ==========================================

# --- Helper Functions ---
def normalize_text(text):
    if not text: return ""
    text = str(text)
    text = unicodedata.normalize("NFKC", text)
    emoji_nums = {"0️⃣":"0", "1️⃣":"1", "2️⃣":"2", "3️⃣":"3", "4️⃣":"4", "5️⃣":"5", "6️⃣":"6", "7️⃣":"7", "8️⃣":"8", "9️⃣":"9"}
    for e, n in emoji_nums.items():
        text = text.replace(e, n)
    return text.lower()

def categorize_group(group_name, messages):
    name = normalize_text(group_name)
    if any(k in name for k in ["幼稚園", "n班", "k1", "k2", "k3", "pn", "小學", "升小", "升幼", "playgroup", "pg", "教材", "面試", "備戰", "早教", "學校", "書院", "幼兒園", "講座", "精讀班", "校網", "教育"]):
        return "Education"
    if any(k in name for k in ["醫院", "產檢", "分娩", "瑪麗", "聯合", "qe", "廣華", "威爾斯", "瑪嘉烈", "屯門醫院", "伊利沙伯", "威爾斯", "仁安", "港怡", "聖德肋撒", "聖保祿", "養和", "中大醫院", "明德", "港安", "嘉諾撒", "浸會", "法國醫院", "東區醫院"]):
        return "Hospitals"
    if any(k in name for k in ["奶粉", "母乳", "轉奶", "加固", "人奶", "餵養", "米糊", "奶粉", "加固", "人奶", "餵養", "米糊", "奶糊", "blw", "tw", "濕疹", "敏感", "g6pd", "蠶豆症", "疫苗", "中醫", "藥膳", "月子餐", "扎肚", "睡眠", "健康", "育兒", "痛症", "護膚", "養生", "情緒", "adhd", "sen"]):
        return "IFT topics"
    if any(k in name for k in ["團購", "購物", "拼媽媽", "二手", "買賣", "著數", "bb展", "優惠", "物資", "交換", "免廢", "vip", "百貨", "用品", "筍貨", "禮品", "荷花"]):
        return "Shopping"
    if any(k in name for k in ["港島", "九龍", "新界", "屯門", "元朗", "天水圍", "屯元天", "大埔", "沙田", "馬鞍山", "北區", "粉嶺", "上水", "將軍澳", "tko", "西貢", "觀塘", "藍田", "油塘", "黃大仙", "九龍城", "啟德", "深水埗", "長沙灣", "順利", "葵涌", "荔枝角", "美孚", "油尖旺", "大角咀", "南昌", "荃灣", "葵青", "東涌", "大嶼山", "中環", "灣仔", "銅鑼灣", "太古", "鰂魚涌", "柴灣", "筲紀灣", "南區", "香港仔", "街坊", "火炭", "大圍", "青衣", "何文田", "黃埔", "西營盤", "堅尼地城", "奧運", "土瓜灣", "北角", "太子", "旺角", "尖沙咀", "離島"]):
        return "Location"
    if re.search(r"(20\d{2}年|2[3-7]年|\d{1,2}月|\d{1,2}日|總社群|同日|預產期|生日|龍b|蛇b|兔b|牛b|虎b|馬b|羊b|猴b|雞b|狗b|豬b|鼠b)", name) or any(k in name for k in ["同日", "總社群", "預產期", "生日", "寶寶", "bb group", "媽媽group", "媽媽谷", "交流群"]):
        return "Stages"
    if not group_name or str(group_name).strip() == "":
        return "Null group name"
    return "Others"

def is_only_media(messages):
    has_content = False
    for msg in messages:
        msg_text = str(msg).strip().lower()
        if not msg_text: continue
        has_content = True
        if msg_text not in ["image", "video", "sticker", "audio"] and not re.match(r"^<.*>$", msg_text):
            return False
    return has_content

# ==========================================
# 🛡️ Encapsulate Google Sheets API (with anti-crash mechanism)
# ==========================================
@with_retry()
def get_column_mapping(sheets_service, spreadsheet_id, sheet_name, dates):
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=f"{sheet_name}!A1:AF1"
    ).execute()
    
    if not result or "values" not in result: return {}
    headers = result["values"][0]
    mapping = {}
    for i, h in enumerate(headers):
        h_strip = h.strip()
        if h_strip in dates:
            col_letter = ""
            n = i
            while n >= 0:
                col_letter = chr(65 + (n % 26)) + col_letter
                n = (n // 26) - 1
            mapping[h_strip] = (col_letter, i)
    return mapping

@with_retry()
def get_dashboard_info(sheets_service, dashboard_id):
    return sheets_service.spreadsheets().get(spreadsheetId=dashboard_id).execute()

@with_retry()
def fetch_raw_data(sheets_service, source_id, range_name="Sheet1!A:AD"):
    return sheets_service.spreadsheets().values().get(
        spreadsheetId=source_id, range=range_name
    ).execute()

@with_retry()
def append_group_records(sheets_service, dashboard_id, target_sheet, records):
    return sheets_service.spreadsheets().values().append(
        spreadsheetId=dashboard_id, range=f"{target_sheet}!A1",
        valueInputOption="USER_ENTERED", body={"values": records}
    ).execute()

@with_retry()
def batch_update_dashboard(sheets_service, dashboard_id, requests):
    return sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=dashboard_id, body={"requests": requests}
    ).execute()

# ==========================================
# 🚀 Main Execution Flow
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="Dashboard Updater")
    parser.add_argument("--dashboard_id", required=True)
    args = parser.parse_args()
    
    hk_tz = pytz.timezone('Asia/Hong_Kong')
    
    # 1. Determine dates to process
    if MANUAL_TARGET_DATES:
        target_dates_yymmdd = MANUAL_TARGET_DATES
        print(f"Using manually specified dates: {target_dates_yymmdd}")
    else:
        yesterday_yymmdd = (datetime.now(hk_tz) - timedelta(days=1)).strftime("%y%m%d")
        target_dates_yymmdd = [yesterday_yymmdd]
        print(f"No date specified, automatically processing yesterday's data: {target_dates_yymmdd}")
        
    # Get Google API authorization
    gc, drive_service, sheets_service = get_google_clients()
    
    # Get all Sheet info from Dashboard to dynamically retrieve gid (sheetId)
    print("🌐 Fetching Dashboard sheet information...")
    dashboard_info = get_dashboard_info(sheets_service, args.dashboard_id)
    dashboard_sheets = {sheet['properties']['title']: sheet['properties']['sheetId'] for sheet in dashboard_info.get('sheets', [])}
    
    # 2. Automatically find corresponding monthly files for each date
    for date_yymmdd in target_dates_yymmdd:
        date_obj = datetime.strptime(date_yymmdd, "%y%m%d")
        date_str = date_obj.strftime("%Y-%m-%d") # YYYY-MM-DD
        
        # Dynamically calculate target tab name (e.g., 2607 and 2607Group)
        yy = date_obj.strftime("%y")
        mm = date_obj.strftime("%m")
        target_dash_sheet = f"{yy}{mm}"
        target_group_sheet = f"{yy}{mm}Group"
        
        # Check if monthly tab exists in Dashboard
        if target_dash_sheet not in dashboard_sheets:
            print(f"❌ Cannot find tab '{target_dash_sheet}' in Dashboard. Please create the monthly tab first!")
            continue
            
        dash_sheet_id = dashboard_sheets[target_dash_sheet]
        
        # Calculate corresponding DailyData source filename (e.g., 2607_DailyData_Part1)
        dd = date_obj.day
        part = "Part1" if dd <= 15 else "Part2"
        source_sheet_name = f"{yy}{mm}_DailyData_{part}"
        
        try:
            print(f"🔍 Searching for source file: {source_sheet_name} ...")
            sh = gc.open(source_sheet_name)
            source_id = sh.id
        except Exception as e:
            print(f"❌ Cannot find source file {source_sheet_name}, skipping this date. Error: {e}")
            continue
            
        print(f"📥 Fetching data from {source_sheet_name} (ID: {source_id})...")
        try:
            raw_source = fetch_raw_data(sheets_service, source_id)
        except Exception as e:
            print(f"❌ Data fetch failed: {e}")
            continue
        
        if not raw_source or "values" not in raw_source: 
            print("⚠️ Source is empty.")
            continue
            
        source_header = raw_source["values"][0]
        df = pd.DataFrame([r + [""] * (len(source_header) - len(r)) for r in raw_source["values"][1:]], columns=source_header)
        
        # Filter data for the current day
        day_df = df[df["Date"].str.strip() == date_str]
        if day_df.empty: 
            print(f"⚠️ No data for {date_str} in {source_sheet_name}.")
            continue
            
        # --- Start Statistics ---
        groups = day_df.groupby("GroupID")
        new_group_records = []
        for gid, gdata in groups:
            gname = gdata["Group"].iloc[0]
            category = categorize_group(gname, gdata["messageBody"].tolist())
            media_tag = "Only image/video" if is_only_media(gdata["messageBody"].tolist()) else ""
            new_group_records.append([gid, gname, category, date_str, media_tag])
            
        friso_stats = {brand: {"P": 0, "I": 0, "N": 0} for brand in FRISO_SUB_BRANDS + ["Friso (unique)"]}
        for _, row in day_df.iterrows():
            sub_brand_found = False
            for sb in FRISO_SUB_BRANDS:
                sentiment = str(row.get(sb, "")).upper().strip()
                if sentiment in ["P", "I", "N"]:
                    friso_stats[sb][sentiment] += 1
                    sub_brand_found = True
            if not sub_brand_found:
                main_sentiment = str(row.get(FRISO_MAIN, "")).upper().strip()
                if main_sentiment in ["P", "I", "N"]:
                    friso_stats["Friso (unique)"][main_sentiment] += 1
                    
        other_brand_stats = {brand: 0 for brand in BRAND_MAPPING.keys()}
        for brand, cols in BRAND_MAPPING.items():
            for col in cols:
                other_brand_stats[brand] += day_df[day_df[col].astype(str).str.upper().str.strip().isin(["P", "I", "N"])].shape[0]
                
        # --- Write to Group Sheet (Dynamically appending to corresponding month's Group tab) ---
        if new_group_records:
            print(f"📝 Appending {len(new_group_records)} records to {target_group_sheet} sheet...")
            try:
                append_group_records(sheets_service, args.dashboard_id, target_group_sheet, new_group_records)
            except Exception as e:
                print(f"❌ Failed to write Group records: {e}")
                
        # --- Prepare to Update Dashboard Cells ---
        col_mapping = get_column_mapping(sheets_service, args.dashboard_id, target_dash_sheet, [date_str])
        
        if date_str in col_mapping:
            col_letter, col_idx = col_mapping[date_str]
            final_requests = []
            
            data_points = [
                (2, len(day_df)), (3, day_df["userPhone"].nunique())
            ]
            row_map = {"Friso (unique)": 17, "美素金裝": 21, "美素皇家": 25, "美素有機": 29, "美素Kids": 33, "美素Signature": 37}
            for brand, start_row in row_map.items():
                stats = friso_stats[brand]
                data_points.append((start_row + 1, stats["P"]))
                data_points.append((start_row + 2, stats["I"]))
                data_points.append((start_row + 3, stats["N"]))
            for i, brand in enumerate(["Abbott", "Apta", "Cow & Gate", "HiPP", "Mead Johnson", "Nestle", "Wyeth / illuma"]):
                data_points.append((43 + i, other_brand_stats[brand]))
                
            for row_num, val in data_points:
                val_type = "numberValue" if isinstance(val, (int, float)) else "stringValue"
                final_requests.append({"updateCells": {"rows": [{"values": [{"userEnteredValue": {val_type: val}}]}], "fields": f"userEnteredValue.{val_type}", "range": {"sheetId": dash_sheet_id, "startRowIndex": row_num-1, "endRowIndex": row_num, "startColumnIndex": col_idx, "endColumnIndex": col_idx+1}}})
                
            if final_requests:
                print(f"📊 Executing Dashboard batch update for {target_dash_sheet}...")
                try:
                    batch_update_dashboard(sheets_service, args.dashboard_id, final_requests)
                except Exception as e:
                    print(f"❌ Dashboard update failed: {e}")
                    
    print("✅ All processes completed.")

if __name__ == "__main__":
    main()

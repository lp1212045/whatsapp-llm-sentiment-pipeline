import os
import sys
import re
import json
import time
import concurrent.futures
import pandas as pd
from datetime import datetime, timedelta
import pytz
import io

# Google related packages (Modularized)
from googleapiclient.http import MediaIoBaseDownload
from google_auth import get_google_clients
import gspread # Required to catch 'SpreadsheetNotFound' exception
import openai # For Poe API

# ==========================================
# 🔐 0. Authorize Google API (Sheets & Drive)
# ==========================================
print("🔐 Authorizing Google API using modular service account...")
try:
    gc, drive_service, _ = get_google_clients()
    print("✅ Service account authorized successfully!\n")
except Exception as e:
    print(f"❌ Authorization failed. Please check if service_account.json exists. Error: {e}")
    sys.exit()

# ==========================================
# ⚙️ 1. Parameters & Configuration
# ==========================================
N8N_RAW_FOLDER_ID = "YOUR_N8N_RAW_FOLDER_ID" # Sanitized for portfolio
KEYWORDS_SHEET_URL = "YOUR_KEYWORDS_SHEET_URL" # Sanitized for portfolio
GROUPINFO_SHEET_URL = "YOUR_GROUPINFO_SHEET_URL" # Sanitized for portfolio
MASTER_WORKSHEET_NAME = "Sheet1" 

# Array for testing multiple dates. Format: ["yymmdd"], e.g., ["260625"] or ["260625","260626"]. 
# If left empty [], it will automatically fetch yesterday's data.
MANUAL_TARGET_DATES = [] 

POE_API_KEY = os.environ.get("POE_API_KEY", "YOUR_LOCAL_API_KEY_HERE")
POE_MODEL = "gemini-2.5-flash" 

poe_client = openai.OpenAI(
    api_key=POE_API_KEY,
    base_url="https://api.poe.com/v1",
)

# Dummy phone numbers for portfolio demonstration
SEEDER_PHONES = {
    "12345678", "87654321", "98765432" 
}

STANDARD_BRANDS = [
    "雅培心美力", "Apta Platinum", "Apta Essensis", "Apta Neo", "牛欄牌", 
    "美素", "美素金裝", "美素皇家", "美素有機", "美素Kids", "美素Signature", 
    "Hipp", "Illuma", "Illuma 有機", "美贊臣 A+", "美贊臣 Enfinitas", 
    "雀巢能恩", "雀巢全護"
]

FINAL_HEADERS = [
    "Group", "GroupID", "Date", "Time", "userPhone", "Internal", 
    "quotedMessage", "messageBody", "brand", "keywords", "warning", "reply"
] + STANDARD_BRANDS + ["Source"]

stats = {
    "csv_files": 0,
    "total_raw_rows": 0,
    "total_deduped_rows": 0,
    "need_ai_processing": 0,
    "ai_actually_processed": 0,
    "spam_detected": 0
}

def print_stage_dashboard(stage_name, metrics):
    print("\n" + "="*50)
    print(f"📊 {stage_name} - Statistics Dashboard")
    print("="*50)
    for key, value in metrics.items():
        print(f"{key:<22} : {value}")
    print("="*50 + "\n")

# ==========================================
# 🌟 Brand Mapping Function
# ==========================================
def get_standard_brand(brand_code, product_code):
    b = str(brand_code).strip().lower()
    p = str(product_code).strip().lower()
    
    if b == 'abbott': return "雅培心美力"
    if b == 'aptamil':
        if p == 'essensis': return "Apta Essensis"
        if p == 'neo': return "Apta Neo"
        return "Apta Platinum"
    if b == 'cowgate': return "牛欄牌"
    if b == 'friso':
        if p == 'prestige': return "美素皇家"
        if p == 'kids': return "美素Kids"
        if p == 'gold': return "美素金裝"
        if p == 'bio': return "美素有機"
        if p == 'signature': return "美素Signature"
        return "美素"
    if b == 'hipp': return "Hipp"
    if b == 'illuma':
        if p == 'organic': return "Illuma 有機"
        return "Illuma"
    if b == 'mjn':
        if p == 'enfinitas': return "美贊臣 Enfinitas"
        return "美贊臣 A+"
    if b == 'nestle':
        if p == 'illuma': return "雀巢全護"
        return "雀巢能恩"
    return b

# ==========================================
# 🤖 2. AI Sentiment & Spam Analysis Function
# ==========================================
def call_llm_analysis(body_text, quoted_text="", hit_kws_list=[], hit_brands_list=[], max_retries=3):
    marked_body = body_text
    marked_quoted = quoted_text
    
    sorted_kws = sorted(hit_kws_list, key=len, reverse=True)
    for kw in sorted_kws:
        if kw:
            pattern = re.compile(rf"(?<!【){re.escape(kw)}(?!】)", re.IGNORECASE)
            marked_body = pattern.sub(f"【{kw}】", marked_body)
            if marked_quoted:
                marked_quoted = pattern.sub(f"【{kw}】", marked_quoted)
                
    json_template = {
        "reasoning": "Processing...",
        "isSpam": False,
        "brand_analysis": {b: "N/P/I" for b in hit_brands_list} if hit_brands_list else {}
    }
    json_template_str = json.dumps(json_template, ensure_ascii=False, indent=2)
    
    # NOTE: The prompt is kept in Traditional Chinese to effectively process Cantonese social media text.
    prompt = f"""# Role
    你是一位具備 15 年育兒經驗的香港母親，同時擔任頂級母嬰品牌公關與客服風控專家。你精通香港/廣東話的母嬰社群俚語。
    
    # Task
    解構輸入的社群留言（引言+回覆），執行「無效數據過濾 (isSpam)」與「品牌立場分析 (brand_analysis)」，最後嚴格輸出純 JSON 格式。
    
    # ⚠️ 核心防呆限制 (極度重要)
    1. 你只能分析被【 】包覆的詞彙所代表的品牌。如果句子裡有某些詞彙（例如「有機」）但沒有被【 】包覆，請視為一般形容詞，絕對不可將其判定為任何品牌。
    2. 系統已初步篩選出本次命中的標準品牌名單：{hit_brands_list}。
    3. 你的 `brand_analysis` 只能包含上述名單內的品牌，絕對不可自行發明、猜測或輸出其他品牌名稱（例如不可輸出 "Signature"，只能輸出 "美素Signature"）。
    
    # Negative Constraints & Rules
    1. 意圖解構 (isSpam): 純交易/抽獎/無關閒聊為 true。有評價、轉奶原因、詢問為 false。
    2. 情緒分析 (brand_analysis) 判定標準：
       - "N" (負面/需客服緊急介入): 必須是「直接針對該品牌產品本身」的嚴重缺點、健康安全問題或重大公關危機。例如：食用後出現不良生理反應（便秘、屎硬、起紅點、敏感、不吸收、熱氣等）、或對品牌有極度嚴重的指控（如：好多打手、品質極差、食壞BB）。
       - "P" (正面): 滿意、推介、穩定飲用 (如「無事」、「安心」)。
       - "I" (中立/一般吐槽): 純詢價、客觀陳述、或對非產品核心問題的輕微抱怨。
         👉 注意：單純的口味描述（如「我覺得甜」）、對營銷活動/會員要求/贈品/價格的吐槽（如「要求有啲矛盾」、「好貴」、「要入會好麻煩😅」）、帶有無奈表情符號的微言，或是負面詞彙並非針對該品牌產品本身（如「BB病左所以換奶粉」），皆屬於中立 "I"，絕對不可判為 "N"。
    
    # Output Format
    強制輸出純 JSON 字串，以 `{{` 開頭，`}}` 結尾。格式必須完全符合以下結構：
    {json_template_str}
    
    # Input
    引言內容: {marked_quoted}
    回覆內容: {marked_body}
    """
    
    attempt = 0
    success = False
    
    while attempt < max_retries and not success:
        try:
            response = poe_client.responses.create(
                model=POE_MODEL,
                input=prompt
            )
            res_text = response.output_text.strip()
            
            if res_text.startswith("```"):
                res_text = re.sub(r"^```[a-zA-Z]*\n", "", res_text)
                res_text = re.sub(r"\n```$", "", res_text)
                
            result = json.loads(res_text.strip())
            return True, result.get("isSpam", False), result.get("brand_analysis", {})
            
        except Exception as e:
            attempt += 1
            if attempt < max_retries:
                time.sleep(2) 
            else:
                return False, False, {}

# ==========================================
# 📂 3. Download Target Date Files via Google Drive API
# ==========================================
hk_tz = pytz.timezone('Asia/Hong_Kong')
if MANUAL_TARGET_DATES:
    target_dates = MANUAL_TARGET_DATES
else:
    target_dates = [(datetime.now(hk_tz) - timedelta(days=1)).strftime("%y%m%d")]

print(f"📅 Target dates to process: {target_dates}")
LOCAL_RAW_DIR = "./temp_raw_data"
os.makedirs(LOCAL_RAW_DIR, exist_ok=True)
daily_file_paths = []

print("🔄 Searching and downloading files via Google Drive API...")
try:
    for date_str in target_dates:
        print(f"\n🔍 Searching for folder with date [{date_str}]...")
        
        date_dir = os.path.join(LOCAL_RAW_DIR, date_str)
        os.makedirs(date_dir, exist_ok=True)
        
        query = f"'{N8N_RAW_FOLDER_ID}' in parents and name contains '{date_str}000000' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        folders = results.get('files', [])
        
        if not folders:
            continue
            
        for folder in folders:
            print(f"📂 Folder found: {folder['name']}")
            
            folder_name = folder['name']
            source_device = "unknown"
            match = re.search(r'-([a-zA-Z0-9]+)-db$', folder_name)
            if match:
                source_device = match.group(1)
            
            file_query = f"'{folder['id']}' in parents and trashed = false"
            files = []
            page_token = None
            
            while True:
                file_results = drive_service.files().list(
                    q=file_query, 
                    pageSize=1000, 
                    pageToken=page_token,
                    fields="nextPageToken, files(id, name)"
                ).execute()
                
                files.extend(file_results.get('files', []))
                page_token = file_results.get('nextPageToken', None)
                if page_token is None: break
            
            valid_files = [f for f in files if f['name'].endswith(('.xlsx', '.csv')) and not f['name'].startswith('~$')]
            total_files = len(valid_files)
            download_count = 0
            
            for file in valid_files:
                request = drive_service.files().get_media(fileId=file['id'])
                local_path = os.path.join(date_dir, file['name'])
                
                fh = io.FileIO(local_path, 'wb')
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                
                daily_file_paths.append((local_path, source_device))
                download_count += 1
                print(f"\r   ⏳ [{date_str}] File download progress: {download_count} / {total_files}", end='', flush=True)
            print()
except Exception as e:
    print(f"❌ File download failed: {e}")
    sys.exit()

stats["csv_files"] = len(daily_file_paths)

# ---------------------------------------------------------
# Read Google Sheets Configuration
# ---------------------------------------------------------
print("\n🌐 Reading configuration from Google Sheets (Keywords & GroupInfo)...")
max_retries = 3
success = False
for attempt in range(max_retries):
    try:
        kw_sheet = gc.open_by_url(KEYWORDS_SHEET_URL).sheet1
        keywords_df = pd.DataFrame(kw_sheet.get_all_records())
        
        gi_sheet = gc.open_by_url(GROUPINFO_SHEET_URL).worksheet('groups')
        groupinfo_df = pd.DataFrame(gi_sheet.get_all_records())
        groupinfo_df = groupinfo_df[['gus_id', 'subject']]
        
        print("✅ Configuration loaded successfully!")
        success = True
        break
        
    except Exception as e:
        print(f"⚠️ Attempt {attempt + 1} to load config failed: {e}")
        if attempt < max_retries - 1:
            time.sleep(5)
        else:
            print("❌ Max retries reached. Please try again later.")
            sys.exit()

group_map = {}
id_col = 'gus_id'
name_col = 'subject'
for _, row in groupinfo_df.iterrows():
    gid = str(row.get(id_col, '')).strip()
    if gid.endswith('.0'): gid = gid[:-2]
    gname = str(row.get(name_col, '')).strip()
    if gid and gid.lower() not in ['nan', 'none']:
        group_map[gid] = gname

brand_keywords = {}
exclude_keywords = []
all_brand_related_kws = set()

for _, row in keywords_df.iterrows():
    k_type = str(row.get('type', '')).strip()
    brand_name = str(row.get('brand', '')).strip()
    kw = str(row.get('keyword', '')).strip()
    product = str(row.get('product', '')).strip()
    req_prod = str(row.get('required_product', '')).strip()
    
    if not kw: continue
    if k_type.lower() == 'exclude':
        exclude_keywords.append(kw)
    else:
        if brand_name not in brand_keywords:
            brand_keywords[brand_name] = []
        
        brand_keywords[brand_name].append({
            "kw": kw,
            "product": product,
            "req_prod": req_prod
        })
        
        if brand_name and brand_name.lower() not in ["1", "nan", "none"]:
            all_brand_related_kws.add(kw)

print_stage_dashboard("Environment & Config Parsing", {
    "📁 Target files downloaded": f"{stats['csv_files']}",
    "🏷️ Brand keywords loaded": f"{sum(len(v) for v in brand_keywords.values())}",
    "👥 Group info loaded": f"{len(group_map)}"
})

# ==========================================
# ⚡ 4. Stage 1: Rule Matching & Tagging
# ==========================================
def get_phone_score(phone):
    phone = str(phone).strip()
    if phone.startswith("852") and "@" not in phone: return 3  
    elif "@" not in phone and re.match(r'^\d+$', phone): return 2  
    else: return 1  

records_dict = {} 
last_seen_tracker = {} 
TIME_TOLERANCE_SECONDS = 60 

print("⚡ Starting Stage 1: Rule matching and tagging...")
for file_path, source_device in daily_file_paths:
    file_name = os.path.basename(file_path)
    group_id = str(os.path.splitext(file_name)[0]).strip() 
    if group_id.endswith('.0'): group_id = group_id[:-2]
    group_name = group_map.get(group_id, "")
    
    try:
        day_df = pd.read_excel(file_path) if file_path.endswith('.xlsx') else pd.read_csv(file_path)
        day_df.columns = day_df.columns.str.strip()
        
        for col in ['Date2', 'Time', 'userPhone', 'messageBody', 'quotedMessage', 'mediaCaption', 'mediaType']:
            if col not in day_df.columns: day_df[col] = ""
            
        for _, row in day_df.iterrows():
            stats["total_raw_rows"] += 1
            
            body = str(row['messageBody']).strip()
            if body.lower() in ["nan", "null", "none"]: body = ""
            
            media_caption = str(row['mediaCaption']).strip()
            if media_caption.lower() in ["nan", "null", "none"]: media_caption = ""
            
            media_type = str(row['mediaType']).strip()
            if media_type.lower() in ["nan", "null", "none"]: media_type = ""
            
            if not body or body.lower() == "image":
                if media_caption:
                    body = media_caption
                elif media_type.lower() == 'image' or body.lower() == "image":
                    body = "image"
                else:
                    body = "[empty]"
                    
            quoted_raw = row.get('quotedMessage')
            quoted = "" if pd.isna(quoted_raw) or str(quoted_raw).strip().lower() in ["nan", "null", "none"] else str(quoted_raw).strip()
            date_val = str(row['Date2']).strip()
            time_val = str(row['Time']).strip()
            phone_raw = str(row['userPhone']).strip()
            
            phone_for_check = re.sub(r'\D', '', phone_raw)
            if phone_for_check.startswith("852"): phone_for_check = phone_for_check[3:]
            internal_flag = "✓" if phone_for_check in SEEDER_PHONES else ""
            
            body_lower = body.lower()
            contains_exclude = any(ex_kw.lower() in body_lower for ex_kw in exclude_keywords)
            hit_brands = []
            hit_keywords = []
            brand_marks = {b: "" for b in STANDARD_BRANDS}
            has_brand_keyword = False
            
            if not contains_exclude and body != "[empty]" and body != "image":
                for brand, kw_dicts in brand_keywords.items():
                    raw_hits = []
                    for kd in kw_dicts:
                        if kd["kw"].lower() in body_lower:
                            raw_hits.append(kd)
                    
                    valid_hits = []
                    for kd in raw_hits:
                        req = kd["req_prod"]
                        if req:
                            if any(other["product"] == req for other in raw_hits):
                                valid_hits.append(kd)
                        else:
                            valid_hits.append(kd)
                            
                    if valid_hits:
                        for kd in valid_hits:
                            std_brand = get_standard_brand(brand, kd["product"])
                            if std_brand not in hit_brands:
                                hit_brands.append(std_brand)
                                
                            if kd["kw"] not in hit_keywords:
                                hit_keywords.append(kd["kw"])
                            if kd["kw"] in all_brand_related_kws:
                                has_brand_keyword = True
                                
            cleaned_body = re.sub(r'\s+', '', body)
            brand_status = ""
            if hit_brands and has_brand_keyword:
                brand_status = "1"
                for b in hit_brands:
                    if b in STANDARD_BRANDS: brand_marks[b] = "✓"
                    
            record = {
                "Group": group_name, "GroupID": group_id, "Date": date_val, "Time": time_val,
                "userPhone": phone_raw, "Internal": internal_flag, "quotedMessage": quoted,
                "messageBody": body, "brand": brand_status, "keywords": ", ".join(hit_keywords),
                "warning": "", "reply": "", **brand_marks, 
                "Source": source_device
            }
            
            base_fingerprint = f"{group_id}_{date_val}_{cleaned_body}"
            current_time_obj = pd.to_datetime(f"{date_val} {time_val}", errors='coerce', dayfirst=True)
            current_phone_score = get_phone_score(phone_raw)
            
            if base_fingerprint not in last_seen_tracker:
                last_seen_tracker[base_fingerprint] = []
                
            is_merged = False
            
            for old_info in last_seen_tracker[base_fingerprint]:
                old_time_obj = old_info["time_obj"]
                old_key = old_info["key"]
                
                if pd.notna(current_time_obj) and pd.notna(old_time_obj):
                    time_diff = abs((current_time_obj - old_time_obj).total_seconds())
                else:
                    time_diff = 0
                    
                if time_diff <= TIME_TOLERANCE_SECONDS:
                    should_merge = True
                    old_phone = str(records_dict[old_key]["userPhone"]).strip()
                    old_phone_score = get_phone_score(old_phone)
                    
                    if old_phone_score >= 2 and current_phone_score >= 2:
                        old_digits = re.sub(r'\D', '', old_phone)
                        curr_digits = re.sub(r'\D', '', phone_raw)
                        if old_digits and curr_digits and (old_digits not in curr_digits and curr_digits not in old_digits):
                            should_merge = False
                    
                    if should_merge:
                        if current_phone_score > old_phone_score:
                            records_dict[old_key]["userPhone"] = phone_raw
                            records_dict[old_key]["Internal"] = internal_flag
                        
                        existing_sources = [s.strip() for s in records_dict[old_key]["Source"].split(",")]
                        if source_device not in existing_sources:
                            existing_sources.append(source_device)
                            records_dict[old_key]["Source"] = ", ".join(existing_sources)
                        is_merged = True
                        break
                        
            if not is_merged:
                unique_key = f"{base_fingerprint}_{time_val}_{len(records_dict)}"
                records_dict[unique_key] = record
                
                last_seen_tracker[base_fingerprint].append({
                    "time_obj": current_time_obj,
                    "key": unique_key
                })
    except Exception as e:
        print(f"❌ Failed to read file {file_name}: {e}")

all_records = list(records_dict.values())
stats["total_deduped_rows"] = len(all_records)
stats["need_ai_processing"] = sum(1 for r in all_records if r["brand"] == "1")

print_stage_dashboard("Stage 1: Rule Matching & Tagging", {
    "💬 Total raw rows": f"{stats['total_raw_rows']}",
    "📝 Rows after deduplication": f"{stats['total_deduped_rows']}",
    "🎯 Rows requiring AI processing": f"{stats['need_ai_processing']}"
})

# ==========================================
# 🤖 5. Stage 2: Precision AI Analysis
# ==========================================
print(f"🤖 Starting Stage 2: Precision AI Sentiment & Spam Analysis...")
records_to_analyze = [r for r in all_records if r["brand"] == "1" and r["keywords"]]
total_to_analyze = len(records_to_analyze)
processed_count = 0

def process_single_record(record):
    kws_list = [k.strip() for k in record["keywords"].split(",") if k.strip()]
    hit_brands_list = [b for b in STANDARD_BRANDS if record.get(b) == "✓"]
    
    success, is_spam, brand_analysis = call_llm_analysis(
        record["messageBody"], 
        record["quotedMessage"], 
        kws_list, 
        hit_brands_list
    )
    return record, success, is_spam, brand_analysis

if total_to_analyze > 0:
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_single_record, record): record for record in records_to_analyze}
        for future in concurrent.futures.as_completed(futures):
            record = futures[future] 
            processed_count += 1
            
            print(f"\r   🔄 AI Processing progress: {processed_count} / {total_to_analyze}", end='', flush=True)
                
            try:
                _, success, is_spam, brand_analysis = future.result()
                if success:
                    stats["ai_actually_processed"] += 1
                    
                    for b in STANDARD_BRANDS: 
                        record[b] = ""
                        
                    if is_spam:
                        stats["spam_detected"] += 1
                        record["brand"] = ""
                        record["keywords"] = ""
                    else:
                        if not brand_analysis:
                            record["brand"] = ""
                        else:
                            friso_sub_brands = ["美素金裝", "美素皇家", "美素有機", "美素Kids", "美素Signature"]
                            friso_sentiments = []
                            for std_brand, sentiment in brand_analysis.items():
                                if std_brand in STANDARD_BRANDS: 
                                    record[std_brand] = sentiment
                                    if std_brand in friso_sub_brands or std_brand == "美素":
                                        friso_sentiments.append(sentiment)
                            
                            if friso_sentiments:
                                if "N" in friso_sentiments:
                                    record["美素"] = "N"
                                elif "P" in friso_sentiments:
                                    record["美素"] = "P"
                                elif "I" in friso_sentiments:
                                    record["美素"] = "I"
                            
                            if record.get("美素") == "N":
                                record["warning"] = "✓"
            except Exception: pass
    print() 

# ==========================================
# 💾 6. Data Cleansing & Dynamic Write to Google Sheets (Split by Date Part1/Part2)
# ==========================================
print("\n💾 Cleansing data and preparing dynamic write to Google Sheets...")
final_df = pd.DataFrame(all_records)

# 💡 Function to generate target Sheet name based on date
def get_target_sheet_name(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        yy = dt.strftime("%y") # 2-digit year, e.g., '26'
        mm = dt.strftime("%m") # 2-digit month, e.g., '07'
        dd = dt.day            # Day, e.g., 5
        part = "Part1" if dd <= 15 else "Part2"
        return f"{yy}{mm}_DailyData_{part}"
    except Exception:
        return "Unknown_Sheet"

if not final_df.empty:
    for col in FINAL_HEADERS:
        if col not in final_df.columns: final_df[col] = ""
    final_df = final_df[FINAL_HEADERS]
    
    # Standardize date format
    final_df['Date_parsed'] = pd.to_datetime(final_df['Date'], errors='coerce', dayfirst=True)
    final_df['Date'] = final_df['Date_parsed'].dt.strftime('%Y-%m-%d')
    final_df = final_df.sort_values(by=['Date_parsed', 'GroupID', 'Time']).drop(columns=['Date_parsed']).fillna("")
    
    # 💡 Calculate target sheet for each record based on date
    final_df['TargetSheet'] = final_df['Date'].apply(get_target_sheet_name)
    
    # 💡 Group and write data based on target Sheet name
    for sheet_name, group_df in final_df.groupby('TargetSheet'):
        if sheet_name == "Unknown_Sheet":
            print("⚠️ Some data dates could not be parsed, skipping write.")
            continue
            
        # Remove helper column
        write_df = group_df.drop(columns=['TargetSheet'])
        
        print(f"🔄 Searching and writing to file: {sheet_name} ...")
        try:
            sh = gc.open(sheet_name)
            worksheet = sh.worksheet(MASTER_WORKSHEET_NAME)
            worksheet.append_rows(write_df.values.tolist(), value_input_option='USER_ENTERED')
            print(f"✅ Successfully appended {len(write_df)} rows to {sheet_name}!")
            
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"❌ Could not find Google Sheet named: 【{sheet_name}】")
            print(f"   👉 Please ensure the file is created in Google Drive and shared with the service account email.")
        except Exception as e:
            print(f"❌ Failed to write to {sheet_name}: {e}")
else:
    print("⚠️ No valid data to write for the target dates.")

print_stage_dashboard("Final Stage: Automation Task Completed", {
    "🎯 Expected AI processing rows": f"{stats['need_ai_processing']}",
    "✅ Actual AI processed rows": f"{stats['ai_actually_processed']}",
    "🗑️ Detected as Spam (Invalid)": f"{stats['spam_detected']}",
    "📝 Final rows written to Sheets": f"{len(final_df) if not final_df.empty else 0}"
})

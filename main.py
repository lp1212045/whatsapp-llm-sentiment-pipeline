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
 
# Google 相關套件
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
 
# 匯入 openai 庫以使用 Poe API
import openai
 
# ==========================================
# 🌟 0. 授權 Google API (Sheets & Drive)
# ==========================================
print("🚀 正在使用服務帳戶自動授權 Google API...")
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
# 建議將金鑰檔案名稱也設為環境變數，並確保該檔案有加入 .gitignore
SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", 'service_account.json')
 
try:
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    drive_service = build('drive', 'v3', credentials=creds)
    print("✅ 服務帳戶授權成功！\n")
except Exception as e:
    print(f"❌ 授權失敗，請檢查 {SERVICE_ACCOUNT_FILE} 是否存在。錯誤訊息: {e}")
    sys.exit()
 
# ==========================================
# ⚙️ 1. 參數與配置設定 (已去敏)
# ==========================================
N8N_RAW_FOLDER_ID = os.environ.get("N8N_RAW_FOLDER_ID", "YOUR_DRIVE_FOLDER_ID")
KEYWORDS_SHEET_URL = os.environ.get("KEYWORDS_SHEET_URL", "YOUR_KEYWORDS_SHEET_URL")
GROUPINFO_SHEET_URL = os.environ.get("GROUPINFO_SHEET_URL", "YOUR_GROUPINFO_SHEET_URL")
MASTER_SHEET_URL = os.environ.get("MASTER_SHEET_URL", "YOUR_MASTER_SHEET_URL")
MASTER_WORKSHEET_NAME = os.environ.get("MASTER_WORKSHEET_NAME", "YOUR_WORKSHEET_NAME") 
 
MANUAL_TARGET_DATES = ["YYMMDD_1", "YYMMDD_2", "YYMMDD_3"] # 這裡可以放多個日期測試了
 
POE_API_KEY = os.environ.get("POE_API_KEY", "YOUR_POE_API_KEY")
POE_MODEL = os.environ.get("POE_MODEL", "gemini-2.5-flash") 
 
poe_client = openai.OpenAI(
    api_key=POE_API_KEY,
    base_url="https://api.poe.com/v1",
)
 
# 內部測試/種子用戶手機號碼 (已去敏)
SEEDER_PHONES = {
    "YOUR_SEEDER_PHONE_1", "YOUR_SEEDER_PHONE_2", "YOUR_SEEDER_PHONE_3"
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
] + STANDARD_BRANDS
 
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
    print(f"📊 {stage_name} - 統計看板")
    print("="*50)
    for key, value in metrics.items():
        print(f"{key:<22} : {value}")
    print("="*50 + "\n")
 
# ==========================================
# 🏷️ 新增：品牌映射函數 (將英文代號轉為標準中文品牌名)
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
# 🧠 2. AI 情感與垃圾分析函數 (加入強化版重試機制)
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
        "reasoning": "分析過程...",
        "isSpam": False,
        "brand_analysis": {b: "N/P/I" for b in hit_brands_list} if hit_brands_list else {}
    }
    json_template_str = json.dumps(json_template, ensure_ascii=False, indent=2)
 
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
    2. 情緒分析 (brand_analysis): 
       - "N" (負面/需客服介入): 生理不適、抱怨、焦慮疑問。
       - "P" (正面): 滿意、推介、穩定飲用 (如「無事」、「安心」)。
       - "I" (中立): 純詢價、客觀陳述。
    
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
# 📥 3. 透過 Google Drive API 下載目標日期的檔案
# ==========================================
hk_tz = pytz.timezone('Asia/Hong_Kong')
 
if MANUAL_TARGET_DATES and MANUAL_TARGET_DATES[0] != "YYMMDD_1":
    target_dates = MANUAL_TARGET_DATES
else:
    target_dates = [(datetime.now(hk_tz) - timedelta(days=1)).strftime("%y%m%d")]
 
print(f"📅 準備處理的日期列表: {target_dates}")
 
LOCAL_RAW_DIR = "./temp_raw_data"
os.makedirs(LOCAL_RAW_DIR, exist_ok=True)
daily_file_paths = []
 
print("📂 正在透過 Google Drive API 搜尋並下載檔案...")
try:
    for date_str in target_dates:
        print(f"\n🔍 正在搜尋日期 [{date_str}] 的資料夾...")
        
        # 📂 新增：為每一天建立獨立的子資料夾
        date_dir = os.path.join(LOCAL_RAW_DIR, date_str)
        os.makedirs(date_dir, exist_ok=True)
        
        query = f"'{N8N_RAW_FOLDER_ID}' in parents and name contains '{date_str}000000' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        folders = results.get('files', [])
 
        if not folders:
            continue
 
        for folder in folders:
            print(f"📁 找到資料夾: {folder['name']}")
            
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
                
                # 📝 修改：將檔案存入對應日期的子資料夾中
                local_path = os.path.join(date_dir, file['name'])
                
                fh = io.FileIO(local_path, 'wb')
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                daily_file_paths.append(local_path)
                
                download_count += 1
                print(f"\r   ⏳ [{date_str}] 檔案下載進度: {download_count} / {total_files}", end='', flush=True)
            print()
 
except Exception as e:
    print(f"❌ 下載檔案失敗: {e}")
    sys.exit()
 
stats["csv_files"] = len(daily_file_paths)
 
# ---------------------------------------------------------
# 讀取 Google Sheets 配置檔 (Keywords & GroupInfo)
# ---------------------------------------------------------
print("\n📑 正在從 Google Sheets 讀取配置檔 (Keywords & GroupInfo)...")
try:
    kw_sheet = gc.open_by_url(KEYWORDS_SHEET_URL).sheet1
    keywords_df = pd.DataFrame(kw_sheet.get_all_records())
    
    gi_sheet = gc.open_by_url(GROUPINFO_SHEET_URL).worksheet('groups')
    groupinfo_df = pd.DataFrame(gi_sheet.get_all_records())
    groupinfo_df = groupinfo_df[['gus_id', 'subject']]
    
    print("✅ 配置檔讀取成功！")
except Exception as e:
    print(f"❌ 讀取配置檔失敗: {e}")
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
 
print_stage_dashboard("環境與配置解析", {
    "📁 下載的目標檔案數": f"{stats['csv_files']} 個",
    "🕵️ 載入的品牌關鍵字數": f"{sum(len(v) for v in brand_keywords.values())} 個",
    "👥 載入的群組資訊數": f"{len(group_map)} 個"
})
 
# ==========================================
# ⚡ 4. 第一階段：規則匹配與打標
# ==========================================
def get_phone_score(phone):
    phone = str(phone).strip()
    if phone.startswith("852") and "@" not in phone: return 3  
    elif "@" not in phone and re.match(r'^\d+$', phone): return 2  
    else: return 1  
 
records_dict = {} 
print("⚡ 開始進行第一階段：規則匹配與打標...")
for file_path in daily_file_paths:
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
                        # 🔧 修復核心：將匹配到的原始 brand+product 映射為 STANDARD_BRANDS
                        for kd in valid_hits:
                            std_brand = get_standard_brand(brand, kd["product"])
                            if std_brand not in hit_brands:
                                hit_brands.append(std_brand)
                                
                            if kd["kw"] not in hit_keywords:
                                hit_keywords.append(kd["kw"])
                            if kd["kw"] in all_brand_related_kws:
                                has_brand_keyword = True
 
            cleaned_body = re.sub(r'\s+', '', body)
            
            # ==========================================
            # 🔑 核心修改：將 phone_for_check 加入 fingerprint
            # ==========================================
            fingerprint = f"{group_id}_{date_val}_{time_val}_{phone_for_check}_{cleaned_body}"
            
            brand_status = ""
            if hit_brands and has_brand_keyword:
                brand_status = "1"
                for b in hit_brands:
                    if b in STANDARD_BRANDS: brand_marks[b] = "✓"
 
            record = {
                "Group": group_name, "GroupID": group_id, "Date": date_val, "Time": time_val,
                "userPhone": phone_raw, "Internal": internal_flag, "quotedMessage": quoted,
                "messageBody": body, "brand": brand_status, "keywords": ", ".join(hit_keywords),
                "warning": "", "reply": "", **brand_marks
            }
 
            current_phone_score = get_phone_score(phone_raw)
            if fingerprint in records_dict:
                if current_phone_score > get_phone_score(records_dict[fingerprint]["userPhone"]):
                    records_dict[fingerprint] = record
            else:
                records_dict[fingerprint] = record
    except Exception as e:
        print(f"❌ 讀取檔案 {file_name} 失敗: {e}")
 
all_records = list(records_dict.values())
stats["total_deduped_rows"] = len(all_records)
stats["need_ai_processing"] = sum(1 for r in all_records if r["brand"] == "1")
 
print_stage_dashboard("第一階段：規則匹配與打標", {
    "📑 原始對話數據總行數": f"{stats['total_raw_rows']} 行",
    "🧹 去重後保留的總行數": f"{stats['total_deduped_rows']} 行",
    "🎯 命中品牌需 AI 處理": f"{stats['need_ai_processing']} 行"
})
 
# ==========================================
# 🤖 5. 第二階段：精準 AI 分析
# ==========================================
print(f"🧠 開始進行第二階段：精準 AI 情感與垃圾分析...")
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
            
            print(f"\r   🤖 AI 處理進度: {processed_count} / {total_to_analyze}", end='', flush=True)
                
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
# 📝 6. 數據清洗與寫入 Google Sheets
# ==========================================
print("\n🧹 正在清洗數據並準備寫入 Google Sheets...")
final_df = pd.DataFrame(all_records)
 
if not final_df.empty:
    for col in FINAL_HEADERS:
        if col not in final_df.columns: final_df[col] = ""
    final_df = final_df[FINAL_HEADERS]
    final_df['Date_parsed'] = pd.to_datetime(final_df['Date'], errors='coerce', dayfirst=True)
    final_df['Date'] = final_df['Date_parsed'].dt.strftime('%Y-%m-%d')
    final_df = final_df.sort_values(by=['Date_parsed', 'GroupID', 'Time']).drop(columns=['Date_parsed']).fillna("")
 
    try:
        sh = gc.open_by_url(MASTER_SHEET_URL)
        worksheet = sh.worksheet(MASTER_WORKSHEET_NAME)
        worksheet.append_rows(final_df.values.tolist(), value_input_option='USER_ENTERED')
        print(f"✅ 成功將 {len(final_df)} 筆資料附加到 Google Sheet 中！")
    except Exception as e:
        print(f"❌ 寫入 Google Sheets 失敗: {e}")
else:
    print("⚠️ 目標日期無有效數據可寫入。")
 
print_stage_dashboard("最終階段：自動化任務完成", {
    "🎯 預期需 AI 處理數": f"{stats['need_ai_processing']} 行",
    "✅ AI 實際成功處理數": f"{stats['ai_actually_processed']} 行",
    "🗑️ 判定為 Spam (無效)": f"{stats['spam_detected']} 行",
    "📝 最終寫入 Sheets 行數": f"{len(final_df) if not final_df.empty else 0} 行"
})

import os
import time
import traceback
import pandas as pd
from datetime import datetime, timedelta

# Import shared modules and configurations
from google_auth import get_google_clients, with_retry
from config import MILK_POWDER_BRANDS, BUSINESS_KEYWORDS, OTHER_BRANDS_KEYWORDS, SIM_MASTER_URL, SIM_MASTER_TAB_NAME

# ==========================================
# ⚙️ Custom Settings & Helper Functions
# ==========================================
PREFIXES_TO_REMOVE = ['852'] 

def clean_phone(p):
    """Clean phone numbers"""
    if pd.isna(p): return ""
    p_str = str(p).strip()
    if p_str.endswith('.0'):
        p_str = p_str[:-2]
    for prefix in PREFIXES_TO_REMOVE:
        if p_str.startswith(prefix):
            p_str = p_str[len(prefix):]
            break 
    return p_str

def simplify_brand(brand_name):
    """Simplify subdivided product lines into unified main brand names"""
    b_lower = str(brand_name).lower()
    
    if '雅培' in b_lower or 'abbott' in b_lower: return 'Abbott'
    if '愛他美' in b_lower or 'apta' in b_lower: return 'Apta'
    if '牛欄' in b_lower or 'cow' in b_lower or 'gate' in b_lower: return 'Cow & Gate'
    if '喜寶' in b_lower or 'hipp' in b_lower: return 'HiPP'
    if '惠氏' in b_lower or 'wyeth' in b_lower or 'illuma' in b_lower or '啟賦' in b_lower: return 'Wyeth'
    if '美贊臣' in b_lower or 'mead johnson' in b_lower or 'enfamil' in b_lower or 'mj' in b_lower: return 'MJ'
    if '雀巢' in b_lower or 'nestle' in b_lower: return 'Nestle'
    if '美素' in b_lower or 'friso' in b_lower: return 'Friso'
    if '雪印' in b_lower or 'snow' in b_lower: return 'Snow'
    
    return brand_name.strip()

def format_brand_mentions(mentions_str):
    """Convert raw brand mention strings into a statistical format, categorizing product lines into main brands"""
    if not mentions_str: return ""
    items = [i.strip() for i in mentions_str.split(',') if i.strip()]
    if not items: return ""
    
    brand_stats = {}
    for item in items:
        if ':' not in item: continue
        b, s = item.split(':', 1)
        # Call simplify_brand here to map to main brand
        b = simplify_brand(b.strip())
        s = s.strip()
        
        if b not in brand_stats:
            brand_stats[b] = {'P': 0, 'I': 0, 'N': 0, 'Total': 0}
        if s in ['P', 'I', 'N']:
            brand_stats[b][s] += 1
            brand_stats[b]['Total'] += 1
            
    result = []
    for b, stats in brand_stats.items():
        if stats['Total'] > 0:
            result.append(f"•{b}: Total: {stats['Total']} (P: {stats['P']}, I: {stats['I']}, N: {stats['N']})")
    return "\n".join(result)

def get_required_sheet_names(target_date, days=30):
    sheet_names = set()
    for i in range(days):
        date_to_check = target_date - timedelta(days=i)
        yy = date_to_check.strftime('%y')
        mm = date_to_check.strftime('%m')
        part = "Part1" if date_to_check.day <= 15 else "Part2"
        sheet_names.add(f"{yy}{mm}_DailyData_{part}")
    return sorted(list(sheet_names))

@with_retry()
def fetch_sheet_data(gc, sheet_name, tab_name="Sheet1"):
    sh = gc.open(sheet_name)
    return sh.worksheet(tab_name).get_all_records()

@with_retry()
def fetch_sheet_data_by_url(gc, url, tab_name):
    sh = gc.open_by_url(url)
    return sh.worksheet(tab_name).get_all_records()

@with_retry()
def update_sheet_data_by_url(gc, url, tab_name, df_final):
    sh = gc.open_by_url(url)
    ws = sh.worksheet(tab_name)
    ws.clear()
    ws.update([df_final.columns.values.tolist()] + df_final.values.tolist())

def main():
    print("🚀 Starting SimMaster Risk Analysis (Rule-based architecture)...", flush=True)
    today = datetime.now()
    cutoff_date = today - timedelta(days=30)
    
    print(f"📅 Preparing to backtrack 30 days of data (since {cutoff_date.strftime('%Y-%m-%d')})", flush=True)
    
    gc, _, _ = get_google_clients()
    required_sheets = get_required_sheet_names(today, days=30)
    
    all_daily_data = []
    successful_sheets = 0
    
    for sheet_name in required_sheets:
        try:
            print(f"   🔍 Searching for {sheet_name}...", end="", flush=True)
            data = fetch_sheet_data(gc, sheet_name) 
            if data: 
                all_daily_data.append(pd.DataFrame(data))
                successful_sheets += 1
                print(f" ✅ Successfully read {len(data)} rows", flush=True)
            else:
                print(" ⚠️ Sheet is empty", flush=True)
        except Exception: 
            print(f" ⚠️ Skipped (May not be created yet)", flush=True)
            
    if not all_daily_data: 
        print("\n❌ Could not find any Daily Data. Program terminated.", flush=True)
        return
        
    df_raw = pd.concat(all_daily_data, ignore_index=True)
    total_raw_rows = len(df_raw)
    
    required_cols = ['Date', 'userPhone', 'messageBody', 'GroupID', 'Group']
    missing_cols = [col for col in required_cols if col not in df_raw.columns]
    if missing_cols:
        print(f"\n❌ Error: Daily Data is missing required columns: {missing_cols}", flush=True)
        return
        
    df_raw['Date_Parsed'] = pd.to_datetime(df_raw['Date'], format='%Y-%m-%d', errors='coerce')
    df_recent = df_raw[df_raw['Date_Parsed'] >= cutoff_date].copy()
    valid_rows = len(df_recent)
    
    print("\n==================================================")
    print("📊 Stage 1: Data Fetching")
    print("==================================================")
    print(f"📂 Sheets read successfully     : {successful_sheets}")
    print(f"📝 Total raw rows               : {total_raw_rows}")
    print(f"📅 Valid rows (last 30 days)    : {valid_rows}")
    print("==================================================\n")
    
    if df_recent.empty:
        print("❌ No valid data within the last 30 days. Program terminated.", flush=True)
        return
        
    print("🔄 Aggregating user behavior data...", flush=True)
    brand_cols = [col for col in MILK_POWDER_BRANDS if col in df_recent.columns]
    
    def extract_mentions(row):
        return ", ".join([f"{col}:{str(row.get(col, '')).strip()}" for col in brand_cols if str(row.get(col, '')).strip() in ['P', 'I', 'N']])
        
    df_recent['Brand_Mentions_Str'] = df_recent.apply(extract_mentions, axis=1)
    
    df_grouped = df_recent.groupby('userPhone').agg(
        Total_Messages=('messageBody', 'count'),
        Total_Groups=('GroupID', 'nunique'),
        Group_List=('Group', lambda x: ", ".join(set([str(i) for i in x if str(i).strip()]))),
        All_Messages=('messageBody', lambda x: " | ".join(str(i) for i in x)),
        Brand_Mentions_Str=('Brand_Mentions_Str', lambda x: ", ".join([i for i in x if i])),
        Last_Spoke_Date=('Date', 'max') 
    ).reset_index()
    
    df_grouped['Brand Mentions'] = df_grouped['Brand_Mentions_Str'].apply(format_brand_mentions)
    df_grouped['userPhone'] = df_grouped['userPhone'].apply(clean_phone)
    active_users = len(df_grouped)
    
    print(f"\n📥 Reading historical SIM Master ({SIM_MASTER_TAB_NAME})...", flush=True)
    final_columns = ['Status', 'UserName', 'Phone', 'Nature', 'Sub-Tag', 'Brand Name', 'Total Messages', 'Brand Mentions', 'Total Groups', 'Group List', 'Risk-Score', 'Warning', 'Last Updated']
    
    try:
        sim_data = fetch_sheet_data_by_url(gc, SIM_MASTER_URL, SIM_MASTER_TAB_NAME) 
        df_sim = pd.DataFrame(sim_data)
        historical_users = len(df_sim)
        print(f"✅ Successfully read {historical_users} historical records", flush=True)
    except Exception as e:
        historical_users = 0
        print(f"⚠️ Failed to read SIM Master or it is empty. Creating a new table. Error: {e}", flush=True)
        df_sim = pd.DataFrame(columns=final_columns)
        
    df_sim = df_sim.astype(object)
    
    print("\n🧠 Merging old/new data and evaluating rule-based risk profiles...", flush=True)
    print(f"🔍 Scanning rules for users who spoke recently (Date: {today.strftime('%Y-%m-%d')})...", flush=True)
    
    if not df_sim.empty:
        df_sim['Phone'] = df_sim['Phone'].apply(clean_phone)
        grouped_dict = df_grouped.set_index('userPhone').to_dict('index')
        
        for idx, row in df_sim.iterrows():
            phone = row['Phone']
            if phone in grouped_dict:
                new_data = grouped_dict[phone]
                
                df_sim.at[idx, 'Total Messages'] = int(new_data['Total_Messages'])
                df_sim.at[idx, 'Total Groups'] = int(new_data['Total_Groups'])
                df_sim.at[idx, 'Group List'] = str(new_data['Group_List'])
                df_sim.at[idx, 'Brand Mentions'] = str(new_data['Brand Mentions'])
                df_sim.at[idx, 'Last Updated'] = str(new_data['Last_Spoke_Date'])
                
                messages_text = new_data['All_Messages']
                mentions_str = new_data['Brand_Mentions_Str']
                
                # 1. Extract milk powder brands and business keywords
                praised_milk_brands = set()
                if mentions_str:
                    for item in mentions_str.split(','):
                        if ':' in item:
                            b, s = item.split(':', 1)
                            # Strict condition: only consider it a recommendation if sentiment is 'P'
                            if s.strip() == 'P' and b.strip() in MILK_POWDER_BRANDS:
                                praised_milk_brands.add(simplify_brand(b.strip()))
                
                triggered_business_kws = [kw for kw in BUSINESS_KEYWORDS if kw in messages_text]
                
                has_milk_brand = len(praised_milk_brands) > 0
                has_business_kw = len(triggered_business_kws) > 0
                has_other_brands = any(kw in messages_text for kw in OTHER_BRANDS_KEYWORDS)
                
                # 2. Strict evaluation logic
                risk_score = 0
                new_sub_tag = ""
                new_nature = "Real"
                final_brand_name = ""
                
                if has_milk_brand:
                    # Scenario A: Recommended milk brand (P)
                    if has_other_brands or new_data['Total_Groups'] > 5 or has_business_kw:
                        risk_score += 80
                        new_sub_tag = "IFT Seeder"
                        final_brand_name = ", ".join(praised_milk_brands)
                    else:
                        risk_score += 20
                        new_sub_tag = ""
                        final_brand_name = "" 
                else:
                    # Scenario B: No milk brand recommendation
                    if has_business_kw:
                        risk_score += 60
                        new_sub_tag = "Business"
                        # Stop writing business keywords into Brand Name
                        final_brand_name = ""
                    elif has_other_brands:
                        risk_score += 30
                    
                if new_data['Total_Groups'] > 5: risk_score += 30
                if mentions_str: risk_score += 20
                    
                # Modification: Mark as Watch if score > 30
                if risk_score > 30:
                    new_nature = "Watch"
                        
                risk_score = min(risk_score, 100)
                # Confirmation: Add ✓ if score >= 80
                warning = '✓' if risk_score >= 80 else ''
                status = str(row.get('Status', '')).strip().lower()
                current_nature = str(row.get('Nature', '')).strip()
                current_sub_tag = str(row.get('Sub-Tag', '')).strip()
                
                if status == 'old':
                    if current_nature.lower() == 'white':
                        pass 
                    elif current_nature.lower() == 'black':
                        df_sim.at[idx, 'Sub-Tag'] = new_sub_tag if new_sub_tag else current_sub_tag
                        df_sim.at[idx, 'Risk-Score'] = risk_score
                        df_sim.at[idx, 'Warning'] = warning
                        if new_sub_tag: df_sim.at[idx, 'Brand Name'] = final_brand_name
                    else:
                        df_sim.at[idx, 'Nature'] = new_nature
                        df_sim.at[idx, 'Sub-Tag'] = new_sub_tag
                        df_sim.at[idx, 'Risk-Score'] = risk_score
                        df_sim.at[idx, 'Warning'] = warning
                        df_sim.at[idx, 'Brand Name'] = final_brand_name
                else:
                    df_sim.at[idx, 'Nature'] = new_nature
                    df_sim.at[idx, 'Sub-Tag'] = new_sub_tag
                    df_sim.at[idx, 'Risk-Score'] = risk_score
                    df_sim.at[idx, 'Warning'] = warning
                    df_sim.at[idx, 'Brand Name'] = final_brand_name
                    
        existing_phones = set(df_sim['Phone'].tolist())
        new_users_list = []
        
        for phone, new_data in grouped_dict.items():
            if phone not in existing_phones:
                messages_text = new_data['All_Messages']
                mentions_str = new_data['Brand_Mentions_Str']
                
                # 1. Extract brands and keywords (New Users)
                praised_milk_brands = set()
                if mentions_str:
                    for item in mentions_str.split(','):
                        if ':' in item:
                            b, s = item.split(':', 1)
                            if s.strip() == 'P' and b.strip() in MILK_POWDER_BRANDS:
                                praised_milk_brands.add(simplify_brand(b.strip()))
                
                triggered_business_kws = [kw for kw in BUSINESS_KEYWORDS if kw in messages_text]
                
                has_milk_brand = len(praised_milk_brands) > 0
                has_business_kw = len(triggered_business_kws) > 0
                has_other_brands = any(kw in messages_text for kw in OTHER_BRANDS_KEYWORDS)
                
                # 2. Strict evaluation logic (New Users)
                risk_score = 0
                new_sub_tag = ""
                new_nature = "Real"
                final_brand_name = ""
                
                if has_milk_brand:
                    if has_other_brands or new_data['Total_Groups'] > 5 or has_business_kw:
                        risk_score += 80
                        new_sub_tag = "IFT Seeder"
                        final_brand_name = ", ".join(praised_milk_brands)
                    else:
                        risk_score += 20
                        new_sub_tag = ""
                        final_brand_name = "" 
                else:
                    if has_business_kw:
                        risk_score += 60
                        new_sub_tag = "Business"
                        final_brand_name = ""
                    elif has_other_brands:
                        risk_score += 30
                    
                if new_data['Total_Groups'] > 5: risk_score += 30
                if mentions_str: risk_score += 20
                    
                if risk_score > 30:
                    new_nature = "Watch"
                        
                risk_score = min(risk_score, 100)
                                
                new_users_list.append({
                    'Status': 'New',
                    'UserName': '',
                    'Phone': phone,
                    'Nature': new_nature,
                    'Sub-Tag': new_sub_tag,
                    'Brand Name': final_brand_name,
                    'Total Messages': int(new_data['Total_Messages']),
                    'Brand Mentions': str(new_data['Brand Mentions']),
                    'Total Groups': int(new_data['Total_Groups']),
                    'Group List': str(new_data['Group_List']),
                    'Risk-Score': risk_score,
                    'Warning': '✓' if risk_score >= 80 else '',
                    'Last Updated': str(new_data['Last_Spoke_Date'])
                })
                
        if new_users_list:
            df_merged = pd.concat([df_sim, pd.DataFrame(new_users_list)], ignore_index=True)
        else:
            df_merged = df_sim.copy()
            
    else:
        print("⚠️ Warning: Historical sheet is empty, writing new users directly.")
        return
        
    for col in final_columns:
        if col not in df_merged.columns: df_merged[col] = ''
            
    df_final = df_merged[final_columns].fillna('')
    df_final['Risk-Score'] = pd.to_numeric(df_final['Risk-Score'], errors='coerce').fillna(0)
    
    df_final['Sort_Order'] = df_final['Status'].apply(lambda x: 0 if str(x).strip().lower() == 'old' else 1)
    df_final = df_final.sort_values(by=['Sort_Order', 'Risk-Score'], ascending=[True, False]).drop(columns=['Sort_Order'])
    df_final['Risk-Score'] = df_final['Risk-Score'].astype(object)
    
    df_final.loc[df_final['Nature'].str.strip().str.lower() == 'white', 'Risk-Score'] = ''
    df_final.loc[df_final['Nature'].str.strip().str.lower() == 'white', 'Warning'] = ''
    
    # Calculate Stage 2 statistics
    total_users = len(df_final)
    watch_count = len(df_final[df_final['Nature'].str.strip().str.lower() == 'watch'])
    business_count = len(df_final[df_final['Sub-Tag'].str.strip().str.lower() == 'business'])
    ift_seeder_count = len(df_final[df_final['Sub-Tag'].str.strip().str.lower() == 'ift seeder'])
    
    print("\n==================================================")
    print("📊 Stage 2: Analysis & Evaluation Results")
    print("==================================================")
    print(f"👥 Active unique users (30d)    : {active_users}")
    print(f"📚 Historical base users        : {historical_users}")
    print(f"📈 Total users post-merge       : {total_users}")
    print(f"⚠️ Evaluated as Watch (High)    : {watch_count}")
    print(f"💼 Evaluated as Business        : {business_count}")
    print(f"🕵️‍♂️ Evaluated as IFT Seeder      : {ift_seeder_count}")
    print("==================================================\n")
    
    print("💾 Writing latest results back to SIM Master Google Sheet...", flush=True)
    update_sheet_data_by_url(gc, SIM_MASTER_URL, SIM_MASTER_TAB_NAME, df_final) 
    print(f"✅ System execution complete! Successfully updated {total_users} user records to SIM Master ({SIM_MASTER_TAB_NAME} tab).", flush=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n" + "="*50)
        print("❌ Fatal Error occurred (Exit Code 1)! Details below:")
        print("="*50)
        traceback.print_exc() 
        print("="*50)
        exit(1)

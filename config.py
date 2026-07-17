# ==========================================
# ⚙️ Global Configuration File (config.py)
# ==========================================

# 🍼 Core Milk Powder Brands (Used by main.py, risk_analysis.py, dashboard.py)
MILK_POWDER_BRANDS = [
    "雅培心美力", "Apta Platinum", "Apta Essensis", "Apta Neo", "牛欄牌", 
    "美素", "美素金裝", "美素皇家", "美素有機", "美素Kids", "美素Signature", 
    "Hipp", "Illuma", "Illuma 有機", "美贊臣 A+", "美贊臣 Enfinitas", 
    "雀巢能恩", "雀巢全護"
]

# 💼 Business / Promotional Keywords (Used by risk_analysis.py)
BUSINESS_KEYWORDS = [
    '私訊', '代購', '團購', '報價', '優惠碼', '加我', '拼單', 'pm', 'inbox', 
    '了解詳情', '留名', '代理', '批發', '招商', '兼職', '賺錢', '有興趣pm', 
    '清貨', '全新未開', '轉讓', '平放'
]

# 🏥 Cross-industry Brands / Services Keywords (Used by risk_analysis.py)
OTHER_BRANDS_KEYWORDS = [
    '幫寶適', 'Pampers', '滿意寶寶', 'Moony', '妙而舒', 'Merries', '大王', 'GOO.N', 'Huggies', '好奇',
    '宏利', 'Manulife', '保誠', 'Prudential', '友邦', 'AIA', '安盛', 'AXA', '儲蓄保', '基金', '理財', '醫療保',
    '扎肚', '陪月', '百日宴', '攝影', '滴雞精', '衍生', '益生菌', '孕婦維他命', '催乳', '通乳'
]

# 🎯 Sim Master Configuration
SIM_MASTER_URL = "YOUR_SIM_MASTER_SHEET_URL" # Sanitized for portfolio
SIM_MASTER_TAB_NAME = "Test"

# 📊 Dashboard Specific Configuration
BRAND_MAPPING = {
    "Abbott": ["雅培心美力"],
    "Apta": ["Apta Platinum", "Apta Essensis", "Apta Neo"],
    "Cow & Gate": ["牛欄牌"],
    "HiPP": ["Hipp"],
    "Mead Johnson": ["美贊臣 A+", "美贊臣 Enfinitas"],
    "Nestle": ["雀巢能恩", "雀巢全護"],
    "Wyeth / illuma": ["Illuma", "Illuma 有機"]
}

FRISO_SUB_BRANDS = ["美素金裝", "美素皇家", "美素有機", "美素Kids", "美素Signature"]
FRISO_MAIN = "美素"

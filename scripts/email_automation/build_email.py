import json

with open('/tmp/metrics.json') as f:
    m = json.load(f)

with open('/tmp/alerts.json') as f:
    alert_data = json.load(f)

alerts = alert_data['alerts']
target_date = m['target_date']

# Sanitized URLs for portfolio demonstration
dashboard_url = "https://docs.google.com/spreadsheets/d/YOUR_DASHBOARD_SHEET_ID/edit"
daily_data_url = "https://docs.google.com/spreadsheets/d/YOUR_DAILY_DATA_SHEET_ID/edit"

# Build negative sentiment alert section
if alerts:
    alert_lines = []
    for idx, alert in enumerate(alerts, 1):
        lines = [f"Alert {idx}"]
        lines.append(f"• Group: {alert['group']}")
        lines.append(f"• Time: {alert['time']}")
        lines.append(f"• User Phone: {alert['userPhone']}")
        if alert.get('quotedMessage'):
            lines.append(f"• Quoted Message: \"{alert['quotedMessage']}\"")
        lines.append(f"• Message Body: \"{alert['messageBody']}\"")
        alert_lines.append('\n'.join(lines))
    alerts_section = '\n\n'.join(alert_lines)
else:
    alerts_section = "No negative sentiment alerts for this date."

# Construct Email Body
content = f"""Dear Team,

Please find below the summary of the daily data for {target_date}.

Key Metrics for {target_date}:
• Total Reach: {m.get('reach', '0')}
• Total Reach (Unique): {m.get('unique_reach', '0')}

Group Classification Breakdown:
• Total Group: {m.get('total_group', '0')}
• Stages: {m.get('stages', '0')}
• Hospitals: {m.get('hospitals', '0')}
• IFT topics: {m.get('ift_topics', '0')}
• Education: {m.get('education', '0')}
• Shopping: {m.get('shopping', '0')}
• Location: {m.get('location', '0')}

Core Brand Mention / Sentiment:
• Core Brand (unique): Total: {m.get('core_brand_total', '0')} (P: {m.get('core_p', '0')}, I: {m.get('core_i', '0')}, N: {m.get('core_n', '0')})

🚨 Urgent: Core Brand related with Warning:
{alerts_section}

The updated data can be found in:
• IFT Cloud - Daily Dashboard: {dashboard_url}
• {target_date} Data: {daily_data_url}

Best regards,
Manus AI Automation
"""

# Prepare payload for Gmail API Connector
email_payload = {
    "messages": [
        {
            "to": ["manager@yourcompany.com"],
            "cc": [
                "team_lead@yourcompany.com",
                "cs_department@yourcompany.com"
            ],
            "subject": f"IFT Cloud - Daily Dashboard Summary & Alerts - {target_date}",
            "content": content
        }
    ]
}

with open('/tmp/email_payload.json', 'w', encoding='utf-8') as f:
    json.dump(email_payload, f, ensure_ascii=False, indent=2)

print(f"Subject: IFT Cloud - Daily Dashboard Summary & Alerts - {target_date}")
print(f"Alerts processed: {len(alerts)}")
print("Email payload successfully generated.")

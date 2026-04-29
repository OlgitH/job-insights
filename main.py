import os
import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import numpy as np
from datetime import datetime
import time
from dotenv import load_dotenv
import json

# --- 1. CONFIGURATION ---
load_dotenv()
APP_ID = os.getenv("ADZUNA_APP_ID")
APP_KEY = os.getenv("ADZUNA_APP_KEY")

# Ensure the public directory exists for Next.js/GitHub Actions
OUTPUT_DIR = "public"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

GREEN_TITLE_KEYS = ['solar', 'retrofit', 'heat pump', 'renewable', 'net zero', 'ecology', 'sustainability officer', 'decarbonisation', 'wind turbine', 'ashp']
DESIGN_TITLE_KEYS = ['graphic designer', 'ux designer', 'ui designer', 'product designer', 'creative lead', 'illustrator', 'content designer', 'interaction designer']

SEARCH_MAP = {
    "Green": GREEN_TITLE_KEYS,
    "Software/Tech": ['software', 'developer', 'cybersecurity', 'data scientist', 'python', 'javascript'],
    "Design": DESIGN_TITLE_KEYS,
    "Engineering": ['mechanical engineer', 'civil engineer', 'electrical engineer', 'structural engineer', 'building services engineer'],
    "Construction": ['builder', 'plumber', 'electrician', 'carpenter', 'bricklayer', 'site manager'],
    "Health": ['nurse', 'doctor', 'healthcare', 'medical'],
    "Education": ['teacher', 'lecturer', 'professor', 'tutor'],
    "Finance": ['accountant', 'banking', 'auditor', 'finance'],
    "Legal": ['solicitor', 'lawyer', 'paralegal'],
    "Legacy (Tourism/Retail)": ['retail', 'hotel', 'waiter', 'customer service']
}

# --- 2. DATA COLLECTION ---
def fetch_job_market_snapshot():
    all_raw_data = []
    url = "https://api.adzuna.com/v1/api/jobs/gb/search/1"
    print(f"--- STARTING PRECISION FETCH ---")
    
    for category, keywords in SEARCH_MAP.items():
        for word in keywords[:3]: 
            params = {
                'app_id': APP_ID, 'app_key': APP_KEY,
                'results_per_page': 50, 'where': 'Bristol',
                'what': word, 'distance': 15, 'content-type': 'application/json'
            }
            try:
                r = requests.get(url, params=params, timeout=15)
                if r.status_code == 200:
                    all_raw_data.extend(r.json().get('results', []))
                time.sleep(0.6) 
            except Exception as e:
                print(f"Error fetching {word}: {e}")
    return all_raw_data

# --- 3. CATEGORIZATION ---
def apply_negative_logic_tagging(raw_jobs):
    tagged_jobs = []
    seen_ids = set()
    
    for job in raw_jobs:
        job_id = job.get('id')
        if job_id in seen_ids: continue
        
        title = str(job.get('title', '')).lower()
        
        if any(eng in title for eng in ['mechanical', 'civil', 'structural', 'electronic', 'compliance']):
            job['assigned_category'] = "Engineering"
            tagged_jobs.append(job)
            seen_ids.add(job_id)
            continue

        if any(word in title for word in GREEN_TITLE_KEYS):
            job['assigned_category'] = "Green"
            tagged_jobs.append(job)
            seen_ids.add(job_id)
            continue

        if any(word in title for word in DESIGN_TITLE_KEYS):
            if not any(ex in title for ex in ['engineer', 'sales', 'manager', 'business development']):
                job['assigned_category'] = "Design"
                tagged_jobs.append(job)
                seen_ids.add(job_id)
                continue

        for category in ["Software/Tech", "Construction", "Health", "Education", "Finance", "Legal", "Legacy (Tourism/Retail)"]:
            if any(word in title for word in SEARCH_MAP[category]):
                job['assigned_category'] = category
                tagged_jobs.append(job)
                seen_ids.add(job_id)
                break
                
    return tagged_jobs

# --- 4. REPORT GENERATION ---
def run_report(tagged_jobs):
    if not tagged_jobs: 
        print("No jobs to process.")
        return

    df = pd.DataFrame(tagged_jobs)
    df['created'] = pd.to_datetime(df['created'])
    # Use UTC for GitHub Actions compatibility
    today = datetime.now(df['created'].dt.tz)
    df['days_on_market'] = (today - df['created']).dt.days

    summary = df.groupby('assigned_category').agg({
        'days_on_market': 'mean', 
        'title': 'count'
    }).rename(columns={'title': 'vacancies', 'days_on_market': 'friction'})
    
    all_themes = list(SEARCH_MAP.keys())
    summary = summary.reindex(all_themes).fillna(0)
    
    demand_targets = {
        'Green': 95, 'Software/Tech': 70, 'Design': 45, 'Engineering': 80, 
        'Construction': 60, 'Education': 50, 'Health': 85, 'Finance': 45, 
        'Legal': 40, 'Legacy (Tourism/Retail)': 30
    }
    summary['target'] = summary.index.map(demand_targets)

    # Export raw data to JSON for Next.js API/Frontend usage
    json_path = os.path.join(OUTPUT_DIR, 'job_data.json')
    summary.reset_index().to_json(json_path, orient='records')
    print(f"Data exported to {json_path}")

    # --- PLOTTING ---
    fig = plt.figure(figsize=(16, 28), facecolor='white')
    ax1 = plt.subplot2grid((5, 1), (0, 0))
    
    x_pos = np.arange(len(summary.index))
    max_f = summary['friction'].max() if summary['friction'].max() > 0 else 30
    cmap = plt.get_cmap('Reds') 
    colors = [cmap(mcolors.Normalize(vmin=0, vmax=max_f)(max_f - val)) for val in summary['friction']]

    ax1.bar(x_pos, summary['vacancies'], width=0.8, color=colors, edgecolor='#333333', alpha=0.9)
    ax1.step(x_pos, summary['target'], where='mid', color='#D2691E', linestyle='--', linewidth=3, label='WECA Target')
    ax1.set_xticks(x_pos)
    ax1.set_xticklabels(summary.index, rotation=35, ha='right')
    ax1.set_title('Cleaned Bristol Matrix: Title-First Priority Filtering', fontsize=20)
    ax1.legend()

    # Table Area
    ax2 = plt.subplot2grid((5, 1), (1, 0), rowspan=4)
    ax2.axis('off')
    
    report_y = 1.0
    for cat in all_themes:
        ax2.text(0, report_y, f"■ {cat.upper()}", fontsize=12, fontweight='bold', transform=ax2.transAxes)
        report_y -= 0.012
        cat_df = df[df['assigned_category'] == cat].sort_values('days_on_market').head(5)
        if cat_df.empty:
            ax2.text(0.02, report_y, "No specific vacancies found.", fontsize=9, style='italic', transform=ax2.transAxes)
            report_y -= 0.015
        else:
            for _, row in cat_df.iterrows():
                title = row['title'][:65]
                days = int(row['days_on_market'])
                company_name = str(row.get('company', {}).get('display_name', 'Unknown'))[:25]
                ax2.text(0.02, report_y, f"{days:2d}d | {title:<68} | {company_name}", fontsize=9, family='monospace', transform=ax2.transAxes)
                report_y -= 0.012
        report_y -= 0.01

    plt.tight_layout()
    img_path = os.path.join(OUTPUT_DIR, 'bristol_cleaned_report.png')
    plt.savefig(img_path, dpi=300, bbox_inches='tight')
    print(f"Report image saved to {img_path}")

if __name__ == "__main__":
    raw = fetch_job_market_snapshot()
    if raw:
        cleaned = apply_negative_logic_tagging(raw)
        run_report(cleaned)
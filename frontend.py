import streamlit as st
import requests

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Property Finder AI", page_icon="🏠", layout="wide")
BASE_URL = "https://pf-recommendation.onrender.com"

# --- 2. CSS STYLING ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] { font-family: 'Open Sans', sans-serif; color: #2b2b2b; }
    header, footer {visibility: hidden;}
    
    .search-container {
        background-color: #f8f9fa; padding: 25px; border-radius: 8px;
        border: 1px solid #e0e0e0; margin-bottom: 30px;
    }
    
    .listing-card {
        display: flex !important;
        flex-direction: row !important;
        background-color: white; border: 1px solid #e0e0e0;
        border-radius: 10px; overflow: hidden; margin-bottom: 25px;
        height: 280px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);
    }
    
    .card-image {
        width: 35% !important; flex-shrink: 0;
        background-position: center; background-size: cover;
        position: relative; background-color: #eee;
    }
    
    .pf-match-box {
        position: absolute; top: 12px; left: 12px;
        background: #36255C; color: white; padding: 6px 12px;
        border-radius: 6px; text-align: center; box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    }
    .match-score { font-size: 20px; font-weight: 800; line-height: 1; }
    .match-label { font-size: 10px; text-transform: uppercase; letter-spacing: 1px; margin-top: 2px;}

    .card-details {
        width: 65% !important; padding: 20px 25px;
        display: flex; flex-direction: column; justify-content: space-between;
    }

    .top-row { display: flex; justify-content: space-between; align-items: start; margin-bottom: 5px; }
    .prop-type { font-size: 12px; text-transform: uppercase; color: #EF5E5E; font-weight: 700; }
    .price-text { font-size: 26px; font-weight: 800; color: #2b2b2b; }
    .title-text { font-size: 16px; font-weight: 600; color: #2b2b2b; margin-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .location-text { font-size: 14px; color: #666; display: flex; align-items: center; gap: 6px; margin-bottom: 12px;}

    .icons-row { 
        display: flex; gap: 20px; font-size: 15px; font-weight: 600; color: #444; 
        background: #f9f9f9; padding: 10px; border-radius: 6px; margin-bottom: 12px;
    }

    .tags-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
    .tag { font-size: 11px; padding: 5px 10px; border-radius: 4px; font-weight: 600; text-transform: uppercase;}
    .tag-basic { background: #f1f3f5; color: #495057; }
    .tag-blue { background: #e3f2fd; color: #1565c0; border: 1px solid #bbdefb; }
    .tag-green { background: #e8f5e9; color: #2e7d32; border: 1px solid #c8e6c9; }
    .tag-gold { background: #fff8e1; color: #f57f17; border: 1px solid #ffecb3; }

    .action-row { display: flex; justify-content: space-between; align-items: center; margin-top: auto; border-top: 1px solid #eee; padding-top: 12px; }
    .agent-info { font-size: 12px; color: #888; display: flex; flex-direction: column; }
    .btn-group { display: flex; gap: 10px; }
    .btn { padding: 8px 20px; border-radius: 6px; font-weight: 600; border: none; cursor: pointer; font-size: 13px; text-decoration: none; display: inline-block; text-align: center;}
    .btn-email { background: #EF5E5E; color: white !important; }
    .btn-call { background: white; color: #EF5E5E !important; border: 1px solid #EF5E5E; }
</style>
""", unsafe_allow_html=True)

# --- 3. HELPER FUNCTIONS ---
@st.cache_data
def get_locations():
    try:
        r = requests.get(f"{BASE_URL}/locations")
        if r.status_code == 200: return r.json().get('locations', [])
    except: return []
    return []

def render_card(item, prop_type, offering):
    # 1. Clean Data
    title = str(item.get('property_title') or "Exclusive Property").strip().upper()
    price = f"{item.get('price', 0):,.0f} AED"
    loc = str(item.get('location_name') or "Dubai")
    score = item.get('final_score', 0) * 100
    
    sqft = f"{item.get('size_sqft', 0)} sqft"
    bed_txt = f"{item.get('beds_int', 0)} Beds"
    bath_txt = f"{item.get('bath_int', 0)} Baths"

    # --- 🛠️ REAL DATA EXTRACTION (NO RANDOM NUMBERS) ---
    
    # A. METRICS LOGIC: Cascade (Views -> Impressions -> Popularity)
    views = int(item.get('view_count') or 0)
    impressions = int(item.get('impression_count') or 0)
    popularity = int(item.get('smart_popularity_score') or 0)
    
    if views > 0:
        metric_txt = f"👁️ {views:,} Views"
    elif impressions > 0:
        metric_txt = f"📊 {impressions:,} Impressions"
    elif popularity > 0:
        metric_txt = f"🔥 {popularity} Popularity"
    else:
        metric_txt = "👁️ New Listing"

    # B. QUALITY SCORE
    quality = float(item.get('quality_score') or 0)
    # Ensure it doesn't look ugly if it's 0.0
    quality_txt = f"{quality}/250" if quality > 0 else "N/A"
    
    # C. AGENT BADGE (Based on real super_agent_score or quality)
    super_score = float(item.get('super_agent_score') or 0)
    is_super_agent = super_score > 0 or quality > 80

    # ----------------------------------------------------

    freshness = item.get('days_old', 0)
    fresh_label = "✨ Listed this week" if freshness < 14 else f"📅 {int(freshness)} days ago"
    
    furnish_raw = str(item.get('furnished_flag') or "").lower()
    if furnish_raw in ['yes', '1', 'furnished']: furnish_txt = "Furnished"
    elif furnish_raw in ['no', '0', 'unfurnished']: furnish_txt = "Unfurnished"
    else: furnish_txt = "Standard"
    
    status = str(item.get('completion_status') or "Ready").title()
    if status == "Nan": status = "Ready"

    super_agent_html = "<span class='tag tag-gold'>⭐ Super Agent</span>" if is_super_agent else ""

    img = "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?ixlib=rb-4.0.3&w=800&q=80"
    if "villa" in prop_type.lower(): 
        img = "https://images.unsplash.com/photo-1613977257363-707ba9348227?ixlib=rb-4.0.3&w=800&q=80"

    # HTML Construction
    html_lines = [
        f'<div class="listing-card">',
        f'  <div class="card-image" style="background-image: url(\'{img}\');">',
        f'      <div class="pf-match-box">',
        f'          <div class="match-score">{score:.1f}%</div>',
        f'          <div class="match-label">PF MATCH</div>',
        f'      </div>',
        f'  </div>',
        f'  <div class="card-details">',
        f'      <div>',
        f'          <div class="top-row">',
        f'              <div class="prop-type">{prop_type} • {offering}</div>',
        f'              <div class="price-text">{price}</div>',
        f'          </div>',
        f'          <div class="title-text">{title}</div>',
        f'          <div class="location-text">📍 {loc}</div>',
        f'          <div class="icons-row">',
        f'              <span>🛏️ {bed_txt}</span>',
        f'              <span>🛁 {bath_txt}</span>',
        f'              <span>📏 {sqft}</span>',
        f'          </div>',
        f'          <div class="tags-row">',
        f'              <span class="tag tag-blue">{fresh_label}</span>',
        f'              <span class="tag tag-green">{status}</span>',
        f'              <span class="tag tag-basic">{furnish_txt}</span>',
        f'              {super_agent_html}',
        f'          </div>',
        f'      </div>',
        f'      <div class="action-row">',
        f'          <div class="agent-info">',
        f'              <span><b>Agent Quality:</b> {quality_txt}</span>',
        f'              <span>{metric_txt}</span>',
        f'          </div>',
        f'          <div class="btn-group">',
        f'              <button class="btn btn-call">Call</button>',
        f'              <button class="btn btn-email">Email</button>',
        f'          </div>',
        f'      </div>',
        f'  </div>',
        f'</div>'
    ]
    
    st.markdown("".join(html_lines), unsafe_allow_html=True)

# --- 4. APP LOGIC ---
all_locs = get_locations()
if not all_locs: all_locs = ["Dubai Marina", "Downtown Dubai", "Business Bay"]
all_locs.insert(0, "All Locations")

st.markdown("## 🔍 Property Finder AI")
with st.container():
    st.markdown('<div class="search-container">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1: selected_loc = st.selectbox("Location", all_locs)
    with c2: offering = st.selectbox("Purpose", ["Rent", "Buy"])
    with c3: prop_type = st.selectbox("Type", ["Apartment", "Villa", "Townhouse"])
    with c4: beds = st.selectbox("Beds", ["Studio", "1 Bed", "2 Beds", "3 Beds", "4 Beds"])
    
    c5, c6, c7 = st.columns([1, 1, 2])
    with c5: min_price = st.text_input("Min Price", "50000")
    with c6: max_price = st.text_input("Max Price", "200000")
    with c7: 
        st.write(""); st.write("")
        find_btn = st.button("🔎 Find Properties", type="primary", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

if find_btn:
    try:
        mn = float(min_price.replace(',', ''))
        mx = float(max_price.replace(',', ''))
        target_price = (mn + mx) / 2
    except: target_price = 100000

    loc_val = "Dubai" if selected_loc == "All Locations" else selected_loc
    payload = {
        "price": target_price, "bedrooms": beds, "property_type": prop_type,
        "offering_type": ("Sale" if offering == "Buy" else "Rent"),
        "location_filter": loc_val, "latitude": 25.10, "longitude": 55.20
    }

    with st.spinner("Analyzing market data..."):
        try:
            resp = requests.post(f"{BASE_URL}/recommend", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                listings = data.get("data", [])
                
                if not listings: st.warning("No listings found.")
                else:
                    st.success(f"✅ Found {len(listings)} listings optimized for you.")
                    for item in listings:
                        render_card(item, prop_type, offering)
            else: st.error("API Error.")

        except Exception as e: st.error(f"Connection Error: {e}")


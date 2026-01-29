# ==========================================
# 📄 FILE: app.py (Geo-Spatial Radius Version)
# ==========================================
from flask import Flask, request, jsonify
import joblib
import pandas as pd
import numpy as np
from sklearn.neighbors import NearestNeighbors
import os

app = Flask(__name__)
MODEL_FILE = "property_finder_brain_compressed.pkl"

# --- GLOBAL VARIABLES ---
nn_model = None
preprocessor = None
df_model = pd.DataFrame()
location_centroids = {}  # NEW: Maps "Location Name" -> (Lat, Lon)

# --- UTILITY FUNCTIONS ---
def calculate_haversine(lat1, lon1, lat2, lon2):
    """Calculates distance in KM between two lat/lon points."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    a = np.sin((lat2-lat1)/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2-lon1)/2)**2
    return 2 * np.arcsin(np.sqrt(a)) * 6371

# --- 1. LOAD THE BRAIN & CALCULATE CENTROIDS ---
print("⏳ Starting Flask Server...")
if os.path.exists(MODEL_FILE):
    print(f"📂 Loading model from {MODEL_FILE}...")
    saved_data = joblib.load(MODEL_FILE)
    
    nn_model = saved_data['model']
    preprocessor = saved_data['preprocessor']
    df_model = saved_data['data']
    
    # --- 🔥 NEW: CALCULATE LOCATION CENTERS 🔥 ---
    print("🌍 Calculating Location Centroids...")
    # Group by location name and find the average Lat/Lon for each community
    if 'location_name' in df_model.columns:
        # Filter out bad coordinates (0,0) before averaging
        valid_coords = df_model[(df_model['latitude'] != 0) & (df_model['longitude'] != 0)]
        centroids = valid_coords.groupby('location_name')[['latitude', 'longitude']].mean()
        location_centroids = centroids.to_dict('index')
    
    print(f"✅ Model Loaded! Serving {len(df_model)} listings.")
    print(f"✅ Mapped {len(location_centroids)} unique location centers.")
else:
    print(f"❌ CRITICAL ERROR: {MODEL_FILE} not found.")

# --- 2. RECOMMENDATION ENDPOINT ---
@app.route('/recommend', methods=['POST'])
def recommend():
    if df_model.empty: return jsonify({"status": "error", "message": "Model not loaded."}), 500

    try:
        data = request.get_json()
        
        # Parse basic inputs
        price = float(data.get('price', 0))
        raw_beds = str(data.get('bedrooms', '0'))
        beds_int = int(''.join(filter(str.isdigit, raw_beds))) if any(c.isdigit() for c in raw_beds) else 0
        raw_type = str(data.get('property_type', 'unknown')).lower().strip()
        raw_offer = str(data.get('offering_type', 'unknown')).lower().strip()
        target_offer = '2' if raw_offer in ['rent', 'lease', '2'] else '1'

        # --- A. INITIAL FILTERING ---
        base_pool = df_model[
            (df_model['offering_type'] == target_offer) & 
            (df_model['property_type'] == raw_type)
        ].copy()

        # 1. Region Filter (Dubai Only)
        if not base_pool.empty:
            base_pool = base_pool[
                base_pool['full_location_path'].astype(str).str.lower().str.contains('dubai', na=False)
            ]

        # 2. Bad Data Filter
        if not base_pool.empty:
            base_pool = base_pool[base_pool['size_sqft'] > 150]

        # --- 🔥 B. SMART RADIUS LOCATION FILTER 🔥 ---
        req_loc = data.get('location_filter')
        
        # Default user coordinates (Downtown Dubai)
        search_lat = 25.10
        search_lon = 55.20
        
        if req_loc and req_loc != "All Locations" and req_loc != "Dubai":
            # Check if we know the center of this location
            if req_loc in location_centroids:
                # 1. Get the center of the requested community
                search_lat = location_centroids[req_loc]['latitude']
                search_lon = location_centroids[req_loc]['longitude']
                
                # 2. Calculate distance of ALL listings from this center
                base_pool['dist_to_center'] = calculate_haversine(
                    search_lat, search_lon, 
                    base_pool['latitude'].values, base_pool['longitude'].values
                )
                
                # 3. FILTER: Keep listings within 3 KM radius (This is the "Smart Radius")
                # You can adjust this to 5.0 for wider search, or 2.0 for stricter
                base_pool = base_pool[base_pool['dist_to_center'] <= 3.0]
                
            else:
                # Fallback: If we don't have coords, use text matching
                base_pool = base_pool[
                    base_pool['full_location_path'].astype(str).str.contains(req_loc, case=False, na=False)
                ]

        if base_pool.empty:
            return jsonify({"status": "success", "count": 0, "data": []})

        # --- C. AI MATCHING ---
        input_row = pd.DataFrame([{
            'price': price, 'size_sqft': 0, 'beds_int': beds_int, 'bath_int': 1,
            'property_type': raw_type, 'offering_type': target_offer
        }])
        
        query_vec = preprocessor.transform(input_row)
        subset_matrix = preprocessor.transform(base_pool)
        
        nn_subset = NearestNeighbors(n_neighbors=min(len(base_pool), 20), metric='cosine').fit(subset_matrix)
        dists, indices = nn_subset.kneighbors(query_vec)
        
        recs = base_pool.iloc[indices.flatten()].copy()
        recs['similarity_score'] = 1 - dists.flatten()

        # --- D. SCORING ---
        # Recalculate Geo Score based on the SELECTED location center (not just generic Dubai)
        recs['dist_km'] = calculate_haversine(search_lat, search_lon, recs['latitude'].values, recs['longitude'].values)
        recs['geo_score'] = 1 / (recs['dist_km'] + 1)

        # Cold Start Boost
        global_pop = df_model[df_model['smart_popularity_score'] > 0]['smart_popularity_score']
        pop_med = global_pop.median() if not global_pop.empty else 50
        max_pop = df_model['smart_popularity_score'].max()

        recs['boosted_pop'] = recs.apply(lambda r: pop_med if (r.get('days_old', 999) <= 14 and r.get('smart_popularity_score', 0) == 0) else r.get('smart_popularity_score', 0), axis=1)
        recs['pop_score'] = np.log1p(recs['boosted_pop']) / np.log1p(max_pop) if max_pop > 0 else 0
        
        recs['final_score'] = (recs['similarity_score']*0.4) + (recs['geo_score']*0.3) + (recs['pop_score']*0.3)

        # Return Data
        rich_cols = ['property_listing_id', 'final_score', 'property_title', 'price', 'beds_int', 'bath_int', 'size_sqft', 'location_name', 'full_location_path', 'property_type', 'offering_type', 'furnished_flag', 'completion_status', 'quality_score', 'days_old','view_count', 
            'impression_count', 
            'popularity_score', 
            'smart_popularity_score',
            'super_agent_score']
        valid_cols = [c for c in rich_cols if c in recs.columns]
        
        results = recs.sort_values('final_score', ascending=False).head(5)[valid_cols].where(pd.notnull(recs), None).to_dict(orient='records')
        return jsonify({"status": "success", "count": len(results), "data": results})

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- 4. LOCATIONS ENDPOINT ---
@app.route('/locations', methods=['GET'])
def get_locations():
    if not location_centroids: return jsonify({"locations": []})
    
    # Return the keys (Location Names) that we successfully mapped coordinates for
    mapped_locs = sorted(list(location_centroids.keys()))
    return jsonify({"locations": mapped_locs})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
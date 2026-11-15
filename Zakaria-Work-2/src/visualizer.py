import folium
import pandas as pd
import numpy as np
from typing import Optional
from .distance_provider import ModularDistanceProvider

ROUTE_COLORS = ['#1f77b4', '#2ca02c', '#d62728', '#9467bd', '#ff7f0e', '#8c564b', '#e377c2']

def plot_interactive_routes(
    routes_df: pd.DataFrame,
    candidates_df: pd.DataFrame,
    dist_provider: ModularDistanceProvider,
    output_html_path: str = "route_proposal.html"
) -> folium.Map:
    """
    Renders an interactive Folium map showing the Central Yard, Disposal Depot,
    serviced containers, and the optimized vehicle routes.
    """
    center_lat, center_lon = dist_provider.depot_coord
    disp_lat, disp_lon = dist_provider.disposal_coord
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=13, tiles='OpenStreetMap')

    # 1. Central Yard (Depot) Marker
    folium.Marker(
        [center_lat, center_lon],
        tooltip="Central Yard (Depot - Start/End)",
        icon=folium.Icon(color='black', icon='home', prefix='fa')
    ).add_to(m)

    # 2. Disposal Depot Marker (Entsorgungszentrum)
    folium.Marker(
        [disp_lat, disp_lon],
        tooltip="Disposal & Recycling Depot (Unloading Site)",
        icon=folium.Icon(color='darkred', icon='trash', prefix='fa')
    ).add_to(m)

    if routes_df.empty or candidates_df.empty:
        m.save(output_html_path)
        return m

    # 3. Add Container Stops and Route Lines per Truck
    coords = dist_provider.coords

    for truck_idx, row in routes_df.iterrows():
        truck_color = ROUTE_COLORS[truck_idx % len(ROUTE_COLORS)]
        stop_indices = row['ordered_stop_indices']
        
        # Build path coordinates: Yard -> Stops -> Disposal -> Yard
        route_path = [[center_lat, center_lon]]
        
        for stop_num, idx in enumerate(stop_indices, 1):
            pt = coords[idx]
            route_path.append([float(pt[0]), float(pt[1])])
            
            # Container marker info
            loc_id = str(candidates_df.iloc[idx].get('Location_id', candidates_df.iloc[idx].get('poi_id', f'Bin_{idx}')))
            street = str(candidates_df.iloc[idx].get('street_name', ''))
            street_str = f" - {street}" if street and street != 'nan' else ""
            fill_val = float(candidates_df.iloc[idx].get('predicted_fill_perc', candidates_df.iloc[idx].get('current_fill_perc', 80.0)))
            reason = str(candidates_df.iloc[idx].get('selection_reason', ''))
            reason_str = f"<br><i>Status: {reason}</i>" if reason else ""
            
            folium.CircleMarker(
                location=[float(pt[0]), float(pt[1])],
                radius=7,
                color=truck_color,
                fill=True,
                fill_color=truck_color,
                fill_opacity=0.85,
                tooltip=f"<b>{row['vehicle']} | Stop #{stop_num}</b>: {loc_id[:12]}{street_str}<br>Fill: {fill_val:.1f}%{reason_str}"
            ).add_to(m)

        # Route to Disposal then back to Yard
        route_path.append([disp_lat, disp_lon])
        route_path.append([center_lat, center_lon])

        # Draw route polyline
        folium.PolyLine(
            route_path,
            color=truck_color,
            weight=4,
            opacity=0.8,
            tooltip=f"<b>{row['vehicle']}</b> | {row['num_stops']} stops | {row['total_distance_km']} km | {row['shift_hours']} hrs | {row['total_weight_kg']} kg"
        ).add_to(m)

    m.save(output_html_path)
    return m

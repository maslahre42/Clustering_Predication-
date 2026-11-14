import folium
import pandas as pd
import numpy as np
from typing import Optional
from html import escape
from pathlib import Path
from .distance_provider import ModularDistanceProvider

ROUTE_COLORS = ['#1f77b4', '#2ca02c', '#d62728', '#9467bd', '#ff7f0e']

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
    m = folium.Map(location=[center_lat, center_lon], zoom_start=13, tiles='OpenStreetMap')
    label = ('Synthetic site assignments' if dist_provider.is_synthetic else 'Provided site coordinates')
    notice = f'{label}. Lines are direct connections; distances are haversine × detour, not road navigation.'
    folium.map.Marker([center_lat, center_lon], icon=folium.DivIcon(html=(
        '<div style="width:360px;background:white;padding:8px;border:1px solid #888">'
        + escape(notice) + '</div>'))).add_to(m)
    Path(output_html_path).parent.mkdir(parents=True, exist_ok=True)

    # 1. Central Yard (Depot) Marker
    folium.Marker(
        [center_lat, center_lon],
        tooltip="Central Yard (Depot - Start/End)",
        icon=folium.Icon(color='black', icon='home', prefix='fa')
    ).add_to(m)

    # 2. Disposal Depot Marker (approx 3km east of center)
    disp_lat, disp_lon = dist_provider.disposal_coord
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

    for truck_idx, (_, row) in enumerate(routes_df.iterrows()):
        truck_color = ROUTE_COLORS[truck_idx % len(ROUTE_COLORS)]
        stop_indices = row['ordered_stop_indices']
        
        # Build path coordinates: Yard -> Stops -> Disposal -> Yard
        route_path = [[center_lat, center_lon]]
        
        for stop_num, idx in enumerate(stop_indices, 1):
            pt = coords[idx]
            route_path.append([pt[0], pt[1]])
            
            # Container marker
            loc_id = str(candidates_df.iloc[idx]['Location_id'])
            fill_val = candidates_df.iloc[idx].get('predicted_fill_perc', np.nan)
            
            folium.CircleMarker(
                location=[pt[0], pt[1]],
                radius=7,
                color=truck_color,
                fill=True,
                fill_color=truck_color,
                fill_opacity=0.85,
                tooltip=escape(f"Truck {truck_idx+1} | Stop #{stop_num}: {loc_id[:8]}... (Predicted maximum bin fill: {fill_val:.1f}%)")
            ).add_to(m)

        route_path.append([disp_lat, disp_lon])
        route_path.append([center_lat, center_lon])

        # Draw route polyline
        folium.PolyLine(
            route_path,
            color=truck_color,
            weight=4,
            opacity=0.8,
            tooltip=f"{row['vehicle']} | {row['num_stops']} stops | {row['total_distance_km']} km | {row['shift_hours']} hrs"
        ).add_to(m)

    m.save(output_html_path)
    return m

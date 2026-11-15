import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  type MaterialType,
  type Route,
  type RoutingSolution,
  type SequenceNode,
} from "../lib/api";
import { formatPct, provenanceLabel } from "../lib/format";

/**
 * Route map (plain Leaflet + OpenStreetMap tiles; react-leaflet intentionally
 * not added — M11 dispatch). Per-route polylines, ordered stop markers,
 * depot/disposal icons. Coordinates are SYNTHETIC demo values (§4.2) — the
 * banner and provenance label below keep that explicit.
 */

const ROUTE_COLORS = ["#2563eb", "#dc2626", "#059669", "#d97706", "#7c3aed", "#0891b2"];

const MATERIAL_COLOR: Record<MaterialType, string> = {
  brown: "#78350f",
  green: "#047857",
  white: "#64748b",
};

function stopIcon(index: number, material: MaterialType): L.DivIcon {
  return L.divIcon({
    className: "",
    html:
      `<span style="display:flex;align-items:center;justify-content:center;` +
      `width:22px;height:22px;border-radius:9999px;color:#fff;font:bold 11px sans-serif;` +
      `background:${MATERIAL_COLOR[material] ?? "#334155"};border:2px solid #fff;` +
      `box-shadow:0 0 3px rgba(0,0,0,.5);">${index}</span>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

function facilityIcon(letter: string, background: string): L.DivIcon {
  return L.divIcon({
    className: "",
    html:
      `<span style="display:flex;align-items:center;justify-content:center;` +
      `width:26px;height:26px;border-radius:6px;color:#fff;font:bold 12px sans-serif;` +
      `background:${background};border:2px solid #fff;box-shadow:0 0 3px rgba(0,0,0,.5);">` +
      `${letter}</span>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  });
}

function nodeLabel(node: SequenceNode): string {
  if ("location_id" in node) {
    return `Stop ${node.location_id} · ${node.material_type} · predicted fill ${formatPct(
      node.predicted_fill_pct,
    )} [demo coordinates]`;
  }
  if ("service_minutes" in node) {
    return `Disposal site ${node.id} (${node.name}) [demo location]`;
  }
  return `Depot ${node.id} (${node.name}) [demo location]`;
}

function routeLayer(route: Route, color: string): L.Layer[] {
  const layers: L.Layer[] = [];
  const latlngs = route.sequence
    .filter((n) => typeof n.lat === "number" && typeof n.lon === "number")
    .map((n) => [n.lat, n.lon] as [number, number]);
  if (latlngs.length >= 2) {
    layers.push(
      L.polyline(latlngs, { color, weight: 4, opacity: 0.8 }).bindTooltip(
        `${route.vehicle_type_id}: ${route.distance_m.toLocaleString("en-US")} m · ${route.duration_minutes} min`,
      ),
    );
  }
  let stopIndex = 0;
  route.sequence.forEach((node) => {
    if ("location_id" in node) {
      stopIndex += 1;
      layers.push(
        L.marker([node.lat, node.lon], { icon: stopIcon(stopIndex, node.material_type) }).bindPopup(
          `#${stopIndex} — ${nodeLabel(node)}`,
        ),
      );
    } else if ("service_minutes" in node) {
      layers.push(
        L.marker([node.lat, node.lon], { icon: facilityIcon("♻", "#047857") }).bindPopup(nodeLabel(node)),
      );
    } else {
      layers.push(
        L.marker([node.lat, node.lon], { icon: facilityIcon("D", "#1d4ed8") }).bindPopup(nodeLabel(node)),
      );
    }
  });
  return layers;
}

export function RouteMap({ solution }: { solution: RoutingSolution }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    // jsdom / hidden containers have zero size — skip init (real browsers have layout).
    if (el === null || el.clientWidth === 0 || el.clientHeight === 0) return;
    const map = L.map(el);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (map === null) return;
    const allLayers = solution.routes.flatMap((route, i) => routeLayer(route, ROUTE_COLORS[i % ROUTE_COLORS.length]));
    const group = L.featureGroup(allLayers).addTo(map);
    const bounds = group.getBounds();
    if (bounds.isValid()) map.fitBounds(bounds.pad(0.15));
    return () => {
      group.remove();
    };
  }, [solution]);

  return (
    <div>
      <div
        ref={containerRef}
        className="h-96 w-full rounded border border-slate-300"
        data-testid="route-map"
      />
      <p className="mt-1 text-xs text-slate-500">
        {provenanceLabel(solution.distance_provenance)} · marker numbers = visit order · D = depot,
        ♻ = disposal site · all marker coordinates are synthetic demo values.
      </p>
    </div>
  );
}

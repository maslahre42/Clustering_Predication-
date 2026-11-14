namespace GarbageCollector.Api.Features.Proposal;

public static class UnservedReason
{
    /// <summary>The site alone is heavier or larger than one truck load. It is reported, never cut down.</summary>
    public const string ExceedsTruckCapacity = "exceeds_truck_capacity";
    /// <summary>Even an empty truck cannot visit this stop, unload and return within one shift.</summary>
    public const string ExceedsShift = "exceeds_shift";
    /// <summary>All available trucks are full for the day.</summary>
    public const string FleetLimit = "fleet_limit";
    /// <summary>Optional stop: no truck that drives anyway had spare time.</summary>
    public const string OptionalNotScheduled = "optional_not_scheduled";
    /// <summary>Coordinates are used for driving time, and this site has none.</summary>
    public const string MissingCoordinates = "missing_coordinates";
}

public sealed record Trip(IReadOnlyList<string> Stops, double WeightKg, double VolumeL);
public sealed record TruckRoute(int Truck, IReadOnlyList<Trip> Trips, double Hours, double? DistanceKm, int Bins);
public sealed record UnservedStop(string LocationId, bool Mandatory, string Reason);
/// <summary><see cref="LoadsByCapacity"/> is collected weight and volume divided by one load. It is not a number of trucks.</summary>
public sealed record RouteTotals(int Trucks, int Trips, int Stops, int Bins, double Hours, double? DistanceKm,
    double WeightT, double VolumeM3, int LoadsByCapacity);
public sealed record RoutePlan(IReadOnlyList<TruckRoute> Routes, IReadOnlyList<UnservedStop> Unserved, RouteTotals Totals);

/// <summary>
/// Builds truck routes for one day. A truck leaves the yard, collects stops, drives to the unloading site when the next
/// stop would exceed its weight or volume limit, continues, and ends with a last unload and the drive home, all inside
/// one shift. Mandatory stops are scheduled first and open as many trucks as needed (up to the fleet size). Optional
/// stops only fill spare time of trucks that drive anyway. This is a constructive heuristic: it gives a feasible plan
/// with few trucks, not a proven optimum.
/// </summary>
public static class RoutePlanner
{
    private const double Epsilon = 1e-9;

    public static RoutePlan Plan(IReadOnlyList<SiteStop> stops, OperationsSettings settings)
    {
        var useCoordinates = settings.FixedTravelMin <= 0;
        var unserved = new List<UnservedStop>();
        var candidates = new List<SiteStop>();
        foreach (var stop in stops)
        {
            if (stop.WeightKg > settings.TruckPayloadKg + Epsilon || stop.VolumeL > settings.TruckVolumeL)
                unserved.Add(new(stop.LocationId, stop.Mandatory, UnservedReason.ExceedsTruckCapacity));
            else if (useCoordinates && (stop.Latitude is null || stop.Longitude is null))
                unserved.Add(new(stop.LocationId, stop.Mandatory, UnservedReason.MissingCoordinates));
            else if (Minutes(Place.Depot, new(stop), settings) + Service(stop, settings) + Closing(new(stop), settings) > settings.ShiftHours * 60 + Epsilon)
                unserved.Add(new(stop.LocationId, stop.Mandatory, UnservedReason.ExceedsShift));
            else candidates.Add(stop);
        }

        var mandatory = candidates.Where(stop => stop.Mandatory)
            .OrderByDescending(stop => stop.Risk).ThenBy(stop => stop.LocationId, StringComparer.Ordinal).ToList();
        var optional = candidates.Where(stop => !stop.Mandatory)
            .OrderByDescending(stop => stop.Risk).ThenBy(stop => stop.LocationId, StringComparer.Ordinal).ToList();

        var trucks = new List<Truck>();
        while (mandatory.Count > 0 && trucks.Count < settings.MaxVehicles)
        {
            var truck = new Truck(settings);
            while (truck.TakeNearest(mandatory)) { }
            trucks.Add(truck);
        }
        unserved.AddRange(mandatory.Select(stop => new UnservedStop(stop.LocationId, true, UnservedReason.FleetLimit)));
        foreach (var truck in trucks) while (truck.TakeNearest(optional, byRisk: true)) { }
        unserved.AddRange(optional.Select(stop => new UnservedStop(stop.LocationId, false, UnservedReason.OptionalNotScheduled)));

        var routes = trucks.Select((truck, index) => truck.Finish(index + 1, useCoordinates)).ToArray();
        var weight = routes.Sum(route => route.Trips.Sum(trip => trip.WeightKg));
        var volume = routes.Sum(route => route.Trips.Sum(trip => trip.VolumeL));
        var loads = routes.Length == 0 ? 0 : Math.Max(1, Math.Max(
            (int)Math.Ceiling(weight / settings.TruckPayloadKg - Epsilon),
            double.IsInfinity(settings.TruckVolumeL) ? 0 : (int)Math.Ceiling(volume / settings.TruckVolumeL - Epsilon)));
        var totals = new RouteTotals(routes.Length, routes.Sum(route => route.Trips.Count),
            routes.Sum(route => route.Trips.Sum(trip => trip.Stops.Count)), routes.Sum(route => route.Bins), routes.Sum(route => route.Hours),
            useCoordinates ? routes.Sum(route => route.DistanceKm ?? 0) : null, weight / 1000, volume / 1000, loads);
        return new(routes, unserved.OrderBy(stop => stop.LocationId, StringComparer.Ordinal).ToArray(), totals);
    }

    /// <summary>Straight-line (haversine) distance times the detour factor. Not a road distance.</summary>
    public static double RoadKm(double latitude1, double longitude1, double latitude2, double longitude2, OperationsSettings settings)
    {
        const double earthRadiusKm = 6371.0088;
        static double Radians(double degrees) => degrees * Math.PI / 180;
        var a = Math.Pow(Math.Sin(Radians(latitude2 - latitude1) / 2), 2) +
            Math.Cos(Radians(latitude1)) * Math.Cos(Radians(latitude2)) * Math.Pow(Math.Sin(Radians(longitude2 - longitude1) / 2), 2);
        return 2 * earthRadiusKm * Math.Asin(Math.Min(1, Math.Sqrt(a))) * settings.DetourFactor;
    }

    private readonly record struct Place(string Id, double? Latitude, double? Longitude)
    {
        public static readonly Place Depot = new("\u0001depot", null, null);
        public static readonly Place Disposal = new("\u0001disposal", null, null);
        public Place(SiteStop stop) : this(stop.LocationId, stop.Latitude, stop.Longitude) { }
        public (double Latitude, double Longitude) At(OperationsSettings settings) =>
            Id == Depot.Id ? (settings.DepotLatitude, settings.DepotLongitude)
            : Id == Disposal.Id ? (settings.DisposalLatitude, settings.DisposalLongitude)
            : (Latitude ?? 0, Longitude ?? 0);
    }

    private static double Km(Place from, Place to, OperationsSettings settings)
    {
        var (a, b) = (from.At(settings), to.At(settings));
        return RoadKm(a.Latitude, a.Longitude, b.Latitude, b.Longitude, settings);
    }
    private static double Minutes(Place from, Place to, OperationsSettings settings) =>
        from.Id == to.Id ? 0
        : settings.FixedTravelMin > 0 ? settings.FixedTravelMin
        : Km(from, to, settings) / settings.AvgSpeedKph * 60;
    private static double Service(SiteStop stop, OperationsSettings settings) =>
        settings.ServiceMinPerStop + settings.ServiceMinPerBin * stop.Bins;
    /// <summary>Last leg of every route: drive to the unloading site, unload, drive to the yard.</summary>
    private static double Closing(Place from, OperationsSettings settings) =>
        Minutes(from, Place.Disposal, settings) + settings.UnloadMin + Minutes(Place.Disposal, Place.Depot, settings);

    private sealed class Truck(OperationsSettings settings)
    {
        private readonly List<List<SiteStop>> trips = [[]];
        private Place position = Place.Depot;
        private double minutes, km, weight, volume;

        /// <summary>Adds the best next stop that still fits the shift and removes it from <paramref name="pool"/>.</summary>
        public bool TakeNearest(List<SiteStop> pool, bool byRisk = false)
        {
            var best = -1; double bestCost = double.MaxValue;
            for (var i = 0; i < pool.Count; i++)
            {
                var (cost, _) = Reach(pool[i]);
                if (minutes + cost + Closing(new(pool[i]), settings) > settings.ShiftHours * 60 + Epsilon) continue;
                if (byRisk) { best = i; break; }               // pool is ordered by risk
                if (cost < bestCost - Epsilon) { best = i; bestCost = cost; }
            }
            if (best < 0) return false;
            var stop = pool[best];
            var (time, unloadFirst) = Reach(stop);
            if (unloadFirst)
            {
                km += Km(position, Place.Disposal, settings) + Km(Place.Disposal, new(stop), settings);
                trips.Add([]); weight = 0; volume = 0;
            }
            else km += Km(position, new(stop), settings);
            minutes += time; weight += stop.WeightKg; volume += stop.VolumeL;
            trips[^1].Add(stop); position = new(stop);
            pool.RemoveAt(best);
            return true;
        }

        /// <summary>Minutes to drive to the stop and serve it, unloading on the way if the load would not fit.</summary>
        private (double Minutes, bool UnloadFirst) Reach(SiteStop stop)
        {
            var fits = weight + stop.WeightKg <= settings.TruckPayloadKg + Epsilon && volume + stop.VolumeL <= settings.TruckVolumeL;
            var drive = fits ? RoutePlanner.Minutes(position, new(stop), settings)
                : RoutePlanner.Minutes(position, Place.Disposal, settings) + settings.UnloadMin + RoutePlanner.Minutes(Place.Disposal, new(stop), settings);
            return (drive + Service(stop, settings), !fits);
        }

        public TruckRoute Finish(int number, bool reportDistance)
        {
            var hours = (minutes + Closing(position, settings)) / 60;
            var distance = km + Km(position, Place.Disposal, settings) + Km(Place.Disposal, Place.Depot, settings);
            return new(number,
                trips.Where(trip => trip.Count > 0).Select(trip => new Trip(trip.Select(stop => stop.LocationId).ToArray(),
                    trip.Sum(stop => stop.WeightKg), trip.Sum(stop => stop.VolumeL))).ToArray(),
                hours, reportDistance ? distance : null, trips.Sum(trip => trip.Sum(stop => stop.Bins)));
        }
    }
}

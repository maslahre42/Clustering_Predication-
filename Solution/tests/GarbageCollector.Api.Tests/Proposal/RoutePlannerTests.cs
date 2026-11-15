using GarbageCollector.Api.Features.Proposal;
using static GarbageCollector.Api.Tests.ProposalFixtures;
namespace GarbageCollector.Api.Tests;

public class RoutePlannerTests
{
    // PreZero rules: 10 min every drive, 5 min per container, 15 min unloading, 8 h shift, 12 t per load.
    private static readonly OperationsSettings Fixed = OperationsSettings.Default;
    private static SiteStop[] Light(int count, bool mandatory = true, string prefix = "S") =>
        Enumerable.Range(0, count).Select(i => Stop($"{prefix}{i:00}", 100, mandatory: mandatory)).ToArray();

    [Fact]
    public void NothingToCollectNeedsNoTruck()
    {
        var plan = RoutePlanner.Plan([], Fixed);
        Assert.Empty(plan.Routes);
        Assert.Empty(plan.Unserved);
        Assert.Equal(0, plan.Totals.Trucks);
        Assert.Equal(0, plan.Totals.Hours);
    }

    [Fact]
    public void LimitedFleetPreservesHigherMandatoryRiskEvenWhenItNeedsMoreService()
    {
        var settings = Fixed with { MaxVehicles = 1, ShiftHours = 1 };
        var high = Stop("HIGH", 1050, bins: 3, risk: 0.99);
        var low = Stop("LOW", 350, bins: 1, risk: 0.71);
        var plan = RoutePlanner.Plan([high, low], settings);
        Assert.Equal("HIGH", Assert.Single(Assert.Single(plan.Routes).Trips).Stops.Single());
        Assert.Equal("LOW", Assert.Single(plan.Unserved).LocationId);
    }

    [Fact]
    public void OneContainerTakesDriveServiceFinalUnloadAndReturn()
    {
        var plan = RoutePlanner.Plan([Stop("A", 800)], Fixed);
        var route = Assert.Single(plan.Routes);
        Assert.Equal(1, route.Truck);
        Assert.Equal(50.0 / 60, route.Hours, 9); // 10 + 5 + 10 + 15 + 10 minutes
        Assert.Null(route.DistanceKm);            // fixed driving time: no distance is invented
        var trip = Assert.Single(route.Trips);
        Assert.Equal(new[] { "A" }, trip.Stops.ToArray());
        Assert.Equal(800, trip.WeightKg, 6);
        Assert.Equal(1, plan.Totals.Trucks);
        Assert.Equal(0.8, plan.Totals.WeightT, 9);
    }

    [Fact]
    public void ContainersAtOneSiteShareTheDrive()
    {
        var route = Assert.Single(RoutePlanner.Plan([Stop("A", 2400, bins: 3)], Fixed).Routes);
        Assert.Equal(60.0 / 60, route.Hours, 9); // 10 + 3×5 + 10 + 15 + 10
        Assert.Equal(3, route.Bins);
    }

    [Fact]
    public void ExtraTimePerStopIsConfigurable()
    {
        var route = Assert.Single(RoutePlanner.Plan([Stop("A", 800)], Fixed with { ServiceMinPerStop = 4, UnloadMin = 20 }).Routes);
        Assert.Equal(59.0 / 60, route.Hours, 9);
    }

    [Fact]
    public void AFullTruckUnloadsAndContinues()
    {
        var plan = RoutePlanner.Plan([Stop("A", 1500), Stop("B", 1500), Stop("C", 1500)], Fixed with { TruckPayloadT = 2 });
        var route = Assert.Single(plan.Routes);
        Assert.Equal(3, route.Trips.Count);
        Assert.All(route.Trips, trip => Assert.InRange(trip.WeightKg, 0, 2000));
        Assert.Equal(130.0 / 60, route.Hours, 9); // 3×(10+5) + 2×(10+15) + 10+15+10
        Assert.Equal(3, plan.Totals.Trips);
        Assert.Equal(3, plan.Totals.LoadsByCapacity);
        Assert.Equal(1, plan.Totals.Trucks); // three loads, but one truck: loads are not trucks
    }

    [Fact]
    public void TruckVolumeBindsOnlyWhenItIsKnown()
    {
        SiteStop[] stops = [Stop("A", 100, liters: 3000), Stop("B", 100, liters: 3000)];
        Assert.Single(Assert.Single(RoutePlanner.Plan(stops, Fixed).Routes).Trips);
        var limited = Assert.Single(RoutePlanner.Plan(stops, Fixed with { TruckVolumeM3 = 4 }).Routes);
        Assert.Equal(2, limited.Trips.Count);
        Assert.All(limited.Trips, trip => Assert.InRange(trip.VolumeL, 0, 4000));
    }

    [Fact]
    public void ASiteBiggerThanOneLoadIsReportedNotCutDown()
    {
        var plan = RoutePlanner.Plan([Stop("BIG", 15000), Stop("OK", 500)], Fixed);
        var unserved = Assert.Single(plan.Unserved);
        Assert.Equal("BIG", unserved.LocationId);
        Assert.Equal(UnservedReason.ExceedsTruckCapacity, unserved.Reason);
        Assert.True(unserved.Mandatory);
        Assert.Equal(0.5, plan.Totals.WeightT, 9); // the 15 t are not silently counted as 12 t
        Assert.Equal(1, plan.Totals.Stops);
    }

    [Fact]
    public void AFullShiftOpensTheNextTruck()
    {
        // 15 minutes per stop, 35 minutes to finish: 29 stops fit in 480 minutes.
        var plan = RoutePlanner.Plan(Light(40), Fixed);
        Assert.Equal(2, plan.Routes.Count);
        Assert.Equal(29, plan.Routes[0].Trips.Sum(t => t.Stops.Count));
        Assert.Equal(11, plan.Routes[1].Trips.Sum(t => t.Stops.Count));
        Assert.All(plan.Routes, route => Assert.InRange(route.Hours, 0, 8));
        Assert.Empty(plan.Unserved);
        Assert.Equal(2, plan.Totals.Trucks);
        Assert.Equal(40, plan.Totals.Stops);
    }

    [Fact]
    public void ALongerShiftNeedsFewerTrucks() =>
        Assert.Equal(1, RoutePlanner.Plan(Light(40), Fixed with { ShiftHours = 11 }).Totals.Trucks);

    [Fact]
    public void TooFewTrucksLeavesMandatoryStopsVisiblyUnserved()
    {
        var plan = RoutePlanner.Plan(Light(40), Fixed with { MaxVehicles = 1 });
        Assert.Single(plan.Routes);
        Assert.Equal(11, plan.Unserved.Count);
        Assert.All(plan.Unserved, u => { Assert.True(u.Mandatory); Assert.Equal(UnservedReason.FleetLimit, u.Reason); });
        Assert.Equal(29, plan.Totals.Stops);
    }

    [Fact]
    public void AStopThatCannotFitAnyShiftIsExplained()
    {
        var plan = RoutePlanner.Plan([Stop("A", 100), Stop("B", 100)], Fixed with { ShiftHours = 0.5 });
        Assert.Empty(plan.Routes);
        Assert.Equal(2, plan.Unserved.Count);
        Assert.All(plan.Unserved, u => Assert.Equal(UnservedReason.ExceedsShift, u.Reason));
    }

    [Fact]
    public void OptionalStopsUseSpareTimeOfTrucksThatDriveAnyway()
    {
        var plan = RoutePlanner.Plan([Stop("M", 100), Stop("O1", 100, mandatory: false, risk: 0.5), Stop("O2", 100, mandatory: false, risk: 0.45)], Fixed);
        Assert.Equal(1, plan.Totals.Trucks);
        Assert.Equal(3, plan.Totals.Stops);
        Assert.Equal("M", plan.Routes[0].Trips[0].Stops[0]); // urgent first
        Assert.Empty(plan.Unserved);
    }

    [Fact]
    public void OptionalStopsAloneNeverSendATruck()
    {
        var plan = RoutePlanner.Plan(Light(3, mandatory: false), Fixed);
        Assert.Empty(plan.Routes);
        Assert.Equal(3, plan.Unserved.Count);
        Assert.All(plan.Unserved, u => { Assert.False(u.Mandatory); Assert.Equal(UnservedReason.OptionalNotScheduled, u.Reason); });
    }

    [Fact]
    public void OptionalStopsNeverOpenAnExtraTruckAndHigherRiskGoesFirst()
    {
        SiteStop[] stops = [.. Light(28), Stop("LOW", 100, mandatory: false, risk: 0.45), Stop("HIGH", 100, mandatory: false, risk: 0.65)];
        var plan = RoutePlanner.Plan(stops, Fixed);
        Assert.Equal(1, plan.Totals.Trucks);
        Assert.Equal(29, plan.Totals.Stops);
        Assert.Contains("HIGH", plan.Routes[0].Trips.SelectMany(t => t.Stops));
        Assert.Equal("LOW", Assert.Single(plan.Unserved).LocationId);
    }

    [Fact]
    public void WithCoordinatesTheNearestStopComesFirstAndDistanceIsReported()
    {
        var settings = Fixed with { FixedTravelMin = 0 };
        SiteStop[] stops = [Stop("FAR", 100, latitude: 49.20, longitude: 9.2185), Stop("NEAR", 100, latitude: 49.15, longitude: 9.2185)];
        var route = Assert.Single(RoutePlanner.Plan(stops, settings).Routes);
        Assert.Equal(new[] { "NEAR", "FAR" }, route.Trips[0].Stops.ToArray());
        Assert.NotNull(route.DistanceKm);
        Assert.True(route.DistanceKm > 10);
        Assert.Equal(route.DistanceKm!.Value / settings.AvgSpeedKph + (5 + 5 + 15) / 60.0, route.Hours, 9);
    }

    [Fact]
    public void StraightLineDistanceUsesTheDetourFactor()
    {
        var oneDegreeLatitude = RoutePlanner.RoadKm(49, 9, 50, 9, Fixed with { DetourFactor = 1.0 });
        Assert.InRange(oneDegreeLatitude, 111.0, 111.4);
        Assert.Equal(oneDegreeLatitude * 1.3, RoutePlanner.RoadKm(49, 9, 50, 9, Fixed), 9);
        Assert.Equal(0, RoutePlanner.RoadKm(49, 9, 49, 9, Fixed));
    }

    [Fact]
    public void MissingCoordinatesOnlyMatterWhenCoordinatesAreUsed()
    {
        SiteStop[] stops = [Stop("NOWHERE", 100, latitude: null, longitude: null)];
        Assert.Empty(RoutePlanner.Plan(stops, Fixed).Unserved);
        var unserved = Assert.Single(RoutePlanner.Plan(stops, Fixed with { FixedTravelMin = 0 }).Unserved);
        Assert.Equal(UnservedReason.MissingCoordinates, unserved.Reason);
    }

    [Fact]
    public void EveryStopIsServedOnceOrExplainedAndNoLimitIsBroken()
    {
        var seed = 12345u;
        double Next() { seed = seed * 1664525u + 1013904223u; return (seed >> 8) / (double)(1 << 24); }
        var stops = Enumerable.Range(0, 150).Select(i => Stop($"S{i:000}", 300 + 2900 * Next(), bins: 1 + (int)(3 * Next()),
            mandatory: Next() < 0.6, risk: Next(), latitude: 49.10 + 0.1 * Next(), longitude: 9.15 + 0.15 * Next())).ToArray();
        foreach (var settings in new[] { Fixed, Fixed with { TruckPayloadT = 5, MaxVehicles = 4 }, Fixed with { FixedTravelMin = 0, TruckVolumeM3 = 20 } })
        {
            var plan = RoutePlanner.Plan(stops, settings);
            var served = plan.Routes.SelectMany(r => r.Trips).SelectMany(t => t.Stops).ToArray();
            Assert.Equal(served.Length, served.Distinct().Count());
            Assert.Equal(stops.Select(s => s.LocationId).Order().ToArray(), served.Concat(plan.Unserved.Select(u => u.LocationId)).Order().ToArray());
            Assert.All(plan.Routes, route => Assert.InRange(route.Hours, 0, settings.ShiftHours + 1e-9));
            Assert.All(plan.Routes.SelectMany(r => r.Trips), trip => {
                Assert.InRange(trip.WeightKg, 0, settings.TruckPayloadKg + 1e-6);
                Assert.InRange(trip.VolumeL, 0, settings.TruckVolumeL);
                Assert.NotEmpty(trip.Stops);
            });
            Assert.InRange(plan.Routes.Count, 1, settings.MaxVehicles);
            Assert.Equal(served.Length, plan.Totals.Stops);
            Assert.Equal(plan.Routes.Sum(r => r.Hours), plan.Totals.Hours, 9);
            Assert.Equal(stops.Where(s => served.Contains(s.LocationId)).Sum(s => s.WeightKg) / 1000, plan.Totals.WeightT, 6);
            Assert.Equal(stops.Where(s => served.Contains(s.LocationId)).Sum(s => s.Bins), plan.Totals.Bins);
            Assert.Equal(Signature(plan), Signature(RoutePlanner.Plan(stops, settings))); // deterministic
        }
    }
}

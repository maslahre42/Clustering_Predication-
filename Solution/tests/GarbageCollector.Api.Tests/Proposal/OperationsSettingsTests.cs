using GarbageCollector.Api.Features.Proposal;
namespace GarbageCollector.Api.Tests;

public class OperationsSettingsTests
{
    [Fact]
    public void CompartmentsRequireAnExplicitCompleteLayoutAndFitTheTruck()
    {
        Assert.Equal(0, OperationsSettings.Default.BrownCompartmentM3);
        Assert.Equal(0, OperationsSettings.Default.CostPerKmEuro);
        Assert.NotEmpty((OperationsSettings.Default with { BrownCompartmentM3 = 2 }).Validate());
        var settings = new ProposalRequest { BrownCompartmentM3 = 2, GreenCompartmentM3 = 3, WhiteCompartmentM3 = 4, CostPerKmEuro = 1.2, FixedTruckCostEuro = 150 }.ToSettings();
        Assert.Empty(settings.Validate());
        Assert.Equal(3, settings.GreenCompartmentM3);
        Assert.Equal(4, settings.WhiteCompartmentM3);
        Assert.Equal(1.2, settings.CostPerKmEuro);
        Assert.Equal(150, settings.FixedTruckCostEuro);
        Assert.NotEmpty((settings with { TruckVolumeM3 = 8 }).Validate());
        Assert.NotEmpty((settings with { WhiteCompartmentM3 = .0001 }).Validate());
        Assert.NotEmpty((settings with { CostPerKmEuro = double.NaN }).Validate());
        Assert.NotEmpty((settings with { FixedTruckCostEuro = -1 }).Validate());
    }

    [Fact]
    public void PublicStreetRoutingHasNoFixedTimeOrAerialCostParameters()
    {
        var json = System.Text.Json.JsonSerializer.Serialize(OperationsSettings.Default);
        foreach (var name in new[] { "FixedTravelMin", "AvgSpeedKph", "DetourFactor", "VehicleFixedCostMin" })
        {
            Assert.DoesNotContain(name, json);
            Assert.Null(typeof(ProposalRequest).GetProperty(name));
        }
        Assert.Equal(0, OperationsSettings.Default.OptionalValueMin);
    }
    [Fact]
    public void DefaultsAreTheNumbersPreZeroGave()
    {
        var settings = OperationsSettings.Default;
        Assert.Equal(3.0, settings.ContainerVolumeM3);
        Assert.Equal(12.0, settings.TruckPayloadT);
        Assert.Equal(0.0, settings.TruckVolumeM3); // unknown: only the weight limit counts
        Assert.Equal(8.0, settings.ShiftHours);
        Assert.Equal(10.0, settings.FixedTravelMin);
        Assert.Equal(5.0, settings.ServiceMinPerBin);
        Assert.False(settings.WorkSaturday);
        Assert.False(settings.WorkSunday);
        Assert.Empty(settings.Validate());
    }

    [Fact]
    public void CapacitiesAreDerivedInOneUnitSystem()
    {
        var settings = OperationsSettings.Default with { TruckVolumeM3 = 18 };
        Assert.Equal(12000, settings.TruckPayloadKg);
        Assert.Equal(18000, settings.TruckVolumeL);
        Assert.True(double.IsPositiveInfinity(OperationsSettings.Default.TruckVolumeL));
        Assert.Equal(1050, OperationsSettings.Default.FullContainerKg); // 3 m³ × 350 kg/m³
    }

    [Theory]
    [InlineData("ContainerVolumeM3", 0)] [InlineData("ContainerVolumeM3", -1)]
    [InlineData("GlassDensityKgM3", 0)] [InlineData("TruckPayloadT", 0)] [InlineData("TruckVolumeM3", -1)]
    [InlineData("MaxVehicles", 0)] [InlineData("ShiftHours", 0)] [InlineData("ShiftHours", 25)]
    [InlineData("FixedTravelMin", -1)] [InlineData("AvgSpeedKph", 0)] [InlineData("DetourFactor", 0.5)]
    [InlineData("ServiceMinPerBin", -1)] [InlineData("ServiceMinPerStop", -1)] [InlineData("UnloadMin", -1)]
    [InlineData("LookaheadDays", 0)] [InlineData("MustProbability", 1.5)] [InlineData("MustProbability", -0.1)]
    [InlineData("NeighbourProbability", 2)] [InlineData("NeighbourFillPercent", 101)] [InlineData("OptionalProbability", -1)]
    [InlineData("DepotLatitude", 91)] [InlineData("DisposalLongitude", 181)]
    public void InvalidValuesAreNamedInsteadOfSilentlyClipped(string field, double value)
    {
        var settings = OperationsSettings.Default.With(field, value);
        var error = Assert.Single(settings.Validate());
        Assert.Contains(field, error);
    }

    [Fact]
    public void NotANumberIsRejected() =>
        Assert.Contains("TruckPayloadT", Assert.Single(OperationsSettings.Default.With("TruckPayloadT", double.NaN).Validate()));

    [Fact]
    public void UnknownFieldCannotBeSet() =>
        Assert.Throws<ArgumentException>(() => OperationsSettings.Default.With("Nope", 1));

    [Fact]
    public void RequestKeepsDefaultsForMissingValuesAndOverridesTheRest()
    {
        var settings = new ProposalRequest { TruckPayloadT = 8, MaxVehicles = 3, WorkSaturday = true }.ToSettings();
        Assert.Equal(8, settings.TruckPayloadT);
        Assert.Equal(3, settings.MaxVehicles);
        Assert.True(settings.WorkSaturday);
        Assert.Equal(OperationsSettings.Default.ShiftHours, settings.ShiftHours);
        Assert.Equal(OperationsSettings.Default, new ProposalRequest().ToSettings());
    }
}

public class CollectionCalendarTests
{
    private static DateOnly D(string value) => DateOnly.ParseExact(value, "yyyy-MM-dd");

    [Theory]
    [InlineData("2026-08-14", "2026-08-17")] // Friday -> Monday
    [InlineData("2026-08-15", "2026-08-17")] // Saturday -> Monday
    [InlineData("2026-08-17", "2026-08-18")] // Monday -> Tuesday
    public void NextCollectionDaySkipsTheWeekend(string after, string expected) =>
        Assert.Equal(D(expected), CollectionCalendar.NextWorkingDay(D(after), OperationsSettings.Default));

    [Fact]
    public void SaturdayCollectionCanBeSwitchedOn() =>
        Assert.Equal(D("2026-08-15"), CollectionCalendar.NextWorkingDay(D("2026-08-14"), OperationsSettings.Default with { WorkSaturday = true }));

    [Theory]
    [InlineData("2026-08-14", 1, "2026-08-17")] // a Friday plan must cover the weekend
    [InlineData("2026-08-17", 1, "2026-08-18")]
    [InlineData("2026-08-17", 2, "2026-08-19")]
    [InlineData("2026-08-20", 3, "2026-08-25")]
    public void WindowEndsOnTheNthNextCollectionDay(string plan, int lookahead, string expected) =>
        Assert.Equal(D(expected), CollectionCalendar.WindowEnd(D(plan), OperationsSettings.Default with { LookaheadDays = lookahead }));
}

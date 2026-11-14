using GarbageCollector.Api.Features.Proposal;
namespace GarbageCollector.Api.Tests;

public class SimulationRulesTests
{
    [Theory]
    [InlineData("2026-08-17", "2026-08-01", "2026-08-17", 7, true)]
    [InlineData("2026-08-17", "2026-07-18", "2026-08-17", 0, true)]
    [InlineData("2026-08-17", "2026-08-01", "2026-08-18", 7, false)]
    [InlineData("2026-08-17", "2026-07-17", "2026-08-17", 7, false)]
    [InlineData("2026-08-17", "2026-08-05", "2026-08-01", 7, false)]
    [InlineData("invalid", "2026-08-01", "2026-08-17", 7, false)]
    [InlineData("2026-08-17", "2026-08-01", "2026-08-17", -1, false)]
    public void WindowsRespectHistoricalCutoffAndWorkLimits(string asOf, string start, string end, int seed, bool valid) =>
        Assert.Equal(valid, SimulationRules.Validate(asOf, start, end, seed) is null);

    [Fact]
    public void PythonOperatingOverridesAreBoundAndValidated()
    {
        var settings = new ProposalRequest { VehicleFixedCostMin = 600, OptionalValueMin = 25, SolverTimeLimitSeconds = 2 }.ToSettings();
        Assert.Equal(600, settings.VehicleFixedCostMin);
        Assert.Equal(25, settings.OptionalValueMin);
        Assert.Equal(2, settings.SolverTimeLimitSeconds);
        Assert.Empty(settings.Validate());
        Assert.NotEmpty((settings with { SolverTimeLimitSeconds = 0 }).Validate());
    }

    [Fact]
    public void ServiceCalendarCannotBeEmpty()
    {
        var settings = OperationsSettings.Default with { WorkMonday = false, WorkTuesday = false, WorkWednesday = false, WorkThursday = false, WorkFriday = false };
        Assert.Contains(settings.Validate(), message => message.Contains("at least one"));
    }
}

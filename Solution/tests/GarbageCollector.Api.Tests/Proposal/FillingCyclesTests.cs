using GarbageCollector.Api.Domain.Collections;
using GarbageCollector.Api.Features.Proposal;
using static GarbageCollector.Api.Tests.ProposalFixtures;
namespace GarbageCollector.Api.Tests;

public class FillingCyclesTests
{
    [Fact]
    public void FirstReadingCreatesNoCycleButRecordsTheEmptying()
    {
        var bin = Assert.Single(Histories([Row("A", "white", "2026-01-01", "80")]));
        Assert.Empty(bin.Cycles);
        Assert.Equal("2026-01-01", bin.LastEmptied);
        Assert.Equal("A:white", bin.Key);
    }

    [Fact]
    public void RateIsThePreEmptyingFillOverTheDaysSinceThePreviousVisit()
    {
        // 100 then 40 is not a "drop of 60": the bin was emptied on 1 January and refilled to 40% in ten days.
        var bin = Assert.Single(Histories([Row("A", "white", "2026-01-01", "100"), Row("A", "white", "2026-01-11", "40")]));
        var cycle = Assert.Single(bin.Cycles);
        Assert.Equal("2026-01-11", cycle.End);
        Assert.Equal(10, cycle.GapDays);
        Assert.Equal(40, cycle.Fill);
        Assert.False(cycle.Censored);
        Assert.Equal(Math.Log(4), cycle.LogRate, 12);
        Assert.Equal("2026-01-11", bin.LastEmptied);
    }

    [Theory]
    [InlineData("100")] [InlineData("overfull")] [InlineData(" OverFull ")]
    public void FullAndOverfullAreLowerBoundsNeverAnInventedPercentage(string raw)
    {
        var bin = Assert.Single(Histories([Row("A", "white", "2026-01-01", "50"), Row("A", "white", "2026-01-21", raw)]));
        var cycle = Assert.Single(bin.Cycles);
        Assert.True(cycle.Censored);
        Assert.Equal(100, cycle.Fill);
        Assert.Equal(20, cycle.GapDays);
    }

    [Fact]
    public void UnknownReadingStillEmptiesTheBinButGivesNoRate()
    {
        var bin = Assert.Single(Histories([
            Row("A", "green", "2026-01-01", "50"), Row("A", "green", "2026-01-11", "unknown"), Row("A", "green", "2026-01-21", "30")]));
        var cycle = Assert.Single(bin.Cycles);
        Assert.Equal(10, cycle.GapDays); // measured from the unknown visit, not from 1 January
        Assert.Equal(30, cycle.Fill);
        Assert.Equal("2026-01-21", bin.LastEmptied);
    }

    [Fact]
    public void UnknownLatestReadingIsStillTheLastEmptying()
    {
        var bin = Assert.Single(Histories([Row("A", "green", "2026-01-01", "50"), Row("A", "green", "2026-01-11", "")]));
        Assert.Empty(bin.Cycles);
        Assert.Equal("2026-01-11", bin.LastEmptied);
    }

    [Fact]
    public void EmptyReadingUsesASmallFloorSoTheRateStaysFinite()
    {
        var bin = Assert.Single(Histories([Row("A", "brown", "2026-01-01", "50"), Row("A", "brown", "2026-01-06", "0")]));
        var cycle = Assert.Single(bin.Cycles);
        Assert.Equal(FillingCycles.MinimumFill, cycle.Fill);
        Assert.False(double.IsInfinity(cycle.LogRate));
    }

    [Fact]
    public void CutoffIsInclusiveAndLaterVisitsAreInvisible()
    {
        Observation[] rows = [
            Row("A", "white", "2026-01-01", "50"), Row("A", "white", "2026-02-01", "60"),
            Row("A", "white", "2026-03-01", "70"), Row("B", "white", "2026-03-01", "70")];
        var bin = Assert.Single(Histories(rows, "2026-02-01"));
        Assert.Equal("A", bin.LocationId);
        Assert.Equal("2026-02-01", bin.LastEmptied);
        Assert.Single(bin.Cycles);
        Assert.Empty(Histories(rows, "2025-12-31"));
    }

    [Fact]
    public void BinsAreLocationPlusMaterialInAStableOrder()
    {
        var bins = Histories([
            Row("B", "white", "2026-01-01", "10"), Row("A", "white", "2026-01-01", "10"),
            Row("A", "brown", "2026-01-01", "10"), Row("A", "white", "2026-01-08", "70")]);
        Assert.Equal(new[] { "A:brown", "A:white", "B:white" }, bins.Select(b => b.Key).ToArray());
        Assert.Single(bins[1].Cycles);
        Assert.Empty(bins[0].Cycles);
    }

    [Fact]
    public void SameDayDuplicateIsOneVisitAndTheLastRowWins()
    {
        var bin = Assert.Single(Histories([
            Row("A", "white", "2026-01-01", "50"), Row("A", "white", "2026-01-11", "20"), Row("A", "white", "2026-01-11", "60")]));
        var cycle = Assert.Single(bin.Cycles);
        Assert.Equal(60, cycle.Fill);
        Assert.Equal(10, cycle.GapDays);
    }

    [Fact]
    public void SourceRowsAreNotReorderedOrChanged()
    {
        Observation[] rows = [Row("B", "white", "2026-02-01", "overfull"), Row("A", "white", "2026-01-01", "10")];
        Histories(rows);
        Assert.Equal("B", rows[0].LocationId);
        Assert.Equal("overfull", rows[0].FillLevel);
    }
}

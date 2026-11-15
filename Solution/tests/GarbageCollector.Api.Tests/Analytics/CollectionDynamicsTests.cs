using System.Text.Json;
using GarbageCollector.Api.Domain.Collections;
using GarbageCollector.Api.Features.Analytics;
namespace GarbageCollector.Api.Tests;

public class CollectionDynamicsTests
{
    private static Observation Row(string id, string material, string date, string fill) => new() { LocationId=id, Material=material, Date=date, FillLevel=fill };

    [Fact]
    public void RecordedCollectionsDifferFromCyclesAndQuantilesUseResetRates()
    {
        Observation[] rows = [Row("A","brown","2026-01-01","90"), Row("A","brown","2026-01-11","20"),
            Row("A","brown","2026-01-31","40"), Row("A","brown","2026-03-02","60")];
        var brown=CollectionDynamics.Create(rows,"2026-03-02").Single(row => row.Material=="brown");
        Assert.Equal(4,brown.Collections); Assert.Equal(3,brown.Intervals); Assert.Equal(1,brown.Bins);
        Assert.Equal(15,brown.Cadence!.Q1); Assert.Equal(20,brown.Cadence.Median); Assert.Equal(25,brown.Cadence.Q3);
        Assert.Equal(2,brown.Rates!.Median); Assert.Equal(50,brown.FillingTimes!.Median);
        Assert.Equal(3,brown.Cadence.Buckets.Sum(bucket => bucket.Count));
        Assert.Equal(0,brown.FillingCurve.Single(point => point.Days==49).Share);
        Assert.Equal(1,brown.FillingCurve.Single(point => point.Days==50).Share);
        Assert.Equal(4,Assert.Single(brown.FastestBins).Collections);
    }

    [Fact]
    public void UnknownResetsZerosAndBoundsAreDistinctAndMaterialsDoNotMix()
    {
        Observation[] rows = [Row("A","brown","2026-01-01","90"), Row("A","brown","2026-01-11","20"),
            Row("A","brown","2026-01-16","unknown"), Row("A","brown","2026-01-21","30"),
            Row("A","brown","2026-01-26","0"), Row("A","brown","2026-01-31","100"),
            Row("A","brown","2026-02-05","overfull"), Row("A","green","2026-01-01","30")];
        var result=CollectionDynamics.Create(rows,"2026-02-05");var brown=result.Single(row => row.Material=="brown");
        Assert.Equal(7,brown.Collections); Assert.Equal(6,brown.Intervals); Assert.Equal(3,brown.NumericCycles);
        Assert.Equal(2,brown.LowerBoundCycles); Assert.Equal(1,brown.UnknownCycles); Assert.Equal(1,brown.ZeroFillCycles);
        Assert.Equal(2,brown.Rates!.Median); Assert.Equal(0,brown.Rates.Minimum);
        Assert.Equal(2,brown.FillingTimes!.Count); Assert.Empty(brown.FastestBins);
        Assert.Equal(1,result.Single(row => row.Material=="green").Collections);
        Assert.Null(result.Single(row => row.Material=="green").Rates);
    }

    [Fact]
    public void FutureRowsAreExcludedDuplicatesDoNotInventVisitsAndLongTimesStayInDenominator()
    {
        Observation[] before=[Row("A","white","2026-01-01","20"),Row("A","white","2026-01-11","1")];
        var first=CollectionDynamics.Create(before,"2026-01-11");
        var later=CollectionDynamics.Create([..before,before[1],Row("A","white","2027-01-01","overfull")],"2026-01-11");
        Assert.Equal(JsonSerializer.Serialize(first),JsonSerializer.Serialize(later));
        var white=first.Single(row=>row.Material=="white");
        Assert.Equal(1000,white.FillingTimes!.Median); Assert.Equal(0,white.FillingCurve[^1].Share);
        Assert.Equal(1,white.FillingTimes.Count); Assert.Equal(91,white.FillingCurve.Length);
        Assert.All(CollectionDynamics.Create([],"2026-01-01"),row=> { Assert.Null(row.Cadence); Assert.Empty(row.FastestBins); });
    }

    [Fact]
    public void HistogramRetainsOutliersInAnExplicitTailAndZeroRatesStayFinite()
    {
        var start = new DateOnly(2026,1,1);
        var rows = Enumerable.Range(0,40).Select(i=>Row("A","brown",start.AddDays(i*10).ToString("yyyy-MM-dd"),"20")).ToList();
        rows.Add(Row("A","brown",start.AddDays(391).ToString("yyyy-MM-dd"),"90"));
        var rates = CollectionDynamics.Create(rows,"2028-01-01")[0].Rates!;
        Assert.Equal(40,rates.Count); Assert.Equal(40,rates.Buckets.Sum(bin=>bin.Count));
        var tail = rates.Buckets[^1]; Assert.True(tail.IsTail); Assert.Equal(2,tail.Lower); Assert.Equal(90,tail.Upper); Assert.Equal(1,tail.Count);
        var zero = CollectionDynamics.Create([Row("Z","brown","2026-01-01","10"),Row("Z","brown","2026-01-02","0")],"2026-01-02")[0];
        Assert.Equal(0,zero.Rates!.Median); Assert.Equal(1,zero.Rates.Buckets.Sum(bin=>bin.Count)); Assert.Null(zero.FillingTimes);
    }

    [Fact]
    public void RankingsRequireThreePositiveCyclesAndAreBoundedAndDeterministic()
    {
        var rows=Enumerable.Range(0,12).SelectMany(i=>Enumerable.Range(1,4).Select(day=>Row($"A{i:00}","brown",$"2026-01-{day:00}","20"))).ToArray();
        var brown=CollectionDynamics.Create(rows.Reverse(),"2026-01-04")[0];
        Assert.Equal(10,brown.FastestBins.Length); Assert.Equal("A00",brown.FastestBins[0].LocationId); Assert.Equal("A09",brown.FastestBins[^1].LocationId);
        Assert.Equal("A00",brown.SlowestBins[0].LocationId);
        Assert.All(brown.Rates!.Buckets,bucket=>Assert.True(bucket.Count>=0));
    }
}

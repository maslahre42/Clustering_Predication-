namespace GarbageCollector.Api.Features.History;

/// <summary>Manual fill values require domain parsing; unknown is always last.</summary>
public static class HistoryFillOrdering
{
    public static IOrderedEnumerable<HistoryItem> Apply(IEnumerable<HistoryItem> items, bool ascending)
    {
        var knownFirst = items.OrderBy(x => !x.IsOverfull && x.FillLevelPercent is null);
        var ordered = ascending
            ? knownFirst.ThenBy(x => x.IsOverfull).ThenBy(x => x.FillLevelPercent)
            : knownFirst.ThenByDescending(x => x.IsOverfull).ThenByDescending(x => x.FillLevelPercent);
        return ordered.ThenByDescending(x => x.Date)
            .ThenBy(x => x.LocationId, StringComparer.Ordinal)
            .ThenBy(x => x.Material, StringComparer.Ordinal);
    }
}

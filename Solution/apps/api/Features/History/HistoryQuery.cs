using GarbageCollector.Api.Domain.Collections;
using GarbageCollector.Api.Infrastructure.Persistence;

namespace GarbageCollector.Api.Features.History;

/// <summary>SQL-translatable filtering and ordering, applied before pagination.</summary>
internal static class HistoryQuery
{
    public static IQueryable<Observation> ApplyFilters(this IQueryable<Observation> query, HistoryFilter filter)
    {
        if (filter.LocationId is not null)
            query = query.Where(x => x.LocationId == filter.LocationId);
        if (!string.IsNullOrWhiteSpace(filter.LocationSearch))
            query = query.Where(x => x.LocationId.Contains(filter.LocationSearch.Trim()));
        if (filter.Material is not null)
            query = query.Where(x => x.Material == filter.Material);
        if (filter.From is not null)
            query = query.Where(x => x.Date.CompareTo(filter.From) >= 0);
        if (filter.To is not null)
            query = query.Where(x => x.Date.CompareTo(filter.To) <= 0);
        if (filter.AsOf is not null)
            query = query.Through(HistoricalCutoff.Parse(filter.AsOf));
        return query;
    }

    public static IOrderedQueryable<Observation> ApplyOrdering(this IQueryable<Observation> query, HistoryFilter filter)
    {
        var ordered = (filter.SortBy, filter.SortDirection == "asc") switch
        {
            ("location", true) => query.OrderBy(x => x.LocationId),
            ("location", false) => query.OrderByDescending(x => x.LocationId),
            ("material", true) => query.OrderBy(x => x.Material),
            ("material", false) => query.OrderByDescending(x => x.Material),
            (_, true) => query.OrderBy(x => x.Date),
            _ => query.OrderByDescending(x => x.Date),
        };
        return ordered.ThenByDescending(x => x.Date).ThenBy(x => x.LocationId).ThenBy(x => x.Material);
    }
}

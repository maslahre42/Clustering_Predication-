using GarbageCollector.Api.Domain.Collections;
namespace GarbageCollector.Api.Infrastructure.Persistence;

public static class ObservationQueries
{
    // Keep the expression SQL-translatable. Domain snapshot builders also check the boundary.
    public static IQueryable<Observation> Through(this IQueryable<Observation> query, HistoricalCutoff cutoff) =>
        query.Where(row => row.Date.CompareTo(cutoff.Value) <= 0);
}

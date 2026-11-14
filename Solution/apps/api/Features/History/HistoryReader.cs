using GarbageCollector.Api.Domain.Collections;
using GarbageCollector.Api.Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;

namespace GarbageCollector.Api.Features.History;

public static class HistoryReader
{
    public static async Task<HistoryPage> ReadAsync(HistoryDbContext db, HistoryFilter filter, CancellationToken ct = default)
    {
        if (!HistoryRules.IsValidSort(filter.SortBy, filter.SortDirection) ||
            !HistoryRules.IsValidQuery(filter.Material, filter.From, filter.To, filter.Page, filter.PageSize) ||
            !HistoryRules.IsValidQuery(null, filter.AsOf, null, null, null))
            throw new ArgumentException("Invalid history filters.", nameof(filter));

        var query = db.Observations.AsNoTracking().ApplyFilters(filter);
        var total = await query.CountAsync(ct);
        var size = filter.PageSize ?? 50;
        var offset = HistoryRules.Offset(filter.Page, filter.PageSize);
        HistoryItem[] items;

        if (filter.SortBy == "fill")
        {
            // Keep manual-value parsing consistent with display. Normalize the database
            // before moving this sort into SQL if the dataset grows substantially.
            var rows = await query.ToArrayAsync(ct);
            items = HistoryFillOrdering.Apply(rows.Select(ToItem), filter.SortDirection == "asc")
                .Skip(offset).Take(size).ToArray();
        }
        else
        {
            var rows = await query.ApplyOrdering(filter).Skip(offset).Take(size).ToArrayAsync(ct);
            items = rows.Select(ToItem).ToArray();
        }

        return new(total, filter.Page ?? 1, size, items);
    }

    private static HistoryItem ToItem(Observation x) =>
        new(x.LocationId, x.Material, x.Date, RecordedFill.ParsePercentage(x.FillLevel), RecordedFill.IsOverfull(x.FillLevel));
}

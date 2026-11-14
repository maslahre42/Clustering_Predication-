namespace GarbageCollector.Api.Features.History;

public sealed record HistoryFilter(string? LocationId = null, string? Material = null,
    string? From = null, string? To = null, string? AsOf = null, int? Page = null, int? PageSize = null,
    string? SortBy = null, string? SortDirection = null, string? LocationSearch = null);
public sealed record HistoryItem(string LocationId, string Material, string Date, double? FillLevelPercent, bool IsOverfull = false);
public sealed record HistoryPage(int Total, int Page, int PageSize, HistoryItem[] Items);


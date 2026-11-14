using GarbageCollector.Api.Domain.Collections;
namespace GarbageCollector.Api.Features.History;

public static class HistoryRules
{
    public static bool IsValidQuery(string? material, string? from, string? to, int? page, int? pageSize) =>
        (material is null or "brown" or "green" or "white") &&
        IsDate(from) && IsDate(to) &&
        (from is null || to is null || string.CompareOrdinal(from, to) <= 0) &&
        (page is null or >= 1) && (pageSize is null or >= 1 and <= 200);

    public static bool IsValidSort(string? field, string? direction) =>
        (field is null or "date" or "location" or "material" or "fill") &&
        (direction is null or "asc" or "desc");

    public static int Offset(int? page, int? pageSize) =>
        (int)Math.Min((long)((page ?? 1) - 1) * (pageSize ?? 50), int.MaxValue);

    private static bool IsDate(string? value) => value is null || HistoricalCutoff.IsValid(value);
}

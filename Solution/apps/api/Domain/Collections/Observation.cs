namespace GarbageCollector.Api.Domain.Collections;

public sealed class Observation
{
    public string LocationId { get; set; } = "";
    public string Material { get; set; } = "";
    public string Date { get; set; } = "";
    public string FillLevel { get; set; } = "";
}

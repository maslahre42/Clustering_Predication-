namespace GarbageCollector.Api.Domain.Locations;

public sealed class BinLocation
{
    public string LocationId { get; set; } = "";
    public double Latitude { get; set; }
    public double Longitude { get; set; }
    public bool IsSynthetic { get; set; }
}

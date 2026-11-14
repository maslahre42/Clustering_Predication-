using System.Reflection;
using System.Text.Json.Serialization;
namespace GarbageCollector.Api.Features.Proposal;

/// <summary>
/// Every operating number of the proposal. Values PreZero gave on 14 November 2026: 3 m³ containers, 12 t per load,
/// 8 h shift, 10 minutes per drive, 5 minutes per container, Monday to Friday. Everything else is an assumption.
/// </summary>
public sealed record OperationsSettings
{
    public static OperationsSettings Default { get; } = new();

    // Waste stream and containers
    public double ContainerVolumeM3 { get; init; } = 3.0;
    public double GlassDensityKgM3 { get; init; } = 350;
    // Fleet. Truck volume 0 = unknown, so only the weight limit applies.
    public double TruckPayloadT { get; init; } = 12.0;
    public double TruckVolumeM3 { get; init; }
    public int MaxVehicles { get; init; } = 12;
    // Shift and driving. Fixed travel 0 = use coordinates (straight line × detour factor).
    public double ShiftHours { get; init; } = 8.0;
    public double FixedTravelMin { get; init; } = 10.0;
    public double AvgSpeedKph { get; init; } = 25.0;
    public double DetourFactor { get; init; } = 1.3;
    public double ServiceMinPerBin { get; init; } = 5.0;
    public double ServiceMinPerStop { get; init; }
    public double UnloadMin { get; init; } = 15.0;
    public bool WorkSaturday { get; init; }
    public bool WorkSunday { get; init; }
    public bool WorkMonday { get; init; } = true;
    public bool WorkTuesday { get; init; } = true;
    public bool WorkWednesday { get; init; } = true;
    public bool WorkThursday { get; init; } = true;
    public bool WorkFriday { get; init; } = true;
    // Yard and unloading site (placeholders near Heilbronn)
    public double DepotLatitude { get; init; } = 49.1427;
    public double DepotLongitude { get; init; } = 9.2185;
    public double DisposalLatitude { get; init; } = 49.1650;
    public double DisposalLongitude { get; init; } = 9.2350;
    // Selection rules
    public int LookaheadDays { get; init; } = 1;
    public double MustProbability { get; init; } = 0.70;
    public double NeighbourProbability { get; init; } = 0.12;
    public double NeighbourFillPercent { get; init; } = 40.0;
    public double OptionalProbability { get; init; } = 0.40;
    public double VehicleFixedCostMin { get; init; } = 480;
    public double OptionalValueMin { get; init; } = 15;
    public int SolverTimeLimitSeconds { get; init; } = 3;

    [JsonIgnore] public double TruckPayloadKg => TruckPayloadT * 1000;
    [JsonIgnore] public double TruckVolumeL => TruckVolumeM3 > 0 ? TruckVolumeM3 * 1000 : double.PositiveInfinity;
    [JsonIgnore] public double ContainerVolumeL => ContainerVolumeM3 * 1000;
    [JsonIgnore] public double FullContainerKg => ContainerVolumeM3 * GlassDensityKgM3;
    public bool IsWorkingDay(DateOnly day) => day.DayOfWeek switch
    {
        DayOfWeek.Saturday => WorkSaturday,
        DayOfWeek.Sunday => WorkSunday,
        DayOfWeek.Monday => WorkMonday,
        DayOfWeek.Tuesday => WorkTuesday,
        DayOfWeek.Wednesday => WorkWednesday,
        DayOfWeek.Thursday => WorkThursday,
        DayOfWeek.Friday => WorkFriday,
        _ => false,
    };

    private static readonly (string Name, double Min, double Max, bool MinExclusive)[] Ranges =
    [
        (nameof(ContainerVolumeM3), 0, 100, true), (nameof(GlassDensityKgM3), 0, 5000, true),
        (nameof(TruckPayloadT), 0, 100, true), (nameof(TruckVolumeM3), 0, 500, false),
        (nameof(MaxVehicles), 1, 200, false), (nameof(ShiftHours), 0, 24, true),
        (nameof(FixedTravelMin), 0, 600, false), (nameof(AvgSpeedKph), 0, 150, true), (nameof(DetourFactor), 1, 5, false),
        (nameof(ServiceMinPerBin), 0, 240, false), (nameof(ServiceMinPerStop), 0, 240, false), (nameof(UnloadMin), 0, 600, false),
        (nameof(DepotLatitude), -90, 90, false), (nameof(DepotLongitude), -180, 180, false),
        (nameof(DisposalLatitude), -90, 90, false), (nameof(DisposalLongitude), -180, 180, false),
        (nameof(LookaheadDays), 1, 14, false), (nameof(MustProbability), 0, 1, false),
        (nameof(NeighbourProbability), 0, 1, false), (nameof(NeighbourFillPercent), 0, 100, false),
        (nameof(OptionalProbability), 0, 1, false),
        (nameof(VehicleFixedCostMin), 0, 2000, false), (nameof(OptionalValueMin), 0, 600, false),
        (nameof(SolverTimeLimitSeconds), 1, 30, false),
    ];

    /// <summary>One message per invalid value, naming the field. Nothing is clipped silently.</summary>
    public IReadOnlyList<string> Validate()
    {
        var errors = new List<string>();
        foreach (var (name, min, max, exclusive) in Ranges)
        {
            var value = Convert.ToDouble(Property(name).GetValue(this));
            var ok = double.IsFinite(value) && value <= max && (exclusive ? value > min : value >= min);
            if (!ok) errors.Add($"{name} must be {(exclusive ? "greater than" : "at least")} {min} and at most {max}.");
        }
        if (TruckPayloadKg > 0 && TruckPayloadKg < 1) errors.Add("TruckPayloadT must allow at least one kilogram for integer routing loads.");
        if (TruckVolumeM3 > 0 && TruckVolumeL < 1) errors.Add("TruckVolumeM3 must allow at least one litre, or use zero for unknown volume.");
        if (!(WorkMonday || WorkTuesday || WorkWednesday || WorkThursday || WorkFriday || WorkSaturday || WorkSunday)) errors.Add("Choose at least one working collection day.");
        return errors;
    }

    /// <summary>Copy with one numeric value replaced, addressed by property name.</summary>
    public OperationsSettings With(string field, double value)
    {
        if (!Ranges.Any(range => range.Name == field)) throw new ArgumentException($"Unknown setting '{field}'.", nameof(field));
        var property = Property(field);
        var copy = this with { };
        object boxed = value;
        if (property.PropertyType == typeof(int))
            boxed = double.IsFinite(value) ? (int)Math.Round(Math.Clamp(value, int.MinValue, int.MaxValue)) : int.MinValue;
        property.SetValue(copy, boxed);
        return copy;
    }

    private static PropertyInfo Property(string name) => typeof(OperationsSettings).GetProperty(name)!;
}

/// <summary>Optional overrides sent with a request. A missing value keeps the default.</summary>
public sealed class ProposalRequest
{
    public double? ContainerVolumeM3 { get; set; }
    public double? GlassDensityKgM3 { get; set; }
    public double? TruckPayloadT { get; set; }
    public double? TruckVolumeM3 { get; set; }
    public int? MaxVehicles { get; set; }
    public double? ShiftHours { get; set; }
    public double? FixedTravelMin { get; set; }
    public double? AvgSpeedKph { get; set; }
    public double? DetourFactor { get; set; }
    public double? ServiceMinPerBin { get; set; }
    public double? ServiceMinPerStop { get; set; }
    public double? UnloadMin { get; set; }
    public bool? WorkSaturday { get; set; }
    public bool? WorkSunday { get; set; }
    public bool? WorkMonday { get; set; }
    public bool? WorkTuesday { get; set; }
    public bool? WorkWednesday { get; set; }
    public bool? WorkThursday { get; set; }
    public bool? WorkFriday { get; set; }
    public double? DepotLatitude { get; set; }
    public double? DepotLongitude { get; set; }
    public double? DisposalLatitude { get; set; }
    public double? DisposalLongitude { get; set; }
    public int? LookaheadDays { get; set; }
    public double? MustProbability { get; set; }
    public double? NeighbourProbability { get; set; }
    public double? NeighbourFillPercent { get; set; }
    public double? OptionalProbability { get; set; }
    public double? VehicleFixedCostMin { get; set; }
    public double? OptionalValueMin { get; set; }
    public int? SolverTimeLimitSeconds { get; set; }

    public OperationsSettings ToSettings()
    {
        var d = OperationsSettings.Default;
        return new OperationsSettings
        {
            ContainerVolumeM3 = ContainerVolumeM3 ?? d.ContainerVolumeM3, GlassDensityKgM3 = GlassDensityKgM3 ?? d.GlassDensityKgM3,
            TruckPayloadT = TruckPayloadT ?? d.TruckPayloadT, TruckVolumeM3 = TruckVolumeM3 ?? d.TruckVolumeM3,
            MaxVehicles = MaxVehicles ?? d.MaxVehicles, ShiftHours = ShiftHours ?? d.ShiftHours,
            FixedTravelMin = FixedTravelMin ?? d.FixedTravelMin, AvgSpeedKph = AvgSpeedKph ?? d.AvgSpeedKph,
            DetourFactor = DetourFactor ?? d.DetourFactor, ServiceMinPerBin = ServiceMinPerBin ?? d.ServiceMinPerBin,
            ServiceMinPerStop = ServiceMinPerStop ?? d.ServiceMinPerStop, UnloadMin = UnloadMin ?? d.UnloadMin,
            WorkSaturday = WorkSaturday ?? d.WorkSaturday, WorkSunday = WorkSunday ?? d.WorkSunday,
            WorkMonday = WorkMonday ?? d.WorkMonday, WorkTuesday = WorkTuesday ?? d.WorkTuesday,
            WorkWednesday = WorkWednesday ?? d.WorkWednesday, WorkThursday = WorkThursday ?? d.WorkThursday,
            WorkFriday = WorkFriday ?? d.WorkFriday,
            DepotLatitude = DepotLatitude ?? d.DepotLatitude, DepotLongitude = DepotLongitude ?? d.DepotLongitude,
            DisposalLatitude = DisposalLatitude ?? d.DisposalLatitude, DisposalLongitude = DisposalLongitude ?? d.DisposalLongitude,
            LookaheadDays = LookaheadDays ?? d.LookaheadDays, MustProbability = MustProbability ?? d.MustProbability,
            NeighbourProbability = NeighbourProbability ?? d.NeighbourProbability,
            NeighbourFillPercent = NeighbourFillPercent ?? d.NeighbourFillPercent,
            OptionalProbability = OptionalProbability ?? d.OptionalProbability,
            VehicleFixedCostMin = VehicleFixedCostMin ?? d.VehicleFixedCostMin,
            OptionalValueMin = OptionalValueMin ?? d.OptionalValueMin,
            SolverTimeLimitSeconds = SolverTimeLimitSeconds ?? d.SolverTimeLimitSeconds,
        };
    }
}

public static class CollectionCalendar
{
    /// <summary>The first collection day strictly after <paramref name="after"/>.</summary>
    public static DateOnly NextWorkingDay(DateOnly after, OperationsSettings settings)
    {
        var day = after.AddDays(1);
        while (!settings.IsWorkingDay(day)) day = day.AddDays(1);
        return day;
    }

    /// <summary>The N-th collection day after the plan date. A Friday plan with look-ahead 1 runs to Monday.</summary>
    public static DateOnly WindowEnd(DateOnly planDate, OperationsSettings settings)
    {
        var day = planDate;
        for (var left = Math.Max(settings.LookaheadDays, 1); left > 0; left--) day = NextWorkingDay(day, settings);
        return day;
    }
}

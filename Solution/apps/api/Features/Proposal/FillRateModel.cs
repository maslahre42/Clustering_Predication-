namespace GarbageCollector.Api.Features.Proposal;

public sealed record FillForecast(double ExpectedFillPercent, double OverflowProbability);

public static class NormalDistribution
{
    public static double Pdf(double z) => Math.Exp(-0.5 * z * z) / Math.Sqrt(2 * Math.PI);

    /// <summary>Standard normal distribution function (complementary error function, relative error below 1.2e-7).</summary>
    public static double Cdf(double z)
    {
        var x = Math.Abs(z) / Math.Sqrt(2);
        var t = 1 / (1 + 0.5 * x);
        var erfc = t * Math.Exp(-x * x - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418 + t * (-0.18628806 +
            t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (-0.82215223 + t * 0.17087277)))))))));
        return z >= 0 ? 1 - 0.5 * erfc : 0.5 * erfc;
    }

    /// <summary>E[Z | Z &gt; a] − a ≥ 0 written as the inverse Mills ratio, stable for large a.</summary>
    public static double Hazard(double a) => a > 8 ? a + 1 / a : Pdf(a) / Math.Max(1 - Cdf(a), 1e-300);
}

/// <summary>
/// Daily fill rate per bin: log-normal, with each bin's level pulled towards the average of its glass type
/// (bins with few visits borrow strength). Full and overfull visits count as "at least this fast".
/// Fitted by expectation-maximisation; deterministic, no random numbers, no external solver.
/// </summary>
public sealed class FillRateModel
{
    private const int Iterations = 60;
    private readonly Dictionary<string, (double Mean, double Variance)> bins = new(StringComparer.Ordinal);
    private readonly Dictionary<string, double> materials = new(StringComparer.Ordinal);
    private double overall = double.NaN;

    /// <summary>Spread of one filling cycle around its bin's level (log scale).</summary>
    public double Sigma { get; private set; } = 0.6;
    /// <summary>Spread of bins around their glass type (log scale).</summary>
    public double Tau { get; private set; } = 0.8;
    public int CycleCount { get; private set; }
    public int CensoredCycleCount { get; private set; }
    /// <summary>Typical (median) fill rate per glass type, percentage points per day.</summary>
    public IReadOnlyDictionary<string, double> MaterialRatePercentPerDay =>
        materials.OrderBy(pair => pair.Key, StringComparer.Ordinal).ToDictionary(pair => pair.Key, pair => Math.Exp(pair.Value));

    public static FillRateModel Fit(IReadOnlyCollection<BinHistory> histories)
    {
        var model = new FillRateModel();
        var data = histories.Where(bin => bin.Cycles.Count > 0)
            .OrderBy(bin => bin.Key, StringComparer.Ordinal)
            .Select(bin => (bin.Key, bin.Material, X: bin.Cycles.Select(c => c.LogRate).ToArray(), C: bin.Cycles.Select(c => c.Censored).ToArray()))
            .ToArray();
        model.CycleCount = data.Sum(bin => bin.X.Length);
        model.CensoredCycleCount = data.Sum(bin => bin.C.Count(c => c));
        if (data.Length == 0) return model;

        double sigma = model.Sigma, tau = model.Tau;
        var level = data.Select(bin => bin.X.Average()).ToArray();
        var variance = new double[data.Length];
        var byMaterial = data.Select((bin, index) => (bin.Material, index)).GroupBy(x => x.Material, StringComparer.Ordinal)
            .ToDictionary(g => g.Key, g => g.Select(x => x.index).ToArray(), StringComparer.Ordinal);
        var materialMean = byMaterial.ToDictionary(g => g.Key, g => g.Value.Average(i => level[i]), StringComparer.Ordinal);

        for (var iteration = 0; iteration < Iterations; iteration++)
        {
            double within = 0, between = 0;
            for (var b = 0; b < data.Length; b++)
            {
                var (x, c) = (data[b].X, data[b].C);
                double sum = 0, squares = 0;
                for (var i = 0; i < x.Length; i++)
                {
                    var z = x[i]; var extra = 0.0;
                    if (c[i])
                    {   // expected value and variance of the true log rate given "at least x"
                        var a = (x[i] - level[b]) / sigma;
                        var hazard = NormalDistribution.Hazard(a);
                        z = level[b] + sigma * hazard;
                        extra = sigma * sigma * Math.Max(0, 1 + a * hazard - hazard * hazard);
                    }
                    sum += z; squares += (z - level[b]) * (z - level[b]) + extra;
                }
                var prior = materialMean[data[b].Material];
                var precision = x.Length / (sigma * sigma) + 1 / (tau * tau);
                var updated = (sum / (sigma * sigma) + prior / (tau * tau)) / precision;
                variance[b] = 1 / precision;
                within += squares + x.Length * variance[b];
                between += (updated - prior) * (updated - prior) + variance[b];
                level[b] = updated;
            }
            foreach (var (material, members) in byMaterial) materialMean[material] = members.Average(i => level[i]);
            sigma = Math.Clamp(Math.Sqrt(within / model.CycleCount), 0.3, 1.2);
            tau = Math.Clamp(Math.Sqrt(between / data.Length), 0.15, 1.2);
        }

        model.Sigma = sigma; model.Tau = tau;
        for (var b = 0; b < data.Length; b++) model.bins[data[b].Key] = (level[b], variance[b]);
        foreach (var (material, mean) in materialMean) model.materials[material] = mean;
        model.overall = level.Average();
        return model;
    }

    /// <summary>
    /// Forecast <paramref name="days"/> after the last emptying. Returns null when there is no history at all.
    /// <see cref="FillForecast.OverflowProbability"/> is the chance of having reached <paramref name="threshold"/> percent.
    /// </summary>
    public FillForecast? Predict(string locationId, string material, double days, double threshold = 100)
    {
        if (double.IsNaN(overall)) return null;
        if (days <= 0) return new(0, 0);
        var (mean, variance) = bins.TryGetValue($"{locationId}:{material}", out var known) ? known
            : (materials.TryGetValue(material, out var typical) ? typical : overall, Tau * Tau);
        var spread = Math.Sqrt(Sigma * Sigma + variance);
        var toFull = (Math.Log(100 / days) - mean) / spread;
        // E[min(100, rate × days)] for a log-normal rate
        var expected = days * Math.Exp(mean + spread * spread / 2) * NormalDistribution.Cdf(toFull - spread)
            + 100 * (1 - NormalDistribution.Cdf(toFull));
        var reached = 1 - NormalDistribution.Cdf((Math.Log(threshold / days) - mean) / spread);
        return new(Math.Clamp(expected, 0, 100), Math.Clamp(reached, 0, 1));
    }
}

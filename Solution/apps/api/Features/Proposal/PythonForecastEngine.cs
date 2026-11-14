using System.Diagnostics;
using System.Text.Json;
using GarbageCollector.Api.Domain.Collections;
using GarbageCollector.Api.Domain.Locations;

namespace GarbageCollector.Api.Features.Proposal;

/// <summary>Request-local JSON/stdin bridge to Omar's original Python package.</summary>
public interface IForecastEngine
{
    Task<JsonElement> RunAsync(string action, string asOf, OperationsSettings settings,
        IReadOnlyCollection<Observation> observations, IReadOnlyCollection<BinLocation> locations,
        string? locationId = null, string? material = null, int horizonDays = 60,
        string? start = null, string? end = null, int seed = 7, CancellationToken cancellationToken = default, string? csv = null);
}

public sealed class PythonForecastEngine(IConfiguration configuration, IHostEnvironment environment) : IForecastEngine
{
    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);

    public async Task<JsonElement> RunAsync(string action, string asOf, OperationsSettings settings,
        IReadOnlyCollection<Observation> observations, IReadOnlyCollection<BinLocation> locations,
        string? locationId = null, string? material = null, int horizonDays = 60,
        string? start = null, string? end = null, int seed = 7, CancellationToken cancellationToken = default, string? csv = null)
    {
        var python = configuration["Forecast:Python"] ?? Path.GetFullPath("../../.venv/bin/python", environment.ContentRootPath);
        var script = Path.GetFullPath(configuration["Forecast:Script"] ?? "../../forecast_service/worker.py", environment.ContentRootPath);
        if (!File.Exists(python) || !File.Exists(script))
            throw new InvalidOperationException("Omar's Python engine is not configured. Run make setup-python in Solution, or set Forecast__Python to the Python environment containing forecast_service/requirements.txt.");
        var info = new ProcessStartInfo(python)
        {
            RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true,
            UseShellExecute = false, CreateNoWindow = true,
        };
        info.ArgumentList.Add(script);
        using var process = Process.Start(info) ?? throw new InvalidOperationException("Cannot start Omar's Python engine.");
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromMinutes(4));
        var output = process.StandardOutput.ReadToEndAsync(timeout.Token);
        var errors = process.StandardError.ReadToEndAsync(timeout.Token);
        try
        {
            var payload = new { action, asOf, settings, observations, locations, locationId, material, horizonDays, start, end, seed, csv };
            await process.StandardInput.WriteAsync(JsonSerializer.Serialize(payload, Json).AsMemory(), timeout.Token);
            process.StandardInput.Close();
            await process.WaitForExitAsync(timeout.Token);
            var text = await output;
            var stderr = await errors;
            if (process.ExitCode != 0)
            {
                var message = "Python engine failed. Check forecast_service dependencies and server logs. " + stderr[..Math.Min(stderr.Length, 300)];
                try
                {
                    using var failure = JsonDocument.Parse(text);
                    if (failure.RootElement.TryGetProperty("validation", out var validation))
                        throw new DatasetRejectedException(validation.Clone());
                    if (failure.RootElement.TryGetProperty("error", out var error)) message = error.GetString() ?? message;
                }
                catch (JsonException) { /* Missing dependency errors can occur before the JSON adapter starts. */ }
                throw new InvalidOperationException(message);
            }
            using var document = JsonDocument.Parse(text);
            return document.RootElement.Clone();
        }
        catch (OperationCanceledException)
        {
            if (!process.HasExited) process.Kill(entireProcessTree: true);
            cancellationToken.ThrowIfCancellationRequested();
            throw new InvalidOperationException("The forecast/simulation exceeded four minutes. Try a shorter simulation window or solver time limit.");
        }
    }
}

public sealed class DatasetRejectedException(JsonElement validation) : Exception("Dataset validation failed.")
{
    public JsonElement Validation { get; } = validation;
}

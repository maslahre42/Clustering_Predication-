using GarbageCollector.Api.Tests;
using Xunit.Abstractions;
using Xunit.Sdk;

// Execute the actual xUnit discovery/execution pipeline in-process when VSTest
// cannot open its communication socket. Assertions and fixtures remain xUnit's.
var failed = false;
foreach (var assembly in new[] { typeof(HistoryRulesTests).Assembly, typeof(GarbageCollector.AppHost.Tests.WorkspaceResourcesTests).Assembly })
{
    var sink = new ResultsSink();
    using var framework = new XunitTestFramework(sink);
    using var executor = framework.GetExecutor(assembly.GetName());
    var options = new RunnerOptions();
    options.SetValue("xunit.execution.DisableParallelization", true);
    executor.RunAll(sink, options, options);
    try { await sink.Finished.Task.WaitAsync(TimeSpan.FromSeconds(60)); }
    catch (TimeoutException) { Console.Error.WriteLine("xUnit execution timed out."); return 1; }
    failed |= sink.Failed != 0 || sink.Total == 0;
}
return failed ? 1 : 0;

sealed class RunnerOptions : ITestFrameworkDiscoveryOptions, ITestFrameworkExecutionOptions
{
    private readonly Dictionary<string, object?> values = [];
    public TValue GetValue<TValue>(string name) => values.TryGetValue(name, out var value) ? (TValue)value! : default!;
    public void SetValue<TValue>(string name, TValue value) => values[name] = value;
}
sealed class ResultsSink : Xunit.LongLivedMarshalByRefObject, IMessageSink
{
    public TaskCompletionSource Finished { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);
    public int Total { get; private set; }
    public int Failed { get; private set; }
    public bool OnMessage(IMessageSinkMessage message)
    {
        if (message is ITestFailed failed) {
            Console.Error.WriteLine($"FAIL {failed.Test.DisplayName}\n{string.Join("\n", failed.Messages)}\n{string.Join("\n", failed.StackTraces)}");
        }
        if (message is IErrorMessage error) {
            Failed++;
            Console.Error.WriteLine(string.Join("\n", error.Messages));
        }
        if (message is ITestAssemblyFinished finished) {
            Total = finished.TestsRun;
            Failed += finished.TestsFailed;
            Console.WriteLine($"xUnit: {Total} tests, {Failed} failed, {finished.TestsSkipped} skipped.");
            Finished.TrySetResult();
        }
        return true;
    }
}

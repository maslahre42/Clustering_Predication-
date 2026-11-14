using GarbageCollector.AppHost;

var builder = DistributedApplication.CreateBuilder(new DistributedApplicationOptions { Args = args, TrustDeveloperCertificate = false });
builder.AddCollectionWorkspace();
builder.Build().Run();

using Aspire.Hosting;
using Aspire.Hosting.ApplicationModel;
using Aspire.Hosting.JavaScript;
using Aspire.Hosting.Docker;
using Aspire.Hosting.Docker.Resources;
using Aspire.Hosting.Docker.Resources.ComposeNodes;
using GarbageCollector.AppHost;

namespace GarbageCollector.AppHost.Tests;

public class WorkspaceResourcesTests
{
    [Fact]
    public async Task PublishUsesContainerPathsAndProductionNetworkBindings()
    {
        var builder = CreateBuilder("--operation", "publish", "--step", "publish");
        builder.AddCollectionWorkspace();
        await using var app = builder.Build();
        Assert.False(builder.Resources.OfType<DockerComposeEnvironmentResource>().Single().DashboardEnabled);
        var api = Assert.IsAssignableFrom<ContainerResource>(builder.Resources.Single(resource => resource.Name == "api"));
        var dockerfile = Assert.Single(api.Annotations.OfType<DockerfileBuildAnnotation>());
        Assert.EndsWith("Solution/apps/api/Dockerfile", dockerfile.DockerfilePath.Replace('\\', '/'));
        Assert.Equal(Path.GetFullPath("../../..", builder.AppHostDirectory), dockerfile.ContextPath);
        var apiEnvironment = await ReadEnvironment(builder, api);
        Assert.Equal("/data/sql.db", apiEnvironment["Database__Path"]);
        Assert.Equal("Production", apiEnvironment["ASPNETCORE_ENVIRONMENT"]);
        Assert.Equal("http://0.0.0.0:8080", apiEnvironment["ASPNETCORE_URLS"]);
        Assert.Equal("api;localhost;127.0.0.1", apiEnvironment["AllowedHosts"]);
        Assert.DoesNotContain(api.Annotations.OfType<EndpointAnnotation>(), endpoint => endpoint.UriScheme == "https");
        Assert.Equal(8080, api.Annotations.OfType<EndpointAnnotation>().Single().TargetPort);
        var web = builder.Resources.Single(resource => resource.Name == "web");
        var webEnvironment = await ReadEnvironment(builder, web);
        Assert.Equal("0.0.0.0", webEnvironment["HOST"]);
        Assert.IsType<EndpointReference>(webEnvironment["NUXT_API_BASE"]);
    }

    [Fact]
    public void ComposePolicyKeepsSourceDataReadOnlyAndApiPrivate()
    {
        var compose = new ComposeFile();
        compose.AddService(new Service { Name = "api", Ports = ["5080:8080"] });
        compose.AddService(new Service { Name = "web", Ports = ["3000:3000"] });
        ComposeDeployment.Configure(compose);
        var api = compose.Services["api"];
        var web = compose.Services["web"];
        Assert.Empty(api.Ports);
        var volume = Assert.Single(api.Volumes);
        Assert.Equal("bind", volume.Type);
        Assert.Equal("/data", volume.Target);
        Assert.Equal(ComposeDeployment.DataDirectory, volume.Source);
        Assert.True(volume.ReadOnly);
        Assert.Equal("127.0.0.1:3000:3000", Assert.Single(web.Ports));
        Assert.Equal("unless-stopped", api.Restart);
        Assert.Equal("unless-stopped", web.Restart);
        Assert.Equal("${NUXT_PUBLIC_MAPTILER_API_KEY:-}", web.Environment["NUXT_PUBLIC_MAPTILER_API_KEY"]);
        Assert.NotNull(web.Healthcheck);
        Assert.Contains("/api/health", web.Healthcheck.Test.Last());

        // The source variable must survive YAML serialization for Compose to resolve on the server.
        var yaml = compose.ToYaml();
        Assert.Contains("${GARBAGE_COLLECTOR_DATA_DIR:-/var/lib/garbage-collector}", yaml);
        Assert.Contains("read_only: true", yaml);
    }

    private static IDistributedApplicationBuilder CreateBuilder(params string[] args)
    {
        // Locate source files without relying on the test process's working directory.
        var root = new DirectoryInfo(AppContext.BaseDirectory);
        while (root is not null && !File.Exists(Path.Combine(root.FullName, "GarbageCollector.slnx"))) root = root.Parent;
        return DistributedApplication.CreateBuilder(new DistributedApplicationOptions {
            Args = ["--hostBuilder:reloadConfigOnChange=false", .. args],
            ProjectDirectory = Path.Combine(root!.FullName, "apps", "apphost"),
            AssemblyName = typeof(WorkspaceResources).Assembly.FullName,
            DisableDashboard = true,
            TrustDeveloperCertificate = false,
        });
    }

    private static async Task<Dictionary<string, object>> ReadEnvironment(IDistributedApplicationBuilder builder, IResource resource)
    {
        var values = new Dictionary<string, object>();
        var context = new EnvironmentCallbackContext(builder.ExecutionContext, resource, values);
        foreach (var callback in resource.Annotations.OfType<EnvironmentCallbackAnnotation>())
            await callback.Callback(context);
        return values;
    }

    [Fact]
    public async Task DefaultDatabasePathPointsToExistingSourceWithoutStartingProcesses()
    {
        var builder = CreateBuilder();
        builder.AddCollectionWorkspace();
        await using var app = builder.Build();
        var api = Assert.Single(builder.Resources.OfType<ProjectResource>());
        var environment = await ReadEnvironment(builder, api);
        Assert.Equal(Path.GetFullPath("../../sql.db", builder.AppHostDirectory), environment["Database__Path"]);
        Assert.NotEmpty(api.Annotations.OfType<HealthCheckAnnotation>());
    }

    [Theory]
    [InlineData("fixtures/history.db")]
    [InlineData("/tmp/garbage-collector-test-history.db")]
    public async Task DatabaseOverrideResolvesAgainstApiDirectory(string path)
    {
        var builder = CreateBuilder($"--Database:Path={path}");
        builder.AddCollectionWorkspace();
        await using var app = builder.Build();
        var environment = await ReadEnvironment(builder, builder.Resources.OfType<ProjectResource>().Single());
        Assert.Equal(Path.GetFullPath(path, Path.GetFullPath("../api", builder.AppHostDirectory)), environment["Database__Path"]);
    }

    [Fact]
    public async Task WebWaitsForHealthyApiAndUsesInjectedEndpoint()
    {
        var builder = CreateBuilder();
        builder.AddCollectionWorkspace();
        await using var app = builder.Build();
        var api = builder.Resources.OfType<ProjectResource>().Single();
        var web = Assert.IsAssignableFrom<IResourceWithEnvironment>(builder.Resources.Single(r => r.Name == "web"));
        Assert.Contains(web.Annotations.OfType<WaitAnnotation>(), wait => ReferenceEquals(wait.Resource, api) && wait.WaitType == WaitType.WaitUntilHealthy);
        var http = Assert.Single(web.Annotations.OfType<EndpointAnnotation>());
        Assert.Equal(3000, http.Port);
        Assert.Equal("pnpm", web.Annotations.OfType<JavaScriptPackageManagerAnnotation>().Last().ExecutableName);
        Assert.Contains("--frozen-lockfile", web.Annotations.OfType<JavaScriptInstallCommandAnnotation>().Last().Args);

        // Allocate a fake endpoint in memory: no sockets, API startup, or SQLite access.
        var apiHttp = api.Annotations.OfType<EndpointAnnotation>().Single(e => e.Name == "http");
        apiHttp.AllocatedEndpoint = new AllocatedEndpoint(apiHttp, "localhost", 54321);
        var environment = await ReadEnvironment(builder, web);
        Assert.Equal("http://localhost:54321", await Assert.IsType<EndpointReference>(environment["NUXT_API_BASE"]).GetValueAsync(default));
        Assert.Equal("127.0.0.1", environment["HOST"]);
    }
}

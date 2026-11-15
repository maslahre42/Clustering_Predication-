using Aspire.Hosting;
using Aspire.Hosting.ApplicationModel;
using Microsoft.Extensions.Configuration;

namespace GarbageCollector.AppHost;

public static class WorkspaceResources
{
    public static void AddCollectionWorkspace(this IDistributedApplicationBuilder builder)
    {
        builder.AddDockerComposeEnvironment("compose")
            .WithProperties(environment => environment.DashboardEnabled = false)
            .ConfigureComposeFile(ComposeDeployment.Configure);
        // Preserve Database__Path overrides; resolve relative paths against the API,
        // just as standalone startup does. Never provision or seed the source file.
        var apiDirectory = Path.GetFullPath("../api", builder.AppHostDirectory);
        var databasePath = Path.GetFullPath(builder.Configuration["Database:Path"] ?? "../../sql.db", apiDirectory);

        var api = builder.AddProject<Projects.GarbageCollector_Api>("api")
            .WithEnvironment("Database__Path", builder.ExecutionContext.IsPublishMode ? ComposeDeployment.DatabasePath : databasePath)
            .WithHttpHealthCheck("/api/health");

        if (builder.ExecutionContext.IsPublishMode)
        {
            var projectRoot = Path.GetFullPath("../..", builder.AppHostDirectory);
            api.WithEnvironment("ASPNETCORE_ENVIRONMENT", "Production")
                .WithEnvironment("AllowedHosts", "api;localhost;127.0.0.1")
                .WithEnvironment("ASPNETCORE_URLS", "http://0.0.0.0:8080")
                .WithEndpoint("http", endpoint => endpoint.TargetPort = 8080);
            foreach (var endpoint in api.Resource.Annotations.OfType<EndpointAnnotation>().Where(endpoint => endpoint.UriScheme == "https").ToArray())
                api.Resource.Annotations.Remove(endpoint);
            api.PublishAsDockerFile(container => container.WithDockerfile(projectRoot, "apps/api/Dockerfile"));
        }

        // Aspire 13 marks JavaScript production publishing and base-image customization experimental.
#pragma warning disable ASPIREJAVASCRIPT001, ASPIREDOCKERFILEBUILDER001
        builder.AddJavaScriptApp("web", "../web", "dev")
            .WithPnpm(installArgs: ["--frozen-lockfile"])
            .PublishAsPackageScript("start")
            .WithDockerfileBaseImage(buildImage: "node:22-bookworm-slim", runtimeImage: "node:22-bookworm-slim")
            .WithHttpEndpoint(port: 3000, env: "PORT")
            .WithExternalHttpEndpoints()
            .WithEnvironment("HOST", builder.ExecutionContext.IsPublishMode ? "0.0.0.0" : "127.0.0.1")
            .WithEnvironment("NUXT_API_BASE", api.GetEndpoint("http"))
            .WaitFor(api);
#pragma warning restore ASPIREJAVASCRIPT001, ASPIREDOCKERFILEBUILDER001
    }
}

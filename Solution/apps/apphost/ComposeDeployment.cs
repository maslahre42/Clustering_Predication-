using Aspire.Hosting.Docker.Resources;
using Aspire.Hosting.Docker.Resources.ServiceNodes;

namespace GarbageCollector.AppHost;

/// <summary>Production Compose policy, shared by the publisher and isolated configuration tests.</summary>
public static class ComposeDeployment
{
    public const string DatabasePath = "/data/sql.db";
    public const string DataDirectory = "${GARBAGE_COLLECTOR_DATA_DIR:-/var/lib/garbage-collector}";

    public static void Configure(ComposeFile compose)
    {
        compose.Name = "garbage-collector";
        var api = compose.Services["api"];
        var web = compose.Services["web"];
        api.Ports.Clear();
        api.Restart = "unless-stopped";
        api.Volumes.Add(new Volume { Name = "collection-history", Type = "bind", Source = DataDirectory, Target = "/data", ReadOnly = true });

        web.Ports.Clear();
        web.Ports.Add("127.0.0.1:3000:3000");
        web.Restart = "unless-stopped";
        web.Environment["NUXT_PUBLIC_MAPTILER_API_KEY"] = "${NUXT_PUBLIC_MAPTILER_API_KEY:-}";
        web.Healthcheck = new Healthcheck {
            Test = ["CMD", "node", "-e", "fetch('http://127.0.0.1:3000/api/health').then(async r=>{if(!r.ok||(await r.json()).status!=='healthy')process.exit(1)}).catch(()=>process.exit(1))"],
            Interval = "30s", Timeout = "5s", Retries = 3, StartPeriod = "30s",
        };
    }
}

using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
namespace GarbageCollector.Api.Infrastructure.Persistence;

public static class PersistenceRegistration
{
    public static IServiceCollection AddHistoricalPersistence(this IServiceCollection services,
        IConfiguration configuration, IHostEnvironment environment)
    {
        var path = Path.GetFullPath(configuration["Database:Path"] ?? "../../sql.db", environment.ContentRootPath);
        if (!File.Exists(path)) throw new FileNotFoundException("SQLite database missing. Configure Database__Path.", path);
        var connection = new SqliteConnectionStringBuilder { DataSource = path, Mode = SqliteOpenMode.ReadOnly }.ToString();
        services.AddDbContext<HistoryDbContext>(options => options.UseSqlite(connection));
        return services;
    }
}

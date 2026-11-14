using Microsoft.EntityFrameworkCore;
using GarbageCollector.Api.Domain.Collections;
using GarbageCollector.Api.Domain.Locations;
namespace GarbageCollector.Api.Infrastructure.Persistence;

public sealed class HistoryDbContext(DbContextOptions<HistoryDbContext> options) : DbContext(options)
{
    public DbSet<Observation> Observations => Set<Observation>();
    public DbSet<BinLocation> Locations => Set<BinLocation>();
    protected override void OnModelCreating(ModelBuilder model)
    {
        model.Entity<Observation>(e => {
            e.HasNoKey(); e.ToTable("raw_data");
            e.Property(x => x.LocationId).HasColumnName("Location_id");
            e.Property(x => x.Material).HasColumnName("material_type");
            e.Property(x => x.Date).HasColumnName("date");
            e.Property(x => x.FillLevel).HasColumnName("fill_level_perc");
        });
        model.Entity<BinLocation>(e => {
            e.ToTable("locations"); e.HasKey(x => x.LocationId);
            e.Property(x => x.LocationId).HasColumnName("location_id");
            e.Property(x => x.Latitude).HasColumnName("latitude");
            e.Property(x => x.Longitude).HasColumnName("longitude");
            e.Property(x => x.IsSynthetic).HasColumnName("is_synthetic");
        });
    }
}

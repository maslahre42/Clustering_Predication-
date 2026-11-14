using GarbageCollector.Api.Api;
using GarbageCollector.Api.Infrastructure.Persistence;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddHistoricalPersistence(builder.Configuration, builder.Environment);
builder.Services.AddOpenApi();
builder.Services.AddProblemDetails();
builder.Services.AddScoped<GarbageCollector.Api.Features.Proposal.IForecastEngine, GarbageCollector.Api.Features.Proposal.PythonForecastEngine>();

var app = builder.Build();
app.UseExceptionHandler();
app.MapApplicationEndpoints();
app.Run();

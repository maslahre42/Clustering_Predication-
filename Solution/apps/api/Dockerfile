# Build with the repository root as context; only code is copied, never the source database.
FROM mcr.microsoft.com/dotnet/sdk:10.0-noble AS build
WORKDIR /src
COPY Solution/global.json Solution/NuGet.Config Solution/
COPY Solution/apps/api/ Solution/apps/api/
COPY Solution/forecast_service/worker.py Solution/forecast_service/requirements.txt Solution/forecast_service/
COPY Solution/forecast_service/integrations/ Solution/forecast_service/integrations/
COPY Omar-Work/fillinq/ Omar-Work/fillinq/
RUN dotnet publish Solution/apps/api/GarbageCollector.Api.csproj -c Release -o /publish

FROM mcr.microsoft.com/dotnet/aspnet:10.0-noble
WORKDIR /app
COPY --from=build /publish/ ./
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv \
    && python3 -m venv /opt/forecast \
    && /opt/forecast/bin/pip install --no-cache-dir -r /app/forecast_service/requirements.txt \
    && rm -rf /var/lib/apt/lists/*
ENV Forecast__Python=/opt/forecast/bin/python \
    Forecast__Script=/app/forecast_service/worker.py \
    Database__Path=/data/sql.db \
    ASPNETCORE_URLS=http://0.0.0.0:8080
USER $APP_UID
EXPOSE 8080
ENTRYPOINT ["dotnet", "GarbageCollector.Api.dll"]

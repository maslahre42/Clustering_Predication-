# Build with the standalone project root as context; only code is copied, never the source database.
FROM mcr.microsoft.com/dotnet/sdk:10.0-noble AS build
WORKDIR /src
COPY global.json NuGet.Config ./
COPY apps/api/ apps/api/
COPY forecast_service/worker.py forecast_service/requirements.txt forecast_service/
COPY forecast_service/integrations/ forecast_service/integrations/
COPY forecast_service/vendor/fillinq/ forecast_service/vendor/fillinq/
RUN dotnet publish apps/api/GarbageCollector.Api.csproj -c Release -o /publish

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

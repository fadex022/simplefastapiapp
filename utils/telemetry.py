from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from configuration.config import get_app_settings

app_settings = get_app_settings()


def configure_telemetry(app=None):
    """Configure OpenTelemetry with appropriate exporters and resources for both tracing and metrics"""

    # Définir les attributs de ressource pour identifier votre service
    resource = Resource.create({
        "service.name": "simplefastapiapp",
        "service.version": "0.1.0",
        "deployment.environment": app_settings.ENVIRONMENT
    })

    # Configurer le fournisseur de traceur
    tracer_provider = TracerProvider(resource=resource)

    # Configurer l'exportateur OTLP pour les traces
    otlp_trace_exporter = OTLPSpanExporter(
        endpoint=app_settings.OTLP_ENDPOINT,  # Par exemple "http://jaeger:4317"
    )

    # Ajouter le processeur de spans à l'exportateur
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_trace_exporter))

    # Définir le fournisseur de traceur global
    trace.set_tracer_provider(tracer_provider)

    # Obtenir un traceur pour votre application
    tracer = trace.get_tracer("simplefastapiapp")

    # Configurer l'exportateur OTLP pour les métriques
    otlp_metric_exporter = OTLPMetricExporter(
        endpoint=app_settings.OTLP_ENDPOINT,
    )

    # Configurer le lecteur de métriques
    metric_reader = PeriodicExportingMetricReader(
        exporter=otlp_metric_exporter,
        export_interval_millis=10000  # Exporter les métriques toutes les 10 secondes
    )

    # Configurer le fournisseur de métriques
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader]
    )

    # Définir le fournisseur de métriques global
    metrics.set_meter_provider(meter_provider)

    # Obtenir un compteur de métriques pour votre application
    meter = metrics.get_meter("simplefastapiapp")

    # Instrumenter FastAPI si une application est fournie
    if app:
        FastAPIInstrumentor.instrument_app(app)

    return tracer, meter


# Créer un traceur et un compteur de métriques global pour l'application
tracer, meter = configure_telemetry()

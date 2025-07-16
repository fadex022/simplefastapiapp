from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from configuration.config import get_app_settings

app_settings = get_app_settings()


def configure_telemetry(app=None):
    """Configure OpenTelemetry with appropriate exporters and resources"""

    # Définir les attributs de ressource pour identifier votre service
    resource = Resource.create({
        "service.name": "simplefastapiapp",
        "service.version": "0.1.0",
        "deployment.environment": app_settings.ENVIRONMENT
    })

    # Configurer le fournisseur de traceur
    tracer_provider = TracerProvider(resource=resource)

    # Configurer l'exportateur OTLP (peut être remplacé par d'autres exportateurs)
    otlp_exporter = OTLPSpanExporter(
        endpoint=app_settings.OTLP_ENDPOINT,  # Par exemple "http://jaeger:4317"
    )

    # Ajouter le processeur de spans à l'exportateur
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # Définir le fournisseur de traceur global
    trace.set_tracer_provider(tracer_provider)

    # Obtenir un traceur pour votre application
    tracer = trace.get_tracer("simplefastapiapp")

    # Instrumenter FastAPI si une application est fournie
    if app:
        FastAPIInstrumentor.instrument_app(app)

    return tracer


# Créer un traceur global pour l'application
tracer = configure_telemetry()
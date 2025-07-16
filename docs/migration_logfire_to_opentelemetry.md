# Migration de Logfire vers OpenTelemetry

## Table des matières
1. [Introduction](#introduction)
2. [Implémentation actuelle avec Logfire](#implémentation-actuelle-avec-logfire)
3. [Présentation d'OpenTelemetry](#présentation-dopentelemetry)
4. [Guide de migration étape par étape](#guide-de-migration-étape-par-étape)
5. [Exemples de configuration](#exemples-de-configuration)
6. [Avantages de la migration](#avantages-de-la-migration)
7. [Conclusion](#conclusion)

## Introduction

Ce document explique comment migrer d'une implémentation de journalisation et de traçage basée sur Logfire vers une solution utilisant OpenTelemetry. Cette migration permettra d'améliorer les capacités d'observabilité de l'application tout en adoptant un standard ouvert et largement supporté par l'industrie.

## Implémentation actuelle avec Logfire

Actuellement, l'application utilise Logfire pour la journalisation et le traçage. Voici les principales caractéristiques de l'implémentation actuelle :

- Une classe `ConditionalLogger` qui encapsule les fonctionnalités de Logfire
- Des méthodes pour différents niveaux de journalisation (debug, info, warn, error, exception)
- Des fonctionnalités pour :
  - Nettoyer les données sensibles des journaux
  - Journalisation conditionnelle basée sur les niveaux de log
  - Suivi des performances
  - Décorateurs de fonction pour la journalisation des performances
- Utilisation de `logfire.span` pour le traçage des requêtes HTTP

## Présentation d'OpenTelemetry

OpenTelemetry est un framework d'observabilité open-source qui fournit un ensemble d'APIs, de bibliothèques, d'agents et d'instrumentation pour générer, collecter et exporter des données télémétriques (traces, métriques et logs). Voici ses principales caractéristiques :

- **Standard ouvert** : Supporté par la Cloud Native Computing Foundation (CNCF)
- **Polyvalent** : Couvre les traces, les métriques et les logs dans une seule solution
- **Extensible** : Nombreux exportateurs disponibles (Jaeger, Zipkin, Prometheus, etc.)
- **Indépendant du fournisseur** : Fonctionne avec de nombreux backends d'observabilité
- **Instrumentation automatique** : Possibilité d'instrumenter automatiquement les frameworks et bibliothèques populaires

## Guide de migration étape par étape

### 1. Installation des dépendances OpenTelemetry

Ajoutez les dépendances OpenTelemetry nécessaires à votre fichier `pyproject.toml` :

```toml
[project]
dependencies = [
    # Dépendances existantes...
    "opentelemetry-api",
    "opentelemetry-sdk",
    "opentelemetry-instrumentation-fastapi",
    "opentelemetry-exporter-otlp",
]
```

### 2. Configuration d'OpenTelemetry

Créez un nouveau fichier `utils/telemetry.py` pour configurer OpenTelemetry :

```python
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
```

### 3. Mise à jour de la classe de journalisation

Remplacez le fichier `utils/logging.py` existant par une nouvelle implémentation utilisant OpenTelemetry :

```python
import functools
import time
import logging
from typing import Any, Callable, Dict, Optional, Set, Type, TypeVar, Union, cast
from configuration.config import get_app_settings
import inspect
from opentelemetry import trace
from opentelemetry.trace.status import Status, StatusCode
from utils.telemetry import tracer

app_settings = get_app_settings()

# Configurer le logger standard de Python
logging.basicConfig(
    level=getattr(logging, app_settings.LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

# Définir les niveaux de log pour la journalisation conditionnelle
class LogLevel:
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

# Définir les modèles de journalisation réutilisables pour les données sensibles
SENSITIVE_FIELDS = {
    "password", "secret", "token", "key", "auth", "credentials", "code",
    "pin", "access_token", "refresh_token", "id_token"
}

# Fonction d'aide pour nettoyer les données sensibles
def scrub_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Supprimer les informations sensibles des journaux"""
    if not isinstance(data, dict):
        return data

    result = {}
    for key, value in data.items():
        # Vérifier si c'est un champ sensible
        is_sensitive = any(sensitive in key.lower() for sensitive in SENSITIVE_FIELDS)

        if is_sensitive and value:
            # Masquer la valeur mais conserver les informations de type
            result[key] = "*" * 8
        elif isinstance(value, dict):
            # Nettoyer récursivement les dictionnaires imbriqués
            result[key] = scrub_sensitive_data(value)
        elif isinstance(value, list):
            # Gérer les listes d'éléments
            result[key] = [
                scrub_sensitive_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value

    return result

# Mettre en cache les résultats des fonctions pour éviter les messages de journal répétés
@functools.lru_cache(maxsize=128)
def should_log_exception(exception_class: Type[Exception]) -> bool:
    """Déterminer si ce type d'exception doit être journalisé"""
    # Toujours journaliser les exceptions critiques
    critical_exceptions = {
        "UnexpectedException",
        "DatabaseException",
        "DatabaseIntegrityException"
    }

    return (
            exception_class.__name__ in critical_exceptions or
            app_settings.ENVIRONMENT == "development"
    )

# Suivi des performances
class PerformanceTracker:
    def __init__(self, threshold_ms: int = 500):
        self.threshold_ms = threshold_ms
        self.start_time = time.time()

    def check_and_log(self, operation: str, extra: Dict[str, Any] = None) -> None:
        """Journaliser si l'opération a pris plus de temps que le seuil"""
        elapsed_ms = (time.time() - self.start_time) * 1000
        if elapsed_ms > self.threshold_ms:
            extra = extra or {}
            extra["elapsed_ms"] = elapsed_ms

            logger.warning(
                f"Opération lente : {operation} a pris {elapsed_ms:.2f}ms",
                extra=extra
            )

# Classe de journalisation principale avec journalisation conditionnelle
class ConditionalLogger:
    def __init__(self):
        self.log_level = getattr(logging, app_settings.LOG_LEVEL, logging.INFO)
        self.python_logger = logging.getLogger("app")
        self.python_logger.setLevel(self.log_level)

    def set_level(self, level: int) -> None:
        """Définir le niveau de journalisation"""
        self.log_level = level
        self.python_logger.setLevel(level)

    def debug(self, message: str, extra: Dict[str, Any] = None) -> None:
        """Journaliser un message de débogage si le niveau le permet"""
        if self.log_level <= LogLevel.DEBUG:
            safe_extra = scrub_sensitive_data(extra or {})
            self.python_logger.debug(message, extra={"otel": safe_extra})
            current_span = trace.get_current_span()
            if current_span:
                for key, value in safe_extra.items():
                    current_span.set_attribute(f"log.{key}", str(value))
                current_span.add_event("debug", {"message": message})

    def info(self, message: str, extra: Dict[str, Any] = None) -> None:
        """Journaliser un message d'information si le niveau le permet"""
        if self.log_level <= LogLevel.INFO:
            safe_extra = scrub_sensitive_data(extra or {})
            self.python_logger.info(message, extra={"otel": safe_extra})
            current_span = trace.get_current_span()
            if current_span:
                for key, value in safe_extra.items():
                    current_span.set_attribute(f"log.{key}", str(value))
                current_span.add_event("info", {"message": message})

    def warn(self, message: str, extra: Dict[str, Any] = None) -> None:
        """Journaliser un message d'avertissement"""
        safe_extra = scrub_sensitive_data(extra or {})
        self.python_logger.warning(message, extra={"otel": safe_extra})
        current_span = trace.get_current_span()
        if current_span:
            for key, value in safe_extra.items():
                current_span.set_attribute(f"log.{key}", str(value))
            current_span.add_event("warning", {"message": message})

    def warning(self, message: str, extra: Dict[str, Any] = None) -> None:
        """Alias pour warn() pour la compatibilité"""
        self.warn(message, extra=extra)

    def error(self, message: str, extra: Dict[str, Any] = None, exc_info: bool = False) -> None:
        """Journaliser un message d'erreur"""
        safe_extra = scrub_sensitive_data(extra or {})
        self.python_logger.error(message, extra={"otel": safe_extra}, exc_info=exc_info)
        current_span = trace.get_current_span()
        if current_span:
            for key, value in safe_extra.items():
                current_span.set_attribute(f"log.{key}", str(value))
            current_span.add_event("error", {"message": message})
            current_span.set_status(Status(StatusCode.ERROR))

    def exception(self, e: Exception, message: Optional[str] = None, extra: Dict[str, Any] = None) -> None:
        """Journaliser une exception avec une gestion intelligente"""
        if not should_log_exception(e.__class__):
            return

        if not message:
            message = f"Exception: {str(e)}"

        safe_extra = scrub_sensitive_data(extra or {})
        # Ajouter le type d'exception au journal
        safe_extra["exception_type"] = e.__class__.__name__

        # Obtenir le nom de la fonction appelante pour un meilleur contexte
        frame = inspect.currentframe().f_back
        if frame:
            func_name = frame.f_code.co_name
            module_name = frame.f_globals["__name__"]
            safe_extra["source"] = f"{module_name}.{func_name}"

        self.python_logger.exception(message, extra={"otel": safe_extra})
        
        current_span = trace.get_current_span()
        if current_span:
            for key, value in safe_extra.items():
                current_span.set_attribute(f"log.{key}", str(value))
            current_span.record_exception(e)
            current_span.set_status(Status(StatusCode.ERROR, str(e)))

# Créer une instance singleton
logger = ConditionalLogger()

# Décorateur de fonction pour la journalisation des performances
def log_performance(threshold_ms: int = 500):
    """Décorateur pour journaliser les exécutions de fonctions lentes"""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(f"{func.__module__}.{func.__name__}"):
                start_time = time.time()
                result = func(*args, **kwargs)
                elapsed_ms = (time.time() - start_time) * 1000

                current_span = trace.get_current_span()
                current_span.set_attribute("function.duration_ms", elapsed_ms)

                if elapsed_ms > threshold_ms:
                    logger.warning(
                        f"Fonction lente : {func.__name__} a pris {elapsed_ms:.2f}ms",
                        extra={
                            "function": func.__name__,
                            "module": func.__module__,
                            "elapsed_ms": elapsed_ms
                        }
                    )

                return result

        return wrapper

    return decorator

# Décorateur de fonction asynchrone pour la journalisation des performances
def log_performance_async(threshold_ms: int = 500):
    """Décorateur pour journaliser les exécutions de fonctions asynchrones lentes"""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(f"{func.__module__}.{func.__name__}"):
                start_time = time.time()
                result = await func(*args, **kwargs)
                elapsed_ms = (time.time() - start_time) * 1000

                current_span = trace.get_current_span()
                current_span.set_attribute("function.duration_ms", elapsed_ms)

                if elapsed_ms > threshold_ms:
                    logger.warning(
                        f"Fonction asynchrone lente : {func.__name__} a pris {elapsed_ms:.2f}ms",
                        extra={
                            "function": func.__name__,
                            "module": func.__module__,
                            "elapsed_ms": elapsed_ms
                        }
                    )

                return result

        return wrapper

    return decorator

# Fonction utilitaire pour créer un span
def create_span(name: str, extra: Dict[str, Any] = None):
    """Créer un span OpenTelemetry avec des attributs supplémentaires"""
    return tracer.start_as_current_span(name, attributes=extra)
```

### 4. Mise à jour du middleware dans main.py

Modifiez le middleware dans `main.py` pour utiliser OpenTelemetry au lieu de Logfire :

```python
from utils.telemetry import configure_telemetry, tracer
from opentelemetry import trace

# Configurer OpenTelemetry avec l'application FastAPI
configure_telemetry(app)

@app.middleware("http")
async def request_middleware(request: Request, call_next: Callable):
    path = request.url.path
    method = request.method
    request_id = request.headers.get("X-Request-ID", "")

    # Ignorer la journalisation pour les chemins qui n'en ont pas besoin
    if any(path.startswith(skip) for skip in SKIP_PATHS):
        return await call_next(request)

    # Toujours journaliser le temps de requête pour la surveillance des performances
    start_time = time.time()

    # Définir le contexte de journal standard pour cette requête
    log_context = {
        "request_id": request_id,
        "method": method,
        "path": path
    }

    # Créer un span pour la requête
    with tracer.start_as_current_span(f"{method} {path}", attributes=log_context) as span:
        try:
            response = await call_next(request)

            # Calculer la durée de la requête
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)

            # Ajouter le timing et le statut au contexte de journal
            log_context.update({
                "status_code": response.status_code,
                "process_time": process_time,
            })
            
            # Ajouter des attributs au span
            span.set_attribute("http.status_code", response.status_code)
            span.set_attribute("http.duration", process_time)

            # Journaliser uniquement les réponses lentes ou d'erreur pour réduire le volume de journaux
            if process_time > 1.0:
                logger.warn(
                    f"Réponse lente : {process_time}",
                    extra=log_context
                )

            return response

        except Exception as e:
            # Toujours journaliser les exceptions
            process_time = time.time() - start_time
            log_context.update({
                "process_time": process_time,
                "error_type": e.__class__.__name__
            })

            # Marquer le span comme en erreur
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))

            logger.exception(e, "Le traitement de la requête a échoué", extra=log_context)
            raise
```

### 5. Mise à jour de la configuration

Ajoutez les paramètres de configuration OpenTelemetry dans `configuration/config.py` :

```python
class AppSettings(BaseSettings):
    # Paramètres existants...
    
    # Paramètres OpenTelemetry
    OTLP_ENDPOINT: str = "http://localhost:4317"  # Endpoint OTLP par défaut
    OTEL_SERVICE_NAME: str = "simplefastapiapp"
    OTEL_TRACES_EXPORTER: str = "otlp"  # Options: otlp, jaeger, zipkin, console
```

## Exemples de configuration

### Configuration pour l'exportation vers Jaeger

```python
# Dans utils/telemetry.py
from opentelemetry.exporter.jaeger.thrift import JaegerExporter

def configure_telemetry(app=None):
    # Configuration existante...
    
    # Utiliser l'exportateur Jaeger au lieu d'OTLP
    jaeger_exporter = JaegerExporter(
        agent_host_name=app_settings.JAEGER_HOST,
        agent_port=app_settings.JAEGER_PORT,
    )
    
    tracer_provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
    # Reste de la configuration...
```

### Configuration pour l'exportation vers Prometheus (métriques)

```python
# Dans utils/telemetry.py
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from prometheus_client import start_http_server

def configure_metrics():
    # Démarrer le serveur HTTP Prometheus
    start_http_server(port=8000, addr="0.0.0.0")
    
    # Créer un lecteur de métriques Prometheus
    prometheus_reader = PrometheusMetricReader()
    
    # Configurer le fournisseur de métriques
    metrics_provider = MeterProvider(
        metric_readers=[prometheus_reader],
        resource=resource
    )
    
    # Définir le fournisseur de métriques global
    metrics.set_meter_provider(metrics_provider)
    
    # Obtenir un compteur de métriques pour l'application
    meter = metrics.get_meter("simplefastapiapp")
    
    return meter
```

## Avantages de la migration

La migration de Logfire vers OpenTelemetry offre plusieurs avantages :

1. **Standard ouvert** : OpenTelemetry est un standard ouvert soutenu par la CNCF, garantissant une compatibilité à long terme et une large adoption par l'industrie.

2. **Solution complète d'observabilité** : OpenTelemetry fournit une solution unifiée pour les traces, les métriques et les logs, permettant une corrélation facile entre ces différentes dimensions.

3. **Écosystème riche** : Un large éventail d'intégrations et d'exportateurs est disponible, permettant d'envoyer les données télémétriques vers de nombreux backends (Jaeger, Zipkin, Prometheus, Grafana, etc.).

4. **Instrumentation automatique** : OpenTelemetry offre des capacités d'instrumentation automatique pour de nombreux frameworks et bibliothèques, réduisant la quantité de code manuel nécessaire.

5. **Indépendance du fournisseur** : Vous pouvez changer de backend d'observabilité sans modifier votre code d'instrumentation.

6. **Performances améliorées** : OpenTelemetry est conçu pour avoir un impact minimal sur les performances de l'application.

7. **Contexte distribué** : Meilleure gestion du contexte dans les systèmes distribués, permettant de suivre les requêtes à travers plusieurs services.

## Conclusion

La migration de Logfire vers OpenTelemetry représente une amélioration significative pour l'observabilité de votre application. Bien que cette migration nécessite des modifications dans plusieurs parties du code, les avantages à long terme en termes de flexibilité, de standardisation et de fonctionnalités justifient cet effort.

En suivant ce guide étape par étape, vous pouvez effectuer cette migration de manière progressive, en vous assurant que chaque composant fonctionne correctement avant de passer au suivant. Une fois la migration terminée, votre application bénéficiera d'une solution d'observabilité moderne, évolutive et conforme aux standards de l'industrie.
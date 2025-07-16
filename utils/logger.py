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
    "password", "secret", "token", "key", "auth", "credentials",
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
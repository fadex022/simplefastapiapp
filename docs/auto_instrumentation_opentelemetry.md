# Comment fonctionne l'auto-instrumentation avec OpenTelemetry

## Table des matières
1. [Introduction](#introduction)
2. [Principes de l'auto-instrumentation](#principes-de-lauto-instrumentation)
3. [Configuration de l'auto-instrumentation](#configuration-de-lauto-instrumentation)
4. [Auto-instrumentation dans ce projet](#auto-instrumentation-dans-ce-projet)
5. [Avantages et limites](#avantages-et-limites)
6. [Personnalisation de l'auto-instrumentation](#personnalisation-de-lauto-instrumentation)
7. [Conclusion](#conclusion)

## Introduction

L'auto-instrumentation est une fonctionnalité puissante d'OpenTelemetry qui permet d'ajouter automatiquement des traces, des métriques et des logs à votre application sans avoir à modifier manuellement chaque partie de votre code. Ce document explique comment fonctionne l'auto-instrumentation avec OpenTelemetry et comment elle est implémentée dans ce projet.

## Principes de l'auto-instrumentation

L'auto-instrumentation d'OpenTelemetry fonctionne en utilisant plusieurs mécanismes :

1. **Instrumentation des bibliothèques** : OpenTelemetry fournit des instrumentations spécifiques pour de nombreuses bibliothèques et frameworks populaires (FastAPI, Flask, Django, SQLAlchemy, Redis, etc.).

2. **Monkey patching** : Pour les bibliothèques Python, l'auto-instrumentation utilise souvent le "monkey patching", une technique qui remplace dynamiquement les méthodes d'une bibliothèque par des versions instrumentées qui collectent des données télémétriques.

3. **Intégration avec les frameworks** : Pour les frameworks web comme FastAPI, l'auto-instrumentation s'intègre avec le système de middleware pour capturer les requêtes entrantes et sortantes.

4. **Propagation du contexte** : L'auto-instrumentation gère automatiquement la propagation du contexte entre les différentes parties de l'application et entre les services.

## Configuration de l'auto-instrumentation

Pour configurer l'auto-instrumentation, vous avez deux approches principales :

### 1. Instrumentation programmatique

C'est l'approche utilisée dans ce projet. Vous importez et utilisez des instrumentateurs spécifiques dans votre code :

```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Après avoir créé votre application FastAPI
app = FastAPI()

# Instrumenter l'application
FastAPIInstrumentor.instrument_app(app)
```

### 2. Instrumentation automatique via l'agent OpenTelemetry

Une alternative est d'utiliser l'agent OpenTelemetry qui peut instrumenter automatiquement votre application au démarrage :

```bash
opentelemetry-instrument --traces_exporter otlp python -m uvicorn main:app
```

Cette commande lance votre application avec l'instrumentation automatique activée, sans nécessiter de modifications de code.

## Auto-instrumentation dans ce projet

Dans ce projet, l'auto-instrumentation est configurée de manière programmatique dans le fichier `utils/telemetry.py` :

```python
def configure_telemetry(app=None):
    # Configuration du TracerProvider, des ressources, etc.
    
    # Instrumenter FastAPI si une application est fournie
    if app:
        FastAPIInstrumentor.instrument_app(app)
    
    return tracer
```

Cette fonction est appelée dans `main.py` après la création de l'application FastAPI et l'enregistrement des routes :

```python
# Configurer OpenTelemetry avec l'application FastAPI
configure_telemetry(app)
```

### Ce que fait l'auto-instrumentation FastAPI

Lorsque `FastAPIInstrumentor.instrument_app(app)` est appelé, il :

1. **Ajoute un middleware** à l'application FastAPI qui intercepte toutes les requêtes entrantes et sortantes.
2. **Crée automatiquement des spans** pour chaque requête HTTP avec des attributs comme :
   - `http.method` (GET, POST, etc.)
   - `http.url`
   - `http.status_code`
   - `http.route` (le chemin de route FastAPI)
3. **Propage le contexte de trace** entre les requêtes via les en-têtes HTTP.
4. **Capture les exceptions** qui se produisent pendant le traitement des requêtes.

### Instrumentation supplémentaire dans ce projet

En plus de l'auto-instrumentation, ce projet utilise également :

1. **Middleware personnalisé** : Un middleware HTTP personnalisé dans `main.py` qui crée des spans supplémentaires avec plus de détails.

2. **Intégration avec la journalisation** : La classe `ConditionalLogger` dans `utils/logger.py` qui ajoute les informations de journal aux spans actuels.

3. **Décorateurs de performance** : Les fonctions `log_performance` et `log_performance_async` qui créent des spans pour les fonctions individuelles.

## Avantages et limites

### Avantages de l'auto-instrumentation

1. **Rapidité d'implémentation** : Ajoutez l'observabilité à votre application avec un minimum de code.
2. **Couverture complète** : Capture automatiquement les interactions avec les frameworks et bibliothèques supportés.
3. **Standardisation** : Utilise des attributs et des noms de span standardisés selon les conventions sémantiques d'OpenTelemetry.
4. **Maintenance simplifiée** : Les mises à jour des instrumentations sont gérées par la communauté OpenTelemetry.

### Limites de l'auto-instrumentation

1. **Granularité limitée** : L'auto-instrumentation peut ne pas capturer tous les détails spécifiques à votre application.
2. **Couverture incomplète** : Toutes les bibliothèques ne sont pas supportées.
3. **Surcharge potentielle** : Peut générer beaucoup de données télémétriques, ce qui peut avoir un impact sur les performances.
4. **Personnalisation nécessaire** : Pour des besoins spécifiques, vous devrez toujours ajouter une instrumentation manuelle.

## Personnalisation de l'auto-instrumentation

Vous pouvez personnaliser l'auto-instrumentation de plusieurs façons :

### 1. Configuration des instrumentateurs

```python
FastAPIInstrumentor.instrument_app(
    app,
    excluded_urls="/health,/metrics",  # Exclure certaines URLs
    tracer_provider=tracer_provider,   # Utiliser un fournisseur de traceur spécifique
)
```

### 2. Combinaison avec l'instrumentation manuelle

Comme dans ce projet, vous pouvez combiner l'auto-instrumentation avec une instrumentation manuelle pour obtenir plus de détails :

```python
# Auto-instrumentation
FastAPIInstrumentor.instrument_app(app)

# Instrumentation manuelle supplémentaire
@app.middleware("http")
async def custom_middleware(request, call_next):
    with tracer.start_as_current_span("custom_operation") as span:
        span.set_attribute("custom.attribute", "value")
        response = await call_next(request)
        return response
```

### 3. Filtrage des spans

Vous pouvez configurer des processeurs de spans pour filtrer ou modifier les spans avant qu'ils ne soient exportés :

```python
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace import sampling

# Utiliser un échantillonneur pour réduire le volume de données
sampler = sampling.ParentBased(sampling.TraceIdRatioBased(0.1))  # 10% des traces
tracer_provider = TracerProvider(sampler=sampler)
```

## Conclusion

L'auto-instrumentation d'OpenTelemetry offre un moyen rapide et efficace d'ajouter de l'observabilité à votre application. Dans ce projet, elle est utilisée pour instrumenter automatiquement l'application FastAPI, tout en étant complétée par une instrumentation manuelle pour des besoins spécifiques.

Pour tirer le meilleur parti de l'auto-instrumentation, il est recommandé de :

1. Commencer par l'auto-instrumentation pour obtenir rapidement des données télémétriques de base.
2. Identifier les parties critiques de votre application qui nécessitent plus de détails.
3. Ajouter une instrumentation manuelle ciblée pour ces parties spécifiques.
4. Configurer l'échantillonnage et le filtrage pour gérer le volume de données.

Cette approche combinée vous permettra d'obtenir une observabilité complète de votre application tout en maintenant un bon équilibre entre la couverture et les performances.
import redis
import json
import functools
import asyncio
from typing import Any, Callable, Tuple

import redis.exceptions
from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from configuration.config import get_redis_settings
from utils.logger import logger

# Get Redis settings
redis_settings = get_redis_settings()

# Initialize Redis clients
# Synchronous client for non-async operations
redis_client: Redis = redis.Redis(
    host=redis_settings.REDIS_HOST,
    port=redis_settings.REDIS_PORT,
    password=redis_settings.REDIS_PASSWORD,
    db=redis_settings.REDIS_DB,
    decode_responses=False  # Keep as bytes for proper serialization
)

# Asynchronous client for async operations
async_redis_client: AsyncRedis = redis.asyncio.Redis(
    host=redis_settings.REDIS_HOST,
    port=redis_settings.REDIS_PORT,
    password=redis_settings.REDIS_PASSWORD,
    db=redis_settings.REDIS_DB,
    decode_responses=False  # Keep as bytes for proper serialization
)

def get_redis_client() -> Redis:
    """
    Get the synchronous Redis client instance
    """
    return redis_client

def get_async_redis_client() -> AsyncRedis:
    """
    Get the asynchronous Redis client instance
    """
    return async_redis_client


def create_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Create a unique cache key based on function arguments
    """
    # Create a list of all args and kwargs
    key_parts = [prefix]

    # Add positional args
    for arg in args:
        if isinstance(arg, (str, int, float, bool)):
            key_parts.append(str(arg))

    # Add keyword args (sorted to ensure consistent keys)
    for k, v in sorted(kwargs.items()):
        if isinstance(v, (str, int, float, bool)):
            key_parts.append(f"{k}:{v}")

    # Join and hash for a consistent length key
    key_string = ":".join(key_parts)
    return f"{key_string}"


def cache(ttl: int = None, prefix: str = None):
    """
    Cache decorator for functions and methods

    Args:
        ttl: Time to live in seconds. Defaults to Redis setting TTL.
        prefix: Key prefix for the cache. Defaults to function name.
    """
    ttl = ttl or redis_settings.REDIS_TTL

    def decorator(func: Callable) -> Callable:
        func_prefix = prefix or func.__qualname__

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Create a cache key
            cache_key = create_cache_key(func_prefix, *args, **kwargs)

            # Try to get from the cache
            try:
                cached_value = await async_redis_client.get(cache_key)
                if cached_value:
                    logger.debug(f"Cache hit for {cache_key}")
                    # Deserialize the cached value
                    data = json.loads(cached_value)

                    # Check if the function returns a StandardResponse
                    return_type = func.__annotations__.get('return')
                    if return_type and hasattr(return_type, '__name__') and return_type.__name__ == 'StandardResponse':
                        from models.response.StandardResponse import StandardResponse
                        # Reconstruct StandardResponse object
                        if isinstance(data, dict):
                            return StandardResponse(**data)
                        elif isinstance(data, str):
                            # Handle case where data is a string
                            logger.debug(f"Converting string data to dict for StandardResponse")
                            return StandardResponse(data={"response": data}, status="success", message=None)
                        else:
                            # For other types, create a default StandardResponse
                            logger.warning(f"Unexpected data type in cache: {type(data)}")
                            return StandardResponse(data={"cached_value": data}, status="success", message=None)
                    else:
                        # For other return types, just return the deserialized JSON
                        return data

                logger.debug(f"Cache miss for {cache_key}")
                # Execute the function
                result = await func(*args, **kwargs)

                # Process the result for caching
                try:
                    # Check if result is a StandardResponse
                    if hasattr(result, 'to_dict'):
                        # Use to_dict method for StandardResponse objects
                        serialized = json.dumps(result.to_dict())
                    else:
                        # For other types, use default serialization
                        serialized = json.dumps(result, default=str)
                except Exception as e:
                    logger.warning(f"Error serializing data: {str(e)}")
                    # Fallback to string representation
                    serialized = json.dumps(str(result))

                # Cache the result
                await async_redis_client.setex(
                    cache_key,
                    ttl,
                    serialized
                )
                return result

            except redis.RedisError as e:
                logger.error(f"Redis error in cache: {str(e)}")
                # Execute the function without caching on error
                return await func(*args, **kwargs)

            except Exception as e:
                logger.warn(f"Unexpected error in cache: {str(e)}")
                return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # Create a cache key
            cache_key = create_cache_key(func_prefix, *args, **kwargs)

            # Try to get from the cache
            try:
                cached_value = redis_client.get(cache_key)
                if cached_value:
                    logger.debug(f"Cache hit for {cache_key}")
                    # Deserialize the cached value
                    data = json.loads(cached_value)

                    # Check if the function returns a StandardResponse
                    return_type = func.__annotations__.get('return')
                    if return_type and hasattr(return_type, '__name__') and return_type.__name__ == 'StandardResponse':
                        from models.response.StandardResponse import StandardResponse
                        # Reconstruct StandardResponse object
                        if isinstance(data, dict):
                            return StandardResponse(**data)
                        elif isinstance(data, str):
                            # Handle case where data is a string
                            logger.debug(f"Converting string data to dict for StandardResponse")
                            return StandardResponse(data={"response": data}, status="success", message=None)
                        else:
                            # For other types, create a default StandardResponse
                            logger.warning(f"Unexpected data type in cache: {type(data)}")
                            return StandardResponse(data={"cached_value": data}, status="success", message=None)
                    else:
                        # For other return types, just return the deserialized JSON
                        return data

                logger.debug(f"Cache miss for {cache_key}")
                # Execute the function
                result = func(*args, **kwargs)

                # Process the result for caching
                try:
                    # Check if result is a StandardResponse
                    if hasattr(result, 'to_dict'):
                        # Use to_dict method for StandardResponse objects
                        serialized = json.dumps(result.to_dict())
                    else:
                        # For other types, use default serialization
                        serialized = json.dumps(result, default=str)
                except Exception as e:
                    logger.warning(f"Error serializing data: {str(e)}")
                    # Fallback to string representation
                    serialized = json.dumps(str(result))

                # Cache the result
                redis_client.setex(
                    cache_key,
                    ttl,
                    serialized
                )
                return result

            except redis.RedisError as e:
                logger.error(f"Redis error in cache: {str(e)}")
                # Execute the function without caching on error
                return func(*args, **kwargs)

            except Exception as e:
                logger.error(f"Unexpected error in cache: {str(e)}")
                return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


async def invalidate_cache(prefix: str, pattern: str = "*"):
    """
    Invalidate cache entries with a specific prefix and pattern

    Args:
        prefix: The cache prefix to invalidate
        pattern: Pattern to match keys (default: "*" for all keys with prefix)
    """
    try:
        # Find keys matching the pattern
        keys = await async_redis_client.keys(f"{prefix}:{pattern}")
        if keys:
            # Delete all matching keys
            await async_redis_client.delete(*keys)
            logger.debug(f"Invalidated {len(keys)} cache entries with prefix {prefix}")
    except redis.RedisError as e:
        logger.error(f"Redis error in invalidate_cache: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in invalidate_cache: {str(e)}")


def clear_all_cache():
    """Clear all cache entries in the Redis database"""
    try:
        redis_client.flushdb()
        logger.info("Cleared all cache entries")
    except redis.RedisError as e:
        logger.error(f"Redis error in clear_all_cache: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in clear_all_cache: {str(e)}")


def cache_health_check() -> Tuple[bool, str]:
    """
    Check if Redis cache is working properly

    Note: This function uses the synchronous Redis client for health checks
    since it's called from synchronous code in the health check module.
    """
    try:
        # Set a test value
        test_key = "health:check"
        test_value = {"status": "ok", "timestamp": "now"}
        redis_client.setex(test_key, 10, json.dumps(test_value))

        # Get the value back
        result = redis_client.get(test_key)
        if result:
            return True, "Cache is healthy"
        return False, "Cache set succeeded but get failed"
    except redis.RedisError as e:
        return False, f"Redis error: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


async def async_cache_health_check() -> Tuple[bool, str]:
    """
    Check if Redis cache is working properly using the async client

    This function uses the asynchronous Redis client for health checks
    and should be used in async code.
    """
    try:
        # Set a test value
        test_key = "health:check:async"
        test_value = {"status": "ok", "timestamp": "now"}
        await async_redis_client.setex(test_key, 10, json.dumps(test_value))

        # Get the value back
        result = await async_redis_client.get(test_key)
        if result:
            return True, "Cache is healthy"
        return False, "Cache set succeeded but get failed"
    except redis.RedisError as e:
        return False, f"Redis error: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"

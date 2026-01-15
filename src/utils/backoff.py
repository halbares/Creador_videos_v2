"""
Sistema de retry y rate limiting para APIs externas.
Implementa exponential backoff y control de tasa de peticiones.
"""

import time
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
from typing import Callable, Optional, Type

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    exceptions: tuple = (Exception,),
):
    """
    Decorador para reintentar funciones con exponential backoff.
    
    Args:
        max_attempts: Número máximo de intentos
        min_wait: Tiempo mínimo de espera entre intentos (segundos)
        max_wait: Tiempo máximo de espera entre intentos (segundos)
        exceptions: Tupla de excepciones a capturar
        
    Returns:
        Decorador configurado
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(exceptions),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )


class RateLimiter:
    """
    Rate limiter por endpoint para controlar peticiones a APIs.
    
    Implementa un algoritmo de token bucket simple.
    """
    
    def __init__(self):
        """Inicializa el rate limiter."""
        self._last_request: dict[str, datetime] = defaultdict(
            lambda: datetime.min
        )
        self._request_counts: dict[str, int] = defaultdict(int)
        self._limits: dict[str, dict] = {
            # Límites por defecto
            "default": {"requests": 60, "period_seconds": 60},
            "openrouter": {"requests": 100, "period_seconds": 60},
            "reddit": {"requests": 60, "period_seconds": 60},
            "pexels": {"requests": 200, "period_seconds": 3600},  # 200/hora
            "youtube": {"requests": 100, "period_seconds": 3600},
        }
    
    def set_limit(self, endpoint: str, requests: int, period_seconds: int) -> None:
        """
        Configura un límite para un endpoint.
        
        Args:
            endpoint: Nombre del endpoint
            requests: Número máximo de peticiones
            period_seconds: Período en segundos
        """
        self._limits[endpoint] = {
            "requests": requests,
            "period_seconds": period_seconds
        }
    
    def _get_limit(self, endpoint: str) -> dict:
        """Obtiene el límite para un endpoint (o el default)."""
        return self._limits.get(endpoint, self._limits["default"])
    
    def wait_if_needed(self, endpoint: str) -> float:
        """
        Espera si es necesario para cumplir con el rate limit.
        
        Args:
            endpoint: Nombre del endpoint
            
        Returns:
            Tiempo esperado en segundos
        """
        limit = self._get_limit(endpoint)
        now = datetime.now()
        
        # Verificar si necesitamos resetear el contador
        period = timedelta(seconds=limit["period_seconds"])
        if now - self._last_request[endpoint] > period:
            self._request_counts[endpoint] = 0
        
        # Verificar si hemos alcanzado el límite
        if self._request_counts[endpoint] >= limit["requests"]:
            # Calcular tiempo de espera
            time_since_first = now - self._last_request[endpoint]
            wait_time = (period - time_since_first).total_seconds()
            
            if wait_time > 0:
                logger.info(f"Rate limit alcanzado para {endpoint}. Esperando {wait_time:.1f}s")
                time.sleep(wait_time)
                self._request_counts[endpoint] = 0
                return wait_time
        
        # Registrar esta petición
        if self._request_counts[endpoint] == 0:
            self._last_request[endpoint] = now
        self._request_counts[endpoint] += 1
        
        return 0.0
    
    def get_remaining(self, endpoint: str) -> int:
        """
        Obtiene el número de peticiones restantes.
        
        Args:
            endpoint: Nombre del endpoint
            
        Returns:
            Número de peticiones restantes
        """
        limit = self._get_limit(endpoint)
        return max(0, limit["requests"] - self._request_counts[endpoint])
    
    def reset(self, endpoint: Optional[str] = None) -> None:
        """
        Resetea los contadores.
        
        Args:
            endpoint: Endpoint específico o None para resetear todos
        """
        if endpoint:
            self._request_counts[endpoint] = 0
            self._last_request[endpoint] = datetime.min
        else:
            self._request_counts.clear()
            self._last_request.clear()


def rate_limited(endpoint: str, rate_limiter: Optional[RateLimiter] = None):
    """
    Decorador para aplicar rate limiting a una función.
    
    Args:
        endpoint: Nombre del endpoint
        rate_limiter: Instancia de RateLimiter (crea una global si no se proporciona)
        
    Returns:
        Decorador configurado
    """
    _rate_limiter = rate_limiter or RateLimiter()
    
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _rate_limiter.wait_if_needed(endpoint)
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Instancia global de rate limiter
global_rate_limiter = RateLimiter()


class APIError(Exception):
    """Error genérico de API."""
    pass


class RateLimitError(APIError):
    """Error cuando se excede el rate limit."""
    pass


class AuthenticationError(APIError):
    """Error de autenticación con la API."""
    pass

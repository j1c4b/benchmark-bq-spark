#!/usr/bin/env python3
"""
Performance Measurement Decorators

Decorators for automatically capturing performance metrics
during data generation, loading, and processing operations.
"""

import time
import functools
import logging
from typing import Callable, Any, Dict, Tuple
from .metrics_collector import MetricsCollector, PerformanceMetrics

logger = logging.getLogger(__name__)


def measure_performance(operation_name: str = None):
    """
    Decorator to automatically measure function execution performance.
    
    Args:
        operation_name: Name for the operation being measured
    
    Returns:
        Decorated function that captures performance metrics
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Tuple[Any, PerformanceMetrics]:
            op_name = operation_name or func.__name__
            collector = MetricsCollector()
            
            logger.info(f"🔍 Starting performance measurement for: {op_name}")
            
            # Execute function with monitoring
            result, perf_metrics, success = collector.measure_execution_time(func, *args, **kwargs)
            
            if success and perf_metrics:
                logger.info(f"✅ {op_name} completed in {perf_metrics.execution_time_seconds:.2f}s")
                logger.info(f"📊 CPU: {perf_metrics.cpu_percent_avg:.1f}% avg, {perf_metrics.cpu_percent_max:.1f}% max")
                logger.info(f"💾 Memory: {perf_metrics.memory_mb_avg:.1f}MB avg, {perf_metrics.memory_mb_peak:.1f}MB peak")
            else:
                logger.error(f"❌ {op_name} failed or metrics collection failed")
            
            # Return both result and metrics
            return result, perf_metrics
        
        return wrapper
    return decorator


def benchmark_data_generation(func: Callable) -> Callable:
    """Specialized decorator for data generation benchmarking."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return measure_performance("Data Generation")(func)(*args, **kwargs)
    return wrapper


def benchmark_data_load(func: Callable) -> Callable:
    """Specialized decorator for data loading benchmarking.""" 
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return measure_performance("Data Load")(func)(*args, **kwargs)
    return wrapper


def benchmark_analytics(func: Callable) -> Callable:
    """Specialized decorator for analytics processing benchmarking."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return measure_performance("Analytics Processing")(func)(*args, **kwargs)
    return wrapper


# Example usage functions to demonstrate decorator usage
if __name__ == "__main__":
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    @measure_performance("Sample Operation")
    def sample_operation(duration: float = 1.0):
        """Sample function to demonstrate performance measurement."""
        time.sleep(duration)
        return f"Operation completed after {duration}s"
    
    # Test the decorator
    result, metrics = sample_operation(2.0)
    print(f"Result: {result}")
    if metrics:
        print(f"Execution time: {metrics.execution_time_seconds:.2f}s")
        print(f"Peak memory: {metrics.memory_mb_peak:.2f}MB")
"""M4 production measurements with explicit populations and reportability."""

from peanalyzer.metrics.models import MetricResult
from peanalyzer.metrics.production import collect_metrics, run_metrics

__all__ = ["MetricResult", "collect_metrics", "run_metrics"]

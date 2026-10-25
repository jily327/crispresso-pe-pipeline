"""Explicit result-family dispatch; existing PE validators remain unchanged."""
from peanalyzer.statistical_models import StatisticsResult
from peanalyzer.reporting_models import ReportManifest
from peanalyzer.metrics import MetricResult


def statistics_model(raw):
    if isinstance(raw, dict) and raw.get('statistics_contract_version')=='indel-nuclease-stats-v1':
        from peanalyzer.nuclease.models import NucleaseStatisticsResult
        return NucleaseStatisticsResult
    return StatisticsResult


def metric_model(raw):
    if isinstance(raw, dict) and raw.get('metric_contract_version')=='indel-nuclease-v1':
        from peanalyzer.nuclease.models import NucleaseMetricResult
        return NucleaseMetricResult
    return MetricResult


def report_model(raw):
    if isinstance(raw, dict) and raw.get('report_contract_version')=='indel-nuclease-report-v1':
        from peanalyzer.nuclease.models import NucleaseReportManifest
        return NucleaseReportManifest
    return ReportManifest

"""Workbook rows from stored biological summaries for either scientific mode."""


def biological_summary_rows(view):
    observations = {observation.series_id: observation for observation in view.observations}
    rows = [("Target", "Copy", "Policy", "Metric", "Condition", "Expected samples",
             "Reportable samples", "Mean", "Sample SD", "Minimum", "Maximum", "Median",
             "Pooled read-weighted fraction", "Executed contrast minimum")]
    for group in view.groups:
        series = observations[group.series_id]
        rows.append((series.target, series.copy_name, series.policy_id, group.metric_name,
                     group.condition, int(group.expected_n), int(group.reportable_n),
                     group.mean, group.sample_sd, group.minimum, group.maximum, group.median,
                     group.pooled_read_fraction, view.minimum_biological_replicates))
    return rows

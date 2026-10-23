"""Deterministic presentation of completed M5 values; no biological inference."""
import csv
import hashlib
import html
from importlib.resources import files
import io
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.ticker import PercentFormatter

from peanalyzer import __version__
from peanalyzer.reporting_models import DEFAULT_TITLE, ReportArtifact, ReportManifest, ReportingError
from peanalyzer.statistical_models import ContrastResult, GroupSummary, Observation, Series, StatisticsResult

PALETTE = ("#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9", "#000000")
SERIES_FIELDS = tuple(Series.model_fields)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReportingError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _nonfinite(value):
    raise ReportingError(f"nonfinite JSON value: {value}")


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ReportingError("nonfinite JSON number")
    return number


def load_result(data):
    """Parse the same immutable bytes used for source hashing and copying."""
    try:
        raw = json.loads(data, object_pairs_hook=_unique, parse_constant=_nonfinite, parse_float=_finite_float)
        return StatisticsResult.model_validate(raw)
    except (ValueError, UnicodeError, TypeError) as exc:
        raise ReportingError(f"invalid M5 result: {exc}") from exc


def condition_key(row):
    return row["editor"], row["treatment"], row["dpi"]


def condition_label(row):
    return f'{row["editor"]} | {row["treatment"]} | {row["dpi"]} dpi'


def identity(row):
    return {key: row[key] for key in SERIES_FIELDS}


def series_key(row):
    return (row["target_name"], row["metric_name"], row["population_scope"],
            row["copy_name"] or "", row["policy_id"] or "", canonical(row["policy_definition"]),
            row["routing_conditioned"])


def metric_label(row):
    population = f'Copy {row["copy_name"]}' if row["copy_name"] is not None else "Target"
    if row["policy_id"] is not None:
        return f'{population} PE family ({row["policy_id"]})'
    metric = row["metric_name"]
    if metric.endswith("crispresso_native_pe"):
        return population + " CRISPResso native PE"
    if metric.endswith("precise_pe"):
        return population + " precise PE"
    return population + " " + metric


def figure_id(kind, value):
    prefix = "series" if kind == "samples" else "family"
    return f"{prefix}-{digest(canonical(value).encode())}-{kind}"


def _ordered(value):
    """Canonicalize inventory order for presentation without changing values."""
    if isinstance(value, dict):
        return {key: json.loads(canonical(item)) if key == "policy_definition" else _ordered(item)
                for key, item in sorted(value.items())}
    if isinstance(value, list):
        return sorted((_ordered(item) for item in value), key=canonical)
    return value


def build_report_spec(result, title=DEFAULT_TITLE):
    """Pure rendering specification. All scientific numbers are direct M5 fields."""
    result = StatisticsResult.model_validate(result.model_dump(mode="json"))
    if not isinstance(title, str) or not title.strip():
        raise ReportingError("title must be nonblank text")
    observations = sorted((_ordered(r.model_dump(mode="json")) for r in result.observations),
                          key=lambda r: (series_key(r), condition_key(r), r["sample_name"], r["sample_id"], canonical(r)))
    groups = sorted((_ordered(r.model_dump(mode="json")) for r in result.group_summaries),
                    key=lambda r: (series_key(r), condition_key(r["condition"]), canonical(r)))
    contrasts = sorted((_ordered(r.model_dump(mode="json")) for r in result.contrasts),
                       key=lambda r: (r["family_id"], r["contrast_id"]))
    families = sorted((_ordered(r.model_dump(mode="json")) for r in result.multiple_testing_families),
                      key=lambda r: r["family_id"])
    definitions = {series_key(r): identity(r) for r in [*observations, *groups]}
    conditions = {condition_key(r): {k: r[k] for k in ("editor", "treatment", "dpi")} for r in observations}
    conditions.update({condition_key(g["condition"]): g["condition"] for g in groups})
    condition_colors = {key: PALETTE[i % len(PALETTE)] for i, key in enumerate(sorted(conditions))}
    series = []
    for key, definition in sorted(definitions.items()):
        rows = [r for r in observations if series_key(r) == key]
        summaries = [g for g in groups if series_key(g) == key]
        local_conditions = {condition_key(r): conditions[condition_key(r)] for r in rows}
        local_conditions.update({condition_key(g["condition"]): g["condition"] for g in summaries})
        ordered_conditions = [local_conditions[k] for k in sorted(local_conditions)]
        points, means = [], []
        for x, condition in enumerate(ordered_conditions):
            ck = condition_key(condition)
            members = [r for r in rows if condition_key(r) == ck and r["status"] == "REPORTABLE"]
            for index, row in enumerate(members):
                offset = 0.0 if len(members) == 1 else 0.36 * (index / (len(members) - 1) - 0.5)
                points.append(dict(sample_name=row["sample_name"], condition=condition, x=x+offset,
                    fraction=row["fraction"], color=condition_colors[ck], source_field="Observation.fraction"))
            for summary in summaries:
                if condition_key(summary["condition"]) == ck and summary["mean_biological_sample_fraction"] is not None:
                    means.append(dict(condition=condition, x=x, fraction=summary["mean_biological_sample_fraction"],
                                      source_field="GroupSummary.mean_biological_sample_fraction"))
        series.append(dict(identity=definition, figure_id=figure_id("samples", definition),
                           conditions=ordered_conditions, points=points, means=means, summaries=summaries))
    effects = [dict(family_id=f["family_id"], figure_id=figure_id("contrasts", {"family_id": f["family_id"]}),
                    contrasts=[c for c in contrasts if c["family_id"] == f["family_id"] and c["status"] == "REPORTABLE"])
               for f in families]
    sample_ids = {a["sample_name"] for g in groups for a in g["sample_assessments"]} | {r["sample_name"] for r in observations}
    return dict(title=title, observations=observations, group_summaries=groups, contrasts=contrasts,
        families=families, series=series, effects=effects,
        unused_metadata_sample_ids=sorted(result.unused_metadata_sample_ids),
        inventory=dict(biological_samples=len(sample_ids), conditions=len(conditions),
            targets=len({r["target_name"] for r in definitions.values()}), metric_series=len(series),
            copy_series=sum(r["copy_name"] is not None for r in definitions.values()),
            family_policy_series=sum(r["policy_id"] is not None for r in definitions.values()),
            contrasts=len(contrasts), multiple_testing_families=len(families)))


def percentage(value):
    return "" if value is None else f"{value * 100:.2f}%"


def _cell(value):
    return canonical(value) if isinstance(value, (dict, list)) else "" if value is None else str(value)


def write_tables(spec, root):
    root.mkdir()
    for name, model in (("observations", Observation), ("group_summaries", GroupSummary), ("contrasts", ContrastResult)):
        with (root / f"{name}.tsv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(model.model_fields), delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows({key: _cell(value) for key, value in row.items()} for row in spec[name])


def _series_caption(row):
    text = (f'{row["target_name"]} — {metric_label(row)}; metric_name={row["metric_name"]}; '
            f'population_scope={row["population_scope"]}; routing_conditioned={str(row["routing_conditioned"]).lower()}. ')
    if row["copy_name"] is not None:
        text += "Copy-level measurements are conditioned on qualified routing and are not whole-target fractions. "
    if row["policy_id"] is not None:
        text += f'policy_id={row["policy_id"]}; policy_definition={canonical(row["policy_definition"])}. '
    return text


def render_svg(item, kind):
    """Render stored values only, with deterministic SVG IDs and literal text."""
    settings = {"svg.hashsalt": item["figure_id"], "svg.fonttype": "none", "text.usetex": False,
                "text.parse_math": False, "font.family": "DejaVu Sans", "font.size": 10,
                "axes.spines.top": False, "axes.spines.right": False,
                "figure.facecolor": "white", "axes.facecolor": "white"}
    with matplotlib.rc_context(matplotlib.rcParamsDefault), matplotlib.rc_context(settings):
        fig = None
        try:
            if kind == "samples":
                fig, ax = plt.subplots(figsize=(max(7, 1.6 * len(item["conditions"])), 5), layout="constrained")
                for point in item["points"]:
                    ax.scatter(point["x"], point["fraction"], s=35, color=point["color"], zorder=3)
                for mean in item["means"]:
                    ax.scatter(mean["x"], mean["fraction"], marker="_", s=350, linewidths=2.5, color="black", zorder=4)
                ax.set_xticks(range(len(item["conditions"])), [condition_label(c) for c in item["conditions"]], rotation=20, ha="right")
                ax.set_ylim(0, 1)
                ax.set_xlim(-0.5, max(0.5, len(item["conditions"]) - 0.5))
                ax.yaxis.set_major_formatter(PercentFormatter(1))
                ax.set_ylabel("Biological-sample fraction")
                ax.set_xlabel("Biological condition (editor | treatment | dpi)")
                ax.set_title(item["identity"]["target_name"] + " — " + metric_label(item["identity"]))
                ax.scatter([], [], color=PALETTE[0], s=35, label="Biological samples")
                ax.scatter([], [], color="black", marker="_", s=350, label="Unweighted biological-sample mean")
                ax.legend(loc="upper left", bbox_to_anchor=(0, 1.25), frameon=False, fontsize=9)
            else:
                rows = item["contrasts"]
                fig, ax = plt.subplots(figsize=(10, max(3, 1.0 * len(rows))), layout="constrained")
                ax.scatter([r["difference_in_biological_sample_fraction"] for r in rows], range(len(rows)), color=PALETTE[0], s=40)
                ax.set_yticks(range(len(rows)), [r["contrast_id"] + " | " + r["target_name"] + " | " + metric_label(r) for r in rows])
                ax.invert_yaxis()
                ax.set_xlim(-1, 1)
                ax.axvline(0, color="#777777", linewidth=0.8)
                ax.set_xlabel("B − A in biological-sample fraction")
                ax.set_title("Multiple-testing family: " + item["family_id"])
            stream = io.StringIO()
            fig.savefig(stream, format="svg", metadata={"Date": None, "Creator": "peanalyzer " + __version__})
            svg = stream.getvalue()
            svg = svg[svg.index("<svg "):]
            label = (item["identity"]["target_name"] + " " + metric_label(item["identity"])) if kind == "samples" else "Contrast family " + item["family_id"]
            svg = svg.replace("<svg ", '<svg role="img" aria-label="' + html.escape(label, quote=True) + '" ', 1)
            try:
                ET.fromstring(svg)
            except ET.ParseError as exc:
                raise ReportingError(f"INVALID_GENERATED_SVG: figure {item['figure_id']} is not well-formed XML") from exc
            return svg
        finally:
            if fig is not None:
                plt.close(fig)


def _table(caption, rows, columns):
    escape = html.escape
    parts = ['<div class="table-scroll"><table><caption>' + escape(caption) + '</caption><thead><tr>']
    parts.extend('<th scope="col">' + escape(key) + '</th>' for key in columns)
    parts.append('</tr></thead><tbody>')
    for row in rows:
        parts.append('<tr>')
        for key in columns:
            value = "See source/result.json" if key == "source_result" else _cell(row.get(key))
            parts.append('<td>' + escape(value, quote=True) + '</td>')
        parts.append('</tr>')
    parts.append('</tbody></table></div>')
    return ''.join(parts)


def render_html(spec, source_hash, figures):
    escape = html.escape
    parts = ['<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
             '<title>' + escape(spec['title']) + '</title><style>',
             files('peanalyzer.reporting_resources').joinpath('report.css').read_text(encoding='utf-8'),
             '</style></head><body><main><h1>' + escape(spec['title']) + '</h1>',
             '<p>Presentation of a completed M5 result. Scientific authority: <a href="source/result.json">source/result.json</a>.</p>',
             '<p>Source SHA-256: <code>' + source_hash + '</code></p><h2>Study inventory</h2>',
             _table('Presentation inventory', [spec['inventory']], list(spec['inventory'])),
             '<h2>Measurement definitions</h2><p>Target measurements describe the target population; copy measurements describe qualified, routing-conditioned copy populations. Native PE follows CRISPResso native classification; precise PE uses exact WT/PE product definitions. Family metrics preserve their named policy and normalized definition. Biological samples are the units of inference. POOLED READ-WEIGHTED DESCRIPTIVE FRACTION is descriptive only.</p>',
             '<h2>Biological sample summaries</h2>']
    summary_rows = [dict(target=g['target_name'], metric=metric_label(g), condition=condition_label(g['condition']),
                         mean=percentage(g['mean_biological_sample_fraction']), expected=g['expected_sample_count'],
                         REPORTABLE=g['reportable_count'], BLOCKED=g['blocked_count'], NOT_ASSESSABLE=g['not_assessable_count'],
                         MISSING_METRIC=g['missing_metric_count']) for g in spec['group_summaries']]
    parts.append(_table('Stored unweighted biological-sample means (display percentages)', summary_rows,
                        ['target', 'metric', 'condition', 'mean', 'expected', 'REPORTABLE', 'BLOCKED', 'NOT_ASSESSABLE', 'MISSING_METRIC']))
    parts.append('<h2>Sample-level figures</h2>')
    for item in spec['series']:
        caption = _series_caption(item['identity'])
        parts.append('<h3>' + escape(item['identity']['target_name'] + ' — ' + metric_label(item['identity'])) + '</h3>')
        if item['points']:
            parts.extend(['<figure>', figures[item['figure_id']], '<figcaption>', escape(caption),
                          'Points = biological samples; summary marker = stored unweighted biological-sample mean. Nonreportable samples have no numerical point.</figcaption></figure>'])
        else:
            parts.append('<p>' + escape(caption) + 'No reportable numerical observations.</p>')
    parts.append('<h2>Statistical contrasts</h2>')
    if not spec['contrasts']:
        parts.append('<p>No statistical contrasts in this M5 result.</p>')
    for item in spec['effects']:
        parts.append('<h3>Multiple-testing family: ' + escape(item['family_id']) + '</h3>')
        if item['contrasts']:
            parts.extend(['<figure>', figures[item['figure_id']], '<figcaption>Effect is B − A in biological-sample fraction. Positive values mean a larger fraction in B than A. p-values are exact M5 values; q-values are M5 family-scoped Benjamini-Hochberg values. No confidence intervals are estimated.'])
            for row in item['contrasts']:
                parts.append('<p>' + escape(row['contrast_id'] + ': ' + _series_caption(row) +
                    'A = ' + condition_label(row['group_a']) + '; B = ' + condition_label(row['group_b']) +
                    '; effect=' + str(row['difference_in_biological_sample_fraction']) + '; p=' + str(row['p_value']) + '; q=' + str(row['q_value'])) + '</p>')
            parts.append('</figcaption></figure>')
        else:
            parts.append('<p>No reportable numerical effects in this family.</p>')
    contrast_display = [dict(contrast_id=c['contrast_id'], family_id=c['family_id'], pairing_mode=c['pairing_mode'],
        expected_n_A=c['expected_group_a_count'], expected_n_B=c['expected_group_b_count'],
        used_n_A=c['used_group_a_count'], used_n_B=c['used_group_b_count'],
        complete_block_count=len(c['complete_blocks']), complete_blocks=c['complete_blocks'],
        excluded_blocks=c['excluded_blocks'], status=c['status'], reason_codes=c['reason_codes']) for c in spec['contrasts']]
    parts.append(_table('Contrast design and reportability', contrast_display,
        ['contrast_id', 'family_id', 'pairing_mode', 'expected_n_A', 'expected_n_B', 'used_n_A', 'used_n_B',
         'complete_block_count', 'complete_blocks', 'excluded_blocks', 'status', 'reason_codes']))
    parts.append(_table('Declared multiple-testing families (M5)', spec['families'], ['family_id', 'method', 'contrast_ids', 'valid_contrast_ids', 'valid_test_count']))
    parts.append('<h2>Reportability / missingness</h2>')
    parts.append(_table('Expected and numerical sample inventories', summary_rows,
                        ['target', 'metric', 'condition', 'expected', 'REPORTABLE', 'BLOCKED', 'NOT_ASSESSABLE', 'MISSING_METRIC']))
    assessments = [dict(**identity(g), condition=g['condition'], **a) for g in spec['group_summaries'] for a in g['sample_assessments']]
    parts.append(_table('Sample assessments and reason codes', assessments, [*SERIES_FIELDS, 'condition', 'sample_name', 'biological_replicate', 'block_id', 'paired', 'status', 'reason_codes']))
    parts.append('<p>Unused metadata sample IDs: ' + escape(canonical(spec['unused_metadata_sample_ids'])) + '</p><h2>Detailed tables</h2>')
    for name, model in (("observations", Observation), ("group_summaries", GroupSummary), ("contrasts", ContrastResult)):
        parts.append('<p><a href="tables/' + name + '.tsv">Download ' + name + '.tsv</a></p>')
        parts.append(_table(name, spec[name], list(model.model_fields)))
    parts.extend(['<h2>Reproducibility</h2><p>Package version: ', escape(__version__),
                  '; report contract: m6-v1; source statistics contract: m5-v1; inventoried artifacts: ', str(5+len(figures)),
                  ' (manifest excluded). Source SHA-256: <code>', source_hash,
                  '</code>. Scientific values come from the copied M5 result.json. Tables are convenience exports; percentage rounding is presentation only. SVGs are embedded for offline use and also exported separately. No source filesystem links are inferred.</p>',
                  '<h2>Limitations</h2><ul><li>No automatic biological interpretation.</li><li>No confidence intervals in M5/M6; small-n exact p-values may be coarse.</li><li>Copy metrics are routing-conditioned.</li><li>Nonreportable measurements remain nonnumerical.</li><li>M4 upstream observability and read-geometry limitations remain upstream.</li><li>CRISPResso report links are deferred: the current source contract provides no portable verified links.</li></ul></main></body></html>\n'])
    return ''.join(parts)


def generate_report(*, result_path, output, title=DEFAULT_TITLE):
    """Publish a new portable report with exact source bytes and verified hashes."""
    source = Path(result_path)
    output = Path(output).absolute()
    stage = None
    lock = output.with_name('.' + output.name + '.m6-lock')
    locked = False
    try:
        data = source.read_bytes()
        source_hash = digest(data)
        spec = build_report_spec(load_result(data), title)
        if output.exists() or output.is_symlink():
            raise ReportingError(f"output already exists: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise ReportingError(f"output publication already in progress: {output}") from exc
        locked = True
        os.close(descriptor)
        stage = Path(tempfile.mkdtemp(prefix='.' + output.name + '.incomplete-', dir=output.parent))
        (stage / 'source').mkdir()
        (stage / 'source/result.json').write_bytes(data)
        write_tables(spec, stage / 'tables')
        (stage / 'figures').mkdir()
        figures, metadata = {}, {}
        for kind, items in (("samples", spec['series']), ("contrasts", spec['effects'])):
            for item in items:
                if not item['points' if kind == 'samples' else 'contrasts']:
                    continue
                fid = item['figure_id']
                figures[fid] = render_svg(item, kind)
                relative = 'figures/' + fid + '.svg'
                (stage / relative).write_text(figures[fid], encoding='utf-8')
                metadata[relative] = dict(figure_id=fid, figure_type=kind)
                if kind == 'samples':
                    metadata[relative].update(item['identity'])
                else:
                    metadata[relative]['family_id'] = item['family_id']
        (stage / 'report.html').write_text(render_html(spec, source_hash, figures), encoding='utf-8')
        artifacts = []
        for path in sorted(p for p in stage.rglob('*') if p.is_file()):
            relative = path.relative_to(stage).as_posix()
            kind, media = {'.html': ('html', 'text/html'), '.json': ('source', 'application/json'),
                           '.tsv': ('table', 'text/tab-separated-values'), '.svg': ('figure', 'image/svg+xml')}[path.suffix]
            artifacts.append(ReportArtifact(path=relative, sha256=digest(path.read_bytes()), artifact_kind=kind,
                                            media_type=media, **metadata.get(relative, {})))
        manifest = ReportManifest(schema_version=1, report_contract_version='m6-v1', package_version=__version__,
            source_statistics_contract_version='m5-v1', source_result_sha256=source_hash, title=title, artifacts=artifacts)
        (stage / 'report_manifest.json').write_text(json.dumps(manifest.model_dump(mode='json'), sort_keys=True, indent=2) + '\n', encoding='utf-8')
        if digest((stage / 'source/result.json').read_bytes()) != source_hash:
            raise ReportingError('copied source hash mismatch')
        if digest(source.read_bytes()) != source_hash:
            raise ReportingError('source result changed during report construction')
        if output.exists() or output.is_symlink():
            raise ReportingError(f"output already exists: {output}")
        stage.rename(output)
        return manifest
    except (OSError, ValueError, TypeError) as exc:
        if isinstance(exc, ReportingError):
            raise
        raise ReportingError(str(exc)) from exc
    finally:
        if stage is not None and stage.exists():
            shutil.rmtree(stage)
        if locked:
            lock.unlink()

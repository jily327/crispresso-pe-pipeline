"""Bounded output handles and the authoritative barcode matrix plus visualization."""

import csv
import gzip
import os
from collections import Counter, OrderedDict
from contextlib import ExitStack
from pathlib import Path

from peanalyzer.fastq import FastqRecord
from peanalyzer.validation import sample_output_names


class SampleWriter:
    """LRU of paired gzip handles; evicted files reopen as valid gzip members."""

    def __init__(self, directory: Path, sample_ids: list[str], max_open_pairs: int):
        self.directory = directory
        self.names = sample_output_names(sample_ids)
        self.counts = dict.fromkeys(sample_ids, 0)
        self.record_counts = {sample: [0, 0] for sample in sample_ids}
        self.identities = {}
        self.max_open_pairs = max_open_pairs
        self.handles = OrderedDict()

    def _open(self, sample: str):
        if sample in self.handles:
            self.handles.move_to_end(sample)
            return self.handles[sample][1]
        if len(self.handles) >= self.max_open_pairs:
            _, (stack, _) = self.handles.popitem(last=False)
            stack.close()
        stack = ExitStack()
        try:
            handles = []
            for filename in self.names[sample]:
                path = self.directory / filename
                # r+b cannot create a missing file during LRU reopening.
                raw = stack.enter_context(path.open("r+b" if filename in self.identities else "xb"))
                stat = os.fstat(raw.fileno())
                identity = (stat.st_dev, stat.st_ino)
                if path.is_symlink() or identity != self.identities.get(filename, identity):
                    raise OSError(f"output file replaced during run: {filename}")
                self.identities[filename] = identity
                raw.seek(0, os.SEEK_END)
                handles.append(stack.enter_context(gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0)))
            self.handles[sample] = stack, handles
        except BaseException:
            stack.close()
            raise
        return handles

    def write(self, sample: str, forward: FastqRecord, reverse: FastqRecord) -> None:
        if sample not in self.counts:
            raise ValueError(f"unknown output sample {sample}")
        handles = self._open(sample)
        for index, (handle, record) in enumerate(zip(handles, (forward, reverse))):
            data = record.to_bytes()
            if handle.write(data) != len(data):
                raise OSError(f"short FASTQ write: {sample} R{index + 1}")
            self.record_counts[sample][index] += 1
        self.counts[sample] += 1

    def close(self) -> None:
        failure = None
        while self.handles:
            _, (stack, _) = self.handles.popitem(last=False)
            try:
                stack.close()
            except BaseException as exc:
                failure = failure or exc
        if failure is not None:
            raise failure

    def ensure_empty_samples(self) -> None:
        for sample, count in self.counts.items():
            if count == 0:
                self._open(sample)
        self.close()

    def verify_files(self) -> None:
        if self.handles:
            raise OSError("output verification requires closed writers")
        if set(self.identities) != {name for pair in self.names.values() for name in pair}:
            raise OSError("not all expected sample FASTQs were created")
        if {path.name for path in self.directory.iterdir()} != set(self.identities):
            raise OSError("output file inventory differs from files created by this run")
        for filename, identity in self.identities.items():
            path = self.directory / filename
            stat = path.stat()
            if path.is_symlink() or (stat.st_dev, stat.st_ino) != identity or stat.st_size == 0:
                raise OSError(f"output file missing, replaced or empty: {filename}")


def write_qc_tables(directory: Path, catalog, matrix: Counter, barcode_counts: Counter, corrected: Counter, expected: dict) -> None:
    forward_ids, reverse_ids = list(catalog.ends["forward"]), list(catalog.ends["reverse"])
    with (directory / "barcode_counts.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["direction", "barcode_id", "sequence", "recognized_read_pairs", "exact_read_pairs", "corrected_read_pairs"])
        for direction, entries in catalog.ends.items():
            for barcode_id, seq in entries.items():
                total = barcode_counts[direction, barcode_id]
                rescued = corrected[direction, barcode_id]
                writer.writerow([direction, barcode_id, seq, total, total - rescued, rescued])
    with (directory / "barcode_pair_matrix.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["forward_barcode_id", *reverse_ids])
        writer.writerows([f, *(matrix[f, r] for r in reverse_ids)] for f in forward_ids)


def write_heatmap(directory: Path, catalog, matrix: Counter, expected: dict) -> None:
    forward_ids, reverse_ids = list(catalog.ends["forward"]), list(catalog.ends["reverse"])
    # Object-oriented Agg backend works headlessly and does not alter pyplot state.
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.patches import Rectangle

    fig = Figure(figsize=(max(5, len(reverse_ids) * .5), max(4, len(forward_ids) * .4)), layout="constrained")
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    data = [[matrix[f, r] for r in reverse_ids] for f in forward_ids]
    plotted = ax.imshow(data, cmap="Blues", aspect="auto", vmin=0)
    ax.set_xticks(range(len(reverse_ids)), reverse_ids, rotation=45)
    ax.set_yticks(range(len(forward_ids)), forward_ids)
    ax.set(xlabel="Reverse barcode", ylabel="Forward barcode", title="Recognized barcode pairs (orange outline = expected)")
    for y, forward in enumerate(forward_ids):
        for x, reverse in enumerate(reverse_ids):
            if (forward, reverse) in expected:
                ax.add_patch(Rectangle((x - .5, y - .5), 1, 1, fill=False, edgecolor="darkorange", linewidth=2))
            if len(forward_ids) * len(reverse_ids) <= 200:
                ax.text(x, y, str(matrix[forward, reverse]), ha="center", va="center", fontsize=7)
    fig.colorbar(plotted, ax=ax, label="Read pairs")
    fig.savefig(directory / "barcode_pair_heatmap.png", dpi=140)


def verify_matrix_file(directory: Path, catalog, matrix: Counter) -> None:
    """Read the small authoritative CSV back; do not reread the FASTQs."""
    forward_ids, reverse_ids = list(catalog.ends["forward"]), list(catalog.ends["reverse"])
    with (directory / "barcode_pair_matrix.csv").open(newline="") as handle:
        rows = list(csv.reader(handle))
    expected = [["forward_barcode_id", *reverse_ids],
                *[[f, *(str(matrix[f, r]) for r in reverse_ids)] for f in forward_ids]]
    if rows != expected:
        raise OSError("on-disk barcode matrix differs from reconciled counts")

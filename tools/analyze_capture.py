#!/usr/bin/env python3
"""Validate a raw capture and summarize byte changes without assuming a protocol."""
import argparse
import collections
import json
from pathlib import Path


def load(path):
    records = []
    previous_ns = -1
    with path.open() as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                row = json.loads(line)
                data = bytes.fromhex(row['hex'])
                timestamp = row['elapsed_ns']
                if not data or len(data) != row['length']:
                    raise ValueError('invalid report length')
                if not isinstance(timestamp, int) or timestamp < previous_ns:
                    raise ValueError('timestamps must be monotonic nonnegative integers')
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(f'{path}:{line_number}: {error}') from error
            previous_ns = timestamp
            records.append((timestamp, data))
    return records


def summarize(records, baseline):
    baseline_groups = collections.defaultdict(collections.Counter)
    for _, data in baseline:
        baseline_groups[(data[0], len(data))][data] += 1
    groups = collections.defaultdict(list)
    for timestamp, data in records:
        groups[(data[0], len(data))].append((timestamp, data))
    output = {'reports': len(records), 'groups': []}
    for (report_id, length), rows in sorted(groups.items()):
        reference_counts = baseline_groups.get((report_id, length))
        reference = (reference_counts.most_common(1)[0][0] if reference_counts
                     else collections.Counter(data for _, data in rows).most_common(1)[0][0])
        offsets = []
        for offset in range(1, length):
            values = collections.Counter(data[offset] for _, data in rows)
            differing = sum(count for value, count in values.items()
                            if value != reference[offset])
            if differing:
                offsets.append({'offset': offset, 'reference': reference[offset],
                                'min': min(values), 'max': max(values),
                                'distinct_values': len(values),
                                'reports_different_from_reference': differing})
        output['groups'].append({
            'report_id_hex': f'{report_id:02x}', 'length': length, 'count': len(rows),
            'unique_reports': len({data for _, data in rows}),
            'reference_source': 'baseline' if reference_counts else 'capture_mode',
            'reference_hex': reference.hex(), 'changed_offsets': offsets,
        })
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    try:
        records = load(args.capture)
        baseline = load(args.baseline) if args.baseline else []
        print(json.dumps(summarize(records, baseline), indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()

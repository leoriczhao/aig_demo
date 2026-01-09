#!/usr/bin/env python3
"""Compare simple_alu VCDs - focus on AND node signals"""

import re
from collections import defaultdict

def parse_vcd(filename):
    signals = {}
    values = defaultdict(dict)

    with open(filename, 'r') as f:
        content = f.read()

    var_pattern = r'\$var\s+\w+\s+(\d+)\s+(\S+)\s+(\S+).*?\$end'
    for match in re.finditer(var_pattern, content):
        var_id = match.group(2)
        name = match.group(3)
        name = re.sub(r'\[.*\]', '', name).strip()
        signals[var_id] = name

    dump_start = content.find('$enddefinitions')
    if dump_start == -1:
        return signals, values

    dump_content = content[dump_start:]
    current_time = 0

    for line in dump_content.split('\n'):
        line = line.strip()
        if not line or line.startswith('$'):
            continue

        if line.startswith('#'):
            try:
                current_time = int(line[1:])
            except:
                pass
            continue

        if line.startswith('b'):
            parts = line.split()
            if len(parts) >= 2:
                value = parts[0][1:]
                var_id = parts[1]
                if var_id in signals:
                    values[current_time][signals[var_id]] = value

        elif line[0] in '01xXzZ' and len(line) >= 2:
            bit_val = line[0]
            var_id = line[1:]
            if var_id in signals:
                values[current_time][signals[var_id]] = bit_val

    return signals, values

def normalize_binary(value):
    value = value.lower().replace('x', '0').replace('z', '0')
    return value.lstrip('0') or '0'

def main():
    golden = "output/vcd/simple_alu_golden.vcd"
    completed = "output/vcd/simple_alu_completed.vcd"

    print("Parsing VCDs...")
    g_sigs, g_vals = parse_vcd(golden)
    c_sigs, c_vals = parse_vcd(completed)

    print(f"Golden: {len(g_sigs)} signals, {len(g_vals)} timestamps")
    print(f"Completed: {len(c_sigs)} signals, {len(c_vals)} timestamps")

    # Focus on key signals including AND node signal
    key_signals = [
        'and_result',    # AND node signal!
        'add_result',    # Should be combinational
        'sub_result',
        'or_result',
        'xor_result',
        'result_is_zero',
        'add_carry',
        'result',        # Latch output
        'zero',
        'carry',
        'a', 'b', 'op'   # Inputs
    ]

    common_times = sorted(set(g_vals.keys()) & set(c_vals.keys()))
    print(f"Common timestamps: {len(common_times)}")

    # Compare
    print("\n" + "="*70)
    print("SIGNAL VALUE COMPARISON")
    print("="*70)

    mismatches = defaultdict(list)
    matches = 0
    total = 0

    for t in common_times:
        gv = g_vals[t]
        cv = c_vals[t]

        for sig in key_signals:
            if sig in gv and sig in cv:
                g = normalize_binary(gv[sig])
                c = normalize_binary(cv[sig])
                total += 1
                if g == c:
                    matches += 1
                else:
                    mismatches[sig].append((t, g, c))

    print(f"\nTotal comparisons: {total}")
    print(f"Matches: {matches}")
    print(f"Accuracy: {matches/total*100:.1f}%" if total > 0 else "N/A")

    if mismatches:
        print(f"\nMismatches: {sum(len(v) for v in mismatches.values())}")
        for sig, diffs in mismatches.items():
            print(f"\n  {sig}:")
            for t, g, c in diffs[:5]:
                print(f"    t={t}: golden={g} completed={c}")
            if len(diffs) > 5:
                print(f"    ... and {len(diffs)-5} more")
    else:
        print("\n✓ All values match!")

    # Sample some values
    print("\n" + "="*70)
    print("SAMPLE VALUES (focus on and_result)")
    print("="*70)

    sample_times = common_times[2:12]  # Skip reset
    for t in sample_times:
        gv = g_vals.get(t, {})
        cv = c_vals.get(t, {})

        print(f"\nTime {t}:")
        for sig in ['a', 'b', 'op', 'and_result', 'result']:
            g = normalize_binary(gv.get(sig, 'N/A')) if sig in gv else 'N/A'
            c = normalize_binary(cv.get(sig, 'N/A')) if sig in cv else 'N/A'
            match = "✓" if g == c else "✗"
            print(f"  {match} {sig:15}: golden={g:>10}  completed={c:>10}")

if __name__ == "__main__":
    main()

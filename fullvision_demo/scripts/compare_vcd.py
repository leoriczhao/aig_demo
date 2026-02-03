#!/usr/bin/env python3
"""
VCD Comparison Script
Compare golden VCD with completed VCD to verify waveform completion accuracy
"""

import sys
import re
from collections import defaultdict

def parse_vcd(filename):
    """Parse VCD file and extract signal values at each timestamp"""
    signals = {}  # var_id -> signal_name
    values = defaultdict(dict)  # timestamp -> {signal_name: value}

    with open(filename, 'r') as f:
        content = f.read()

    # Parse variable definitions
    # Match: $var wire 32 ! pc_out [31:0] $end  or  $var wire 32 ! pc_out $end
    var_pattern = r'\$var\s+\w+\s+(\d+)\s+(\S+)\s+(\S+).*?\$end'
    for match in re.finditer(var_pattern, content):
        width = int(match.group(1))
        var_id = match.group(2)
        name = match.group(3)
        # Remove array notation like [31:0]
        name = re.sub(r'\[.*\]', '', name).strip()
        signals[var_id] = name

    # Find value dump section (after $enddefinitions)
    dump_start = content.find('$enddefinitions')
    if dump_start == -1:
        return signals, values

    dump_content = content[dump_start:]

    current_time = 0

    # Parse timestamps and values
    for line in dump_content.split('\n'):
        line = line.strip()
        if not line or line.startswith('$'):
            continue

        # Timestamp
        if line.startswith('#'):
            current_time = int(line[1:])
            continue

        # Binary value: bXXXX var_id
        if line.startswith('b'):
            parts = line.split()
            if len(parts) >= 2:
                value = parts[0][1:]  # Remove 'b' prefix
                var_id = parts[1]
                if var_id in signals:
                    values[current_time][signals[var_id]] = value

        # Single bit value: 0X or 1X
        elif line[0] in '01xXzZ' and len(line) >= 2:
            bit_val = line[0]
            var_id = line[1:]
            if var_id in signals:
                values[current_time][signals[var_id]] = bit_val

    return signals, values

def normalize_binary(value):
    """Normalize binary value (remove leading zeros, handle x/z)"""
    # Replace x/z with 0 for comparison
    value = value.lower().replace('x', '0').replace('z', '0')
    # Remove leading zeros but keep at least one digit
    value = value.lstrip('0') or '0'
    return value

def compare_vcds(golden_file, completed_file, key_signals=None):
    """Compare two VCD files"""
    print(f"Parsing golden VCD: {golden_file}")
    golden_signals, golden_values = parse_vcd(golden_file)
    print(f"  Found {len(golden_signals)} signals, {len(golden_values)} timestamps")

    print(f"Parsing completed VCD: {completed_file}")
    completed_signals, completed_values = parse_vcd(completed_file)
    print(f"  Found {len(completed_signals)} signals, {len(completed_values)} timestamps")

    # Find common signals
    golden_names = set(golden_signals.values())
    completed_names = set(completed_signals.values())
    common_signals = golden_names & completed_names
    print(f"\nCommon signals: {len(common_signals)}")

    # If key_signals specified, filter to those
    if key_signals:
        common_signals = common_signals & set(key_signals)
        print(f"Filtered to key signals: {len(common_signals)}")

    # Compare values at common timestamps
    common_times = set(golden_values.keys()) & set(completed_values.keys())
    print(f"Common timestamps: {len(common_times)}")

    if not common_times:
        print("WARNING: No common timestamps found!")
        print(f"Golden timestamps (first 10): {sorted(golden_values.keys())[:10]}")
        print(f"Completed timestamps (first 10): {sorted(completed_values.keys())[:10]}")
        return

    # Statistics
    total_comparisons = 0
    matches = 0
    mismatches = []

    sorted_times = sorted(common_times)

    for t in sorted_times:
        golden_vals = golden_values[t]
        completed_vals = completed_values[t]

        for sig in common_signals:
            if sig in golden_vals and sig in completed_vals:
                g_val = normalize_binary(golden_vals[sig])
                c_val = normalize_binary(completed_vals[sig])

                total_comparisons += 1
                if g_val == c_val:
                    matches += 1
                else:
                    mismatches.append({
                        'time': t,
                        'signal': sig,
                        'golden': g_val,
                        'completed': c_val
                    })

    # Report results
    print(f"\n{'='*60}")
    print("COMPARISON RESULTS")
    print(f"{'='*60}")
    print(f"Total comparisons: {total_comparisons}")
    print(f"Matches: {matches}")
    print(f"Mismatches: {len(mismatches)}")

    if total_comparisons > 0:
        accuracy = matches / total_comparisons * 100
        print(f"Accuracy: {accuracy:.2f}%")

    if mismatches:
        print(f"\n{'='*60}")
        print("FIRST 20 MISMATCHES:")
        print(f"{'='*60}")
        for m in mismatches[:20]:
            print(f"  Time {m['time']:>10}: {m['signal']:20} golden={m['golden']:>12} completed={m['completed']:>12}")

        # Group mismatches by signal
        print(f"\n{'='*60}")
        print("MISMATCHES BY SIGNAL:")
        print(f"{'='*60}")
        by_signal = defaultdict(int)
        for m in mismatches:
            by_signal[m['signal']] += 1
        for sig, count in sorted(by_signal.items(), key=lambda x: -x[1])[:20]:
            print(f"  {sig:30}: {count} mismatches")
    else:
        print("\n✓ All compared values match!")

    # Sample some matched values at specific times
    print(f"\n{'='*60}")
    print("SAMPLE VALUES AT KEY TIMESTAMPS:")
    print(f"{'='*60}")

    key_sigs = ['pc_out', 'pc', 'pc_plus_4', 'ex_mem_alu_result', 'data_out']
    sample_times = sorted_times[::max(1, len(sorted_times)//10)][:10]

    for t in sample_times:
        print(f"\nTime {t}:")
        golden_vals = golden_values.get(t, {})
        completed_vals = completed_values.get(t, {})

        for sig in key_sigs:
            g = golden_vals.get(sig, 'N/A')
            c = completed_vals.get(sig, 'N/A')
            if g != 'N/A':
                g = normalize_binary(g)
            if c != 'N/A':
                c = normalize_binary(c)

            match_str = "✓" if g == c else "✗"
            print(f"  {match_str} {sig:15}: golden={g:>12}  completed={c:>12}")

def main():
    golden_file = "/home/leoric/code/aig_demo/fullvision_demo/output/vcd/mini_cpu_golden.vcd"
    completed_file = "/home/leoric/code/aig_demo/fullvision_demo/output/vcd/mini_cpu_completed.vcd"

    # Key signals that are properly mapped (not optimized away)
    key_signals = [
        'pc_out', 'pc', 'pc_plus_4',
        'data_out', 'data_in',
        'mem_read', 'mem_write',
        'rst_n', 'clk',
        'if_id_pc', 'if_id_instr',
        'id_ex_rs1_data', 'id_ex_rs2_data',
        'ex_mem_alu_result',
        'regfile[0]', 'regfile[1]', 'regfile[2]',
    ]

    compare_vcds(golden_file, completed_file, key_signals)

if __name__ == "__main__":
    main()

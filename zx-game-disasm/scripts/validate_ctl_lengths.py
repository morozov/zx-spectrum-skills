#!/usr/bin/env python3
"""
Validate that line-level comments in a SkoolKit .ctl file don't have redundant lengths.

This script processes indented lines of the form $ADDRESS,LENGTH. If the length
equals the difference between this address and the next address, it reports a
violation since the length is redundant and can be omitted.

Any indent counts, both when reading a length and when finding the next address,
as `validate_ctl_array_elements.py` and `validate_ctl_instruction_order.py` read
it: SkoolKit renders a four-space comment exactly as it renders a two-space one.
A depth this check ignored would be a comment it did not see, and the gap it then
measured would run past it - which reports a legitimately explicit length as
redundant and fails the build on correct annotation.
"""

import re
import sys


def parse_address_line(line):
    """
    Parse an indented line of the form '$ADDRESS,LENGTH'.
    Returns (address, length, rest_of_line) or None if not matching.
    Only matches lines with exactly 2 comma-separated values (not 3+).
    """
    match = re.match(r'^ +\$([0-9A-Fa-f]+),(\d+)([^,].*)$', line)
    if match:
        address = int(match.group(1), 16)
        length = int(match.group(2))
        rest = match.group(3)
        return (address, length, rest)
    return None


def get_next_address(lines, start_index):
    """
    Find the next comment line of the form '$ADDRESS' at any indent.
    Returns the address as an integer or None.
    """
    for i in range(start_index + 1, len(lines)):
        line = lines[i]
        match = re.match(r'^ +\$([0-9A-Fa-f]+)', line)
        if match:
            return int(match.group(1), 16)
    return None


def validate_ctl_file(path):
    """
    Validate the CTL file for redundant length values.
    Returns a list of violations.
    """
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    violations = []

    for i, line in enumerate(lines):
        parsed = parse_address_line(line)

        if parsed:
            address, length, rest = parsed
            next_address = get_next_address(lines, i)

            if next_address is not None:
                address_diff = next_address - address

                if address_diff == length:
                    # Length is redundant
                    violations.append({
                        'line_number': i + 1,
                        'line_content': line.rstrip(),
                        'address': address,
                        'length': length,
                        'next_address': next_address
                    })

    return violations


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <ctl_file>")
        print()
        print("Validates that line-level comments don't have redundant lengths.")
        sys.exit(1)

    ctl_file_path = sys.argv[1]

    try:
        violations = validate_ctl_file(ctl_file_path)

        if not violations:
            return 0

        print(f"Found {len(violations)} redundant length(s):")
        print()

        for v in violations:
            print(f"  Line {v['line_number']}: ${v['address']:04X},{v['length']} "
                  f"(next=${v['next_address']:04X}, diff={v['length']})")
            print(f"    {v['line_content']}")
            print()

        return 1

    except FileNotFoundError:
        print(f"Error: File not found: {ctl_file_path}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())

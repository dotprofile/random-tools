#!/usr/bin/env python3
"""
ppc_bin_diff.py — Compare two PowerPC binaries and dump instruction-level differences.

Usage:
  python ppc_bin_diff.py clean.bin patched.bin [--base 0x80000000] [--mode 64|32] [--endian big|little]
                                               [--outfile patches.asm] [--makepatch]

Defaults:
  --mode 64 --endian big  (Xbox 360 HV style)
"""

import argparse
import datetime as _dt
from pathlib import Path
import sys

try:
    from capstone import (
        Cs,
        CS_ARCH_PPC,
        CS_MODE_64,
        CS_MODE_32,
        CS_MODE_BIG_ENDIAN,
        CS_MODE_LITTLE_ENDIAN,
    )
except Exception as e:
    sys.exit(
        "ERROR: The 'capstone' module is required.\n"
        "Install with: pip install capstone\n"
        f"Details: {e}"
    )


def parse_int(s: str) -> int:
    s = s.strip().lower()
    return int(s, 16) if s.startswith("0x") else int(s)


def read_bin(p: Path) -> bytes:
    if not p.is_file():
        raise FileNotFoundError(f"File not found: {p}")
    return p.read_bytes()


def make_disassembler(mode_bits: int, endian: str) -> "Cs":
    mode = CS_MODE_64 if mode_bits == 64 else CS_MODE_32
    if endian.lower().startswith("big"):
        mode |= CS_MODE_BIG_ENDIAN
    else:
        mode |= CS_MODE_LITTLE_ENDIAN
    md = Cs(CS_ARCH_PPC, mode)
    md.detail = False
    return md


def hex32(b: bytes, endian: str) -> str:
    if len(b) != 4:
        return "0x" + b.hex()
    val = int.from_bytes(b, "big" if endian.startswith("b") else "little", signed=False)
    return f"0x{val:08X}"


def disasm_block(md: "Cs", buf: bytes, start_addr: int, endian: str):
    """Disassemble entire buffer; fall back to .long for undecodable words."""
    out = []
    for ins in md.disasm(buf, start_addr):
        out.append((ins.address, ins.bytes, ins.mnemonic, ins.op_str))
    if not out and buf:
        # fall back: render as .long 0x???????? per 4 bytes
        addr = start_addr
        for i in range(0, len(buf), 4):
            chunk = buf[i : i + 4]
            out.append((addr, chunk, ".long", hex32(chunk, endian)))
            addr += 4
    return out


def coalesce_diff_blocks(a: bytes, b: bytes):
    """
    Yield (offset, size) ranges where 4-byte words differ.
    Scan in 4-byte steps for PPC instruction alignment.
    """
    n = min(len(a), len(b))
    n_aligned = (n // 4) * 4
    i = 0
    while i < n_aligned:
        if a[i : i + 4] != b[i : i + 4]:
            j = i + 4
            while j < n_aligned and a[j : j + 4] != b[j : j + 4]:
                j += 4
            yield (i, j - i)
            i = j
        else:
            i += 4

    # Handle trailing length deltas as a final diff block
    if len(a) != len(b):
        off = n_aligned
        size = max(len(a), len(b)) - off
        if size > 0:
            # round to multiple of 4 so disassembly/longs align nicely
            size_rounded = size + ((4 - (size % 4)) % 4)
            yield (off, size_rounded)


def write_diff(
    outfile: Path,
    clean: bytes,
    patched: bytes,
    base_addr: int,
    md: "Cs",
    endian: str,
):
    lines = []
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    header = [
        "; ================================================",
        f"; ppc_bin_diff output generated {now}",
        f"; base address: 0x{base_addr:X}",
        f"; capstone mode: {'PPC64' if ('64' in str(md.mode)) else 'PPC32'}"
        f" + {'BIG' if ('BIG' in str(md.mode)) else 'LITTLE'}",
        f"; clean size:   {len(clean)} bytes",
        f"; patched size: {len(patched)} bytes",
        "; ================================================\n",
    ]
    lines.extend(header)

    blocks = list(coalesce_diff_blocks(clean, patched))
    if not blocks:
        lines.append("; No differences found.\n")
    else:
        for (off, sz) in blocks:
            addr = base_addr + off
            clean_chunk = clean[off : off + sz]
            patch_chunk = patched[off : off + sz]

            lines.append(f"; --- Diff block at 0x{addr:X} (+0x{off:X}), size 0x{sz:X} bytes ---")
            lines.append("; ORIGINAL:")
            for a_addr, a_bytes, a_mnem, a_ops in disasm_block(md, clean_chunk, addr, endian):
                bytes_hex = a_bytes.hex()
                lines.append(f"0x{a_addr:08X}:  {bytes_hex:<12}  {a_mnem} {a_ops}".rstrip())

            lines.append("; PATCHED:")
            for p_addr, p_bytes, p_mnem, p_ops in disasm_block(md, patch_chunk, addr, endian):
                bytes_hex = p_bytes.hex()
                lines.append(f"0x{p_addr:08X}:  {bytes_hex:<12}  {p_mnem} {p_ops}".rstrip())

            lines.append("")  # blank line

    outfile.write_text("\n".join(lines), encoding="utf-8")
    return len(blocks)


def write_makepatch(
    outfile: Path,
    patched: bytes,
    clean: bytes,
    base_addr: int,
    md: "Cs",
    endian: str,
):
    """
    Emit ONLY the patched side, grouped into MAKEPATCH blocks:

    MAKEPATCH 0x0000ABCD
    0:
        <patched instructions...>
    9:
    """
    lines = []
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"; Generated by ppc_bin_diff on {now} (MAKEPATCH mode)")
    lines.append(f"; base address: 0x{base_addr:X}")
    lines.append("")

    blocks = list(coalesce_diff_blocks(clean, patched))
    if not blocks:
        lines.append("; No differences found.")
    else:
        for (off, sz) in blocks:
            addr = base_addr + off
            chunk = patched[off : off + sz]
            # Header with 8-digit, zero-padded lowercase hex per your example
            lines.append(f"MAKEPATCH 0x{addr:08x}")
            lines.append("0:")
            for _, _, mnem, ops in disasm_block(md, chunk, addr, endian):
                if ops:
                    lines.append(f"\t{mnem} {ops}")
                else:
                    lines.append(f"\t{mnem}")
            lines.append("9:\n")

    outfile.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return len(blocks)


def main():
    ap = argparse.ArgumentParser(description="PowerPC binary differ with Capstone disassembly.")
    ap.add_argument("clean", type=Path, help="Path to original/clean binary")
    ap.add_argument("patched", type=Path, help="Path to patched/modified binary")
    ap.add_argument("--base", default="0x0", type=str, help="Base address (hex or int). Default 0x0")
    ap.add_argument("--mode", default=64, type=int, choices=(32, 64), help="Capstone PPC mode (32 or 64). Default 64")
    ap.add_argument("--endian", default="big", choices=("big", "little"), help="Endianness. Default big")
    ap.add_argument("--outfile", default="patches.asm", type=Path, help="Output file (default patches.asm)")
    ap.add_argument("--makepatch", action="store_true", help="Emit only patched instructions in MAKEPATCH format")
    args = ap.parse_args()

    base_addr = parse_int(args.base)
    clean = read_bin(args.clean)
    patched = read_bin(args.patched)

    md = make_disassembler(args.mode, args.endian)

    try:
        if args.makepatch:
            blocks = write_makepatch(args.outfile, patched, clean, base_addr, md, args.endian)
        else:
            blocks = write_diff(args.outfile, clean, patched, base_addr, md, args.endian)
    except Exception as e:
        sys.exit(f"ERROR: {e}")

    if args.makepatch:
        print(f"Wrote {args.outfile} with {blocks} MAKEPATCH block(s).")
    else:
        print(f"Wrote {args.outfile} with {blocks} diff block(s).")


if __name__ == "__main__":
    main()

"""Generate original boot-test programs for NES, Mega Drive, and PlayStation."""

import argparse
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path


def nes_rom(dendy):
    # NES 2.0 header, NROM, 16 KiB PRG, 8 KiB CHR, timing NTSC or Dendy.
    header = b'NES\x1a' + bytes((1, 1, 0, 8, 0, 0, 0, 0, 3 if dendy else 0, 0, 0, 0))
    reset = bytes.fromhex(
        '78 d8 a2 ff 9a '       # SEI; CLD; LDX #$ff; TXS
        'a9 00 8d 00 20 8d 01 20 '
        '2c 02 20 10 fb '       # Wait for two vblanks before PPU writes.
        '2c 02 20 10 fb '
        'a9 3f 8d 06 20 a9 00 8d 06 20 '
        'a9 21 8d 07 20 '       # Universal background color.
        'a9 0e 8d 01 20'
    )
    loop = 0x8000 + len(reset)
    program = bytearray(b'\xea' * 16384)
    program[:len(reset)] = reset
    program[len(reset):len(reset) + 3] = b'\x4c' + struct.pack('<H', loop)
    program[-6:] = struct.pack('<HHH', loop, 0x8000, loop)
    return header + program + bytes(8192)


def megadrive_rom():
    rom = bytearray(65536)
    struct.pack_into('>II', rom, 0, 0xFFFF00, 0x200)
    rom[0x100:0x110] = b'SEGA MEGA DRIVE '
    rom[0x120:0x150] = b'HOMETV PI QA'.ljust(48)
    rom[0x150:0x180] = b'HOMETV PI QA'.ljust(48)
    rom[0x180:0x18E] = b'GM HOMETV-00'.ljust(14)
    rom[0x190:0x1A0] = b'J'.ljust(16)
    rom[0x1F0:0x200] = b'JUE'.ljust(16)
    struct.pack_into('>IIII', rom, 0x1A0, 0, len(rom) - 1, 0xFF0000, 0xFFFFFF)
    program = bytes.fromhex(
        '46fc 2700 '                    # MOVE.W #$2700,SR
        '23fc 53454741 00a14000 '       # Unlock display output on TMSS hardware.
        '33fc 8004 00c00004 '
        '33fc 8144 00c00004 '
        '33fc 8f02 00c00004 '
        '23fc c0000000 00c00004 '
        '33fc 00e0 00c00000 '           # Write green to VDP color RAM.
        '33fc 8700 00c00004 '
        '60fe'                          # BRA.S to this instruction.
    )
    rom[0x200:0x200 + len(program)] = program
    checksum = sum(word for word, in struct.iter_unpack('>H', rom[0x200:])) & 0xFFFF
    struct.pack_into('>H', rom, 0x18E, checksum)
    return rom


def playstation_executable():
    # GPU writes set the display mode/ranges, then paint its untextured backdrop.
    program = [0x3C081F80]  # LUI $t0,$1f80 (hardware register base)
    for register, value in (
        (0x1814, 0x00000000), (0x1814, 0x08000001), (0x1814, 0x06C60260),
        (0x1814, 0x07042018), (0x1814, 0x03000000), (0x1810, 0x02A00000),
        (0x1810, 0), (0x1810, 0x00F00140),
    ):
        program.extend((0x3C090000 | (value >> 16), 0x35290000 | (value & 0xFFFF), 0xAD090000 | register))
    program.extend((0x1000FFFF, 0))  # BEQ $zero,$zero back to itself; NOP delay slot.
    executable = bytearray(4096)
    executable[:8] = b'PS-X EXE'
    struct.pack_into('<IIII', executable, 16, 0x80010000, 0, 0x80010000, 2048)
    struct.pack_into('<I', executable, 48, 0x801FFF00)
    struct.pack_into('<' + 'I' * len(program), executable, 2048, *program)
    return executable


def playstation_disc(output, genisoimage):
    with tempfile.TemporaryDirectory(prefix='hometv-psx-qa-') as temporary:
        files = Path(temporary)
        (files / 'HOMETV.EXE').write_bytes(playstation_executable())
        (files / 'SYSTEM.CNF').write_bytes(b'BOOT = cdrom:\\HOMETV.EXE;1\r\n')
        subprocess.run([genisoimage, '-quiet', '-iso-level', '1', '-V', 'HOMETV_PSX',
                        '-o', str(output / 'hometv-psx.iso'), str(files)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    default = Path(__file__).resolve().parents[1] / 'dist/retro-fixtures'
    parser.add_argument('output', type=Path, nargs='?', default=default)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / 'hometv-nes-ntsc.nes').write_bytes(nes_rom(dendy=False))
    (output / 'hometv-nes-dendy.nes').write_bytes(nes_rom(dendy=True))
    (output / 'hometv-megadrive.md').write_bytes(megadrive_rom())
    genisoimage = shutil.which('genisoimage')
    if genisoimage:
        playstation_disc(output, genisoimage)
    else:
        print('PlayStation ISO requires genisoimage')


if __name__ == '__main__':
    main()

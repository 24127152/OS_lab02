import os
import struct
import tempfile
import unittest

from fat32_reader import FAT32Reader


SECTOR_SIZE = 512


def build_boot_sector(
    bytes_per_sector=512,
    sectors_per_cluster=1,
    reserved_sectors=32,
    num_fats=2,
    total_sectors=200,
    sectors_per_fat=1,
    root_cluster=2,
):
    b = bytearray(SECTOR_SIZE)
    b[0:3] = b"\xEB\x58\x90"
    b[3:11] = b"MSWIN4.1"
    b[11:13] = struct.pack("<H", bytes_per_sector)
    b[13] = sectors_per_cluster
    b[14:16] = struct.pack("<H", reserved_sectors)
    b[16] = num_fats
    b[32:36] = struct.pack("<I", total_sectors)
    b[36:40] = struct.pack("<I", sectors_per_fat)
    b[44:48] = struct.pack("<I", root_cluster)
    b[82:90] = b"FAT32   "
    b[510:512] = b"\x55\xAA"
    return b


def make_short_entry(name_8, ext_3, attr=0x20, first_cluster=2, size=0):
    entry = bytearray(32)
    entry[0:8] = name_8.encode("ascii").ljust(8, b" ")[:8]
    entry[8:11] = ext_3.encode("ascii").ljust(3, b" ")[:3]
    entry[11] = attr
    entry[20:22] = struct.pack("<H", (first_cluster >> 16) & 0xFFFF)
    entry[26:28] = struct.pack("<H", first_cluster & 0xFFFF)
    entry[28:32] = struct.pack("<I", size)
    return entry


def make_single_lfn_entry(name):
    entry = bytearray(32)
    entry[0] = 0x41
    entry[11] = 0x0F
    entry[12] = 0
    entry[13] = 0
    entry[26:28] = b"\x00\x00"

    encoded = name.encode("utf-16le")
    units = [encoded[i:i + 2] for i in range(0, len(encoded), 2)]

    while len(units) < 13:
        units.append(b"\xFF\xFF")

    if len(name) < 13:
        units[len(name)] = b"\x00\x00"

    payload = b"".join(units[:13])
    entry[1:11] = payload[0:10]
    entry[14:26] = payload[10:22]
    entry[28:32] = payload[22:26]
    return entry


class FAT32ReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp_files = []

    def tearDown(self):
        for path in self.temp_files:
            if os.path.exists(path):
                os.remove(path)

    def _new_temp_img(self):
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=".img")
        handle.close()
        self.temp_files.append(handle.name)
        return handle.name

    def test_read_boot_sector_direct_fat32(self):
        path = self._new_temp_img()
        image = bytearray(SECTOR_SIZE * 300)
        image[0:SECTOR_SIZE] = build_boot_sector(sectors_per_fat=4, total_sectors=300)

        with open(path, "wb") as f:
            f.write(image)

        reader = FAT32Reader(path)
        info = reader.read_boot_sector()

        self.assertEqual(info["partition_start_sector"], 0)
        self.assertEqual(info["bytes_per_sector"], 512)
        self.assertEqual(info["fat_start"], 32)
        self.assertEqual(info["first_data_sector"], 40)

    def test_read_boot_sector_from_mbr_partition(self):
        path = self._new_temp_img()
        image = bytearray(SECTOR_SIZE * 500)

        mbr = bytearray(SECTOR_SIZE)
        mbr[510:512] = b"\x55\xAA"
        entry_offset = 446
        mbr[entry_offset + 4] = 0x0C
        mbr[entry_offset + 8:entry_offset + 12] = struct.pack("<I", 63)
        image[0:SECTOR_SIZE] = mbr

        boot = build_boot_sector(sectors_per_fat=3, total_sectors=300)
        image[63 * SECTOR_SIZE:(63 + 1) * SECTOR_SIZE] = boot

        with open(path, "wb") as f:
            f.write(image)

        reader = FAT32Reader(path)
        info = reader.read_boot_sector()

        self.assertEqual(info["partition_start_sector"], 63)
        self.assertEqual(info["fat_start"], 95)
        self.assertEqual(info["first_data_sector"], 101)

    def test_list_root_directory_across_cluster_chain(self):
        path = self._new_temp_img()
        image = bytearray(SECTOR_SIZE * 300)
        image[0:SECTOR_SIZE] = build_boot_sector(sectors_per_fat=1, total_sectors=300)

        fat_offset = 32 * SECTOR_SIZE
        image[fat_offset + 2 * 4:fat_offset + 2 * 4 + 4] = struct.pack("<I", 3)
        image[fat_offset + 3 * 4:fat_offset + 3 * 4 + 4] = struct.pack("<I", 0x0FFFFFFF)

        cluster2_offset = 34 * SECTOR_SIZE
        cluster3_offset = 35 * SECTOR_SIZE

        image[cluster2_offset:cluster2_offset + 32] = make_short_entry("FILEA", "TXT", first_cluster=5, size=5)
        for i in range(1, 16):
            image[cluster2_offset + i * 32] = 0xE5

        image[cluster3_offset:cluster3_offset + 32] = make_short_entry("FILEB", "TXT", first_cluster=6, size=7)
        image[cluster3_offset + 32] = 0x00

        with open(path, "wb") as f:
            f.write(image)

        reader = FAT32Reader(path)
        reader.read_boot_sector()
        entries = reader.list_root_directory()
        names = [entry["name"] for entry in entries]

        self.assertIn("FILEA.TXT", names)
        self.assertIn("FILEB.TXT", names)

    def test_list_root_directory_decodes_single_lfn(self):
        path = self._new_temp_img()
        image = bytearray(SECTOR_SIZE * 300)
        image[0:SECTOR_SIZE] = build_boot_sector(sectors_per_fat=1, total_sectors=300)

        fat_offset = 32 * SECTOR_SIZE
        image[fat_offset + 2 * 4:fat_offset + 2 * 4 + 4] = struct.pack("<I", 0x0FFFFFFF)

        root_offset = 34 * SECTOR_SIZE
        image[root_offset:root_offset + 32] = make_single_lfn_entry("LONGNAME.TXT")
        image[root_offset + 32:root_offset + 64] = make_short_entry("LONGNA~1", "TXT", first_cluster=8, size=9)
        image[root_offset + 64] = 0x00

        with open(path, "wb") as f:
            f.write(image)

        reader = FAT32Reader(path)
        reader.read_boot_sector()
        entries = reader.list_root_directory()

        self.assertEqual(entries[0]["name"], "LONGNAME.TXT")
        self.assertEqual(entries[0]["size"], 9)

    def test_read_file_content_reads_exact_size(self):
        path = self._new_temp_img()
        image = bytearray(SECTOR_SIZE * 300)
        image[0:SECTOR_SIZE] = build_boot_sector(sectors_per_fat=1, total_sectors=300)

        fat_offset = 32 * SECTOR_SIZE
        image[fat_offset + 2 * 4:fat_offset + 2 * 4 + 4] = struct.pack("<I", 0x0FFFFFFF)
        image[fat_offset + 5 * 4:fat_offset + 5 * 4 + 4] = struct.pack("<I", 0x0FFFFFFF)

        root_offset = 34 * SECTOR_SIZE
        image[root_offset:root_offset + 32] = make_short_entry("FILEA", "TXT", first_cluster=5, size=5)
        image[root_offset + 32] = 0x00

        data_cluster_offset = 37 * SECTOR_SIZE
        image[data_cluster_offset:data_cluster_offset + 5] = b"abcde"

        with open(path, "wb") as f:
            f.write(image)

        reader = FAT32Reader(path)
        reader.read_boot_sector()
        data = reader.read_file_content(first_cluster=5, size=5)

        self.assertEqual(data, b"abcde")

    def test_list_directory_recursive_returns_nested_items(self):
        path = self._new_temp_img()
        image = bytearray(SECTOR_SIZE * 300)
        image[0:SECTOR_SIZE] = build_boot_sector(sectors_per_fat=1, total_sectors=300)

        fat_offset = 32 * SECTOR_SIZE
        image[fat_offset + 2 * 4:fat_offset + 2 * 4 + 4] = struct.pack("<I", 0x0FFFFFFF)
        image[fat_offset + 3 * 4:fat_offset + 3 * 4 + 4] = struct.pack("<I", 0x0FFFFFFF)
        image[fat_offset + 4 * 4:fat_offset + 4 * 4 + 4] = struct.pack("<I", 0x0FFFFFFF)

        root_offset = 34 * SECTOR_SIZE
        image[root_offset:root_offset + 32] = make_short_entry("SUBDIR", "", attr=0x10, first_cluster=3, size=0)
        image[root_offset + 32] = 0x00

        subdir_offset = 35 * SECTOR_SIZE
        image[subdir_offset:subdir_offset + 32] = make_short_entry("CHILD", "TXT", attr=0x20, first_cluster=4, size=6)
        image[subdir_offset + 32] = 0x00

        data_offset = 36 * SECTOR_SIZE
        image[data_offset:data_offset + 6] = b"HELLO!"

        with open(path, "wb") as f:
            f.write(image)

        reader = FAT32Reader(path)
        reader.read_boot_sector()
        items = reader.list_directory_recursive()
        paths = [item["path"] for item in items]

        self.assertIn("/SUBDIR", paths)
        self.assertIn("/SUBDIR/CHILD.TXT", paths)


if __name__ == "__main__":
    unittest.main()

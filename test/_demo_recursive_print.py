import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fat32_reader import FAT32Reader

image_path = r"C:\Users\Admin\Downloads\fat32_test.img"
reader = FAT32Reader(image_path)
info = reader.read_boot_sector()

print("Boot OK:", isinstance(info, dict))
items = reader.list_directory_recursive()
print("Total recursive items:", len(items))

for index, item in enumerate(items[:20], 1):
    print(
        f"{index}. {item['path']} | {item['type']} | "
        f"size={item['size']} | cluster={item['first_cluster']}"
    )

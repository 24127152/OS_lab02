import os
import re
import struct
import sys


class FAT32Reader:
    def __init__(self, file_path):
        self.file_path = file_path
        self.info = {}

    @staticmethod
    def _is_power_of_two(value):
        return value > 0 and (value & (value - 1)) == 0

    def _is_fat32_boot_sector(self, sector):
        if len(sector) < 512:
            return False

        signature = sector[510:512]
        if signature != b"\x55\xAA":
            return False

        bytes_per_sector = struct.unpack_from("<H", sector[11:13])[0]
        sectors_per_cluster = struct.unpack_from("<B", sector[13:14])[0]
        reserved_sectors = struct.unpack_from("<H", sector[14:16])[0]
        num_fats = struct.unpack_from("<B", sector[16:17])[0]
        sectors_per_fat = struct.unpack_from("<I", sector[36:40])[0]

        if bytes_per_sector not in (512, 1024, 2048, 4096):
            return False
        if not self._is_power_of_two(sectors_per_cluster):
            return False
        if reserved_sectors == 0 or num_fats == 0 or sectors_per_fat == 0:
            return False

        fs_type = sector[82:90]
        return fs_type == b"FAT32   "

    def _find_fat32_partition_start(self, mbr_sector):
        if len(mbr_sector) < 512 or mbr_sector[510:512] != b"\x55\xAA":
            return None

        fat32_types = {0x0B, 0x0C, 0x1B, 0x1C}
        partition_table_offset = 446
        #Các loại phân vùng FAT32 phổ biến trong MBR

        for i in range(4):
            entry_offset = partition_table_offset + (i * 16)
            part_type = mbr_sector[entry_offset + 4]
            start_lba = struct.unpack_from("<I", mbr_sector[entry_offset + 8:entry_offset + 12])[0]
            if part_type in fat32_types and start_lba > 0:
                return start_lba

        return None


    #Hàm đổi cluster snag sector
    def cluster_to_sector(self, cluster):
        if 'first_data_sector' not in self.info or 'sectors_per_cluster' not in self.info:
            raise ValueError("Boot sector information is incomplete. Cannot convert cluster to sector.")
        return self.info['first_data_sector'] + ((cluster - 2) * self.info['sectors_per_cluster'])
        
    #Hàm đọc entry trong FAT
    def read_fat_entry(self, f, cluster):
        fat_offset = self.info['fat_start'] * self.info['bytes_per_sector'] + (cluster * 4)
        f.seek(fat_offset)
        entry_data = f.read(4)
        if len(entry_data) < 4:
            return None
        return struct.unpack_from("<I", entry_data)[0] & 0x0FFFFFFF

    #Hàm đọc chuỗi cluster từ cluster đầu tiên
    def read_cluster_chain(self, f, start_cluster):
        cluster_chain = []
        visited = set()
        current_cluster = start_cluster
        while (
            current_cluster not in visited
            and current_cluster >= 2
            and current_cluster != 0x0FFFFFF7
            and current_cluster < 0x0FFFFFF8
        ):
            visited.add(current_cluster)
            cluster_chain.append(current_cluster)
            nxt = self.read_fat_entry(f, current_cluster)
            if nxt is None or nxt >= 0x0FFFFFF8:
                break
            current_cluster = nxt
        return cluster_chain

    #Hàm giải mã 1 entry LFN
    def decode_lfn_entry(self, entry):
        raw_name = entry[1:11] + entry[14:26] + entry[28:32]
        chunks = []
        for i in range(0, len(raw_name), 2):
            code_unit = raw_name[i:i + 2]
            if code_unit in (b"\x00\x00", b"\xFF\xFF"):
                break
            chunks.append(code_unit)
        return b"".join(chunks).decode("utf-16le", errors="ignore")

    @staticmethod
    def decode_fat_date(raw_date):
        if raw_date == 0:
            return "N/A"
        year = 1980 + ((raw_date >> 9) & 0x7F)
        month = (raw_date >> 5) & 0x0F
        day = raw_date & 0x1F
        if month == 0 or day == 0:
            return "N/A"
        return f"{year:04d}-{month:02d}-{day:02d}"

    @staticmethod
    def decode_fat_time(raw_time):
        if raw_time == 0:
            return "N/A"
        hour = (raw_time >> 11) & 0x1F
        minute = (raw_time >> 5) & 0x3F
        second = (raw_time & 0x1F) * 2
        return f"{hour:02d}:{minute:02d}:{second:02d}"

    #Hàm parse cac entry 32-byte trong 1 thu muc
    def parse_directory_entries(self, directory_data):
        files = []
        lfn_parts = []

        for i in range(0, len(directory_data), 32):
            entry = directory_data[i:i + 32]
            if len(entry) < 32:
                break

            first_byte = entry[0]
            if first_byte == 0x00:
                break
            if first_byte == 0xE5:
                lfn_parts = []
                continue

            attr = entry[11]
            if attr == 0x0F:
                lfn_parts.append(self.decode_lfn_entry(entry))
                continue

            if attr & 0x08:
                lfn_parts = []
                continue

            filename = entry[0:8].decode('ascii', errors='ignore').strip()
            ext = entry[8:11].decode('ascii', errors='ignore').strip()
            short_name = f"{filename}.{ext}" if ext else filename
            fullname = ''.join(reversed(lfn_parts)).strip() if lfn_parts else short_name
            lfn_parts = []

            high_cluster = struct.unpack_from("<H", entry[20:22])[0]
            low_cluster = struct.unpack_from("<H", entry[26:28])[0]
            first_cluster = low_cluster + (high_cluster << 16)
            file_size = struct.unpack_from("<I", entry[28:32])[0]
            created_time_raw = struct.unpack_from("<H", entry[14:16])[0]
            created_date_raw = struct.unpack_from("<H", entry[16:18])[0]

            is_dir = (attr & 0x10) != 0
            entry_type = "Directory" if is_dir else "File"

            files.append({
                "name": fullname,
                "type": entry_type,
                "first_cluster": first_cluster,
                "size": file_size,
                "attr": attr,
                "created_date": self.decode_fat_date(created_date_raw),
                "created_time": self.decode_fat_time(created_time_raw),
            })

        return files

    #Hàm đọc dữ liệu của 1 cluster chain
    def read_cluster_data(self, f, start_cluster, max_bytes=None):
        if start_cluster < 2:
            return b""

        cluster_chain = self.read_cluster_chain(f, start_cluster)
        cluster_size = self.info['bytes_per_sector'] * self.info['sectors_per_cluster']
        output = bytearray()

        for cluster in cluster_chain:
            cluster_offset = self.cluster_to_sector(cluster) * self.info['bytes_per_sector']
            f.seek(cluster_offset)
            output.extend(f.read(cluster_size))

            if max_bytes is not None and len(output) >= max_bytes:
                return bytes(output[:max_bytes])

        return bytes(output if max_bytes is None else output[:max_bytes])

    #Hàm list file/folder trong 1 thu muc theo cluster dau
    def list_directory(self, start_cluster):
        if not self.info:
            boot_info = self.read_boot_sector()
            if not isinstance(boot_info, dict):
                return boot_info

        try:
            with open(self.file_path, 'rb') as f:
                raw_dir_data = self.read_cluster_data(f, start_cluster)
            return self.parse_directory_entries(raw_dir_data)
        except Exception as e:
            print(f"Error reading directory: {e}")
            return []

    #Hàm list files trong thư mục gốc
    def list_root_directory(self):
        if not self.info:
            boot_info = self.read_boot_sector()
            if not isinstance(boot_info, dict):
                return boot_info
        return self.list_directory(self.info['root_cluster'])

    #Hàm trả về danh sách tất cả file .txt (phẳng, không in cây)
    def list_all_txt_files(self):
        items = self.list_directory_recursive()
        if not isinstance(items, list):
            return []
        txt_files = []
        for item in items:
            if item.get("type") != "File":
                continue
            if item.get("name", "").lower().endswith(".txt"):
                txt_files.append(item)
        return txt_files
            
    #Hàm đọc boot sector và trích xuất thông tin cần thiết để làm việc với FAT32
    def read_boot_sector(self):
        try:
            with open(self.file_path, 'rb') as f:
                first_sector = f.read(512)
                if len(first_sector) < 512:
                    return "Boot sector must be 512 bytes long"

                partition_start_sector = 0
                boot_sector = first_sector

                if not self._is_fat32_boot_sector(first_sector):
                    detected_start = self._find_fat32_partition_start(first_sector)
                    if detected_start is None:
                        return "Cannot find FAT32 boot sector (not direct FAT32 and no FAT32 partition in MBR)."

                    f.seek(detected_start * 512)
                    candidate_boot_sector = f.read(512)
                    if not self._is_fat32_boot_sector(candidate_boot_sector):
                        return "Found FAT32 partition entry but boot sector at partition start is invalid."

                    partition_start_sector = detected_start
                    boot_sector = candidate_boot_sector

                self.info['bytes_per_sector'] = struct.unpack_from("<H", boot_sector[11:13])[0]
                self.info['sectors_per_cluster'] = struct.unpack_from("<B", boot_sector[13:14])[0]
                self.info['reserved_sectors'] = struct.unpack_from("<H", boot_sector[14:16])[0]
                self.info['nums_of_fats'] = struct.unpack_from("<B", boot_sector[16:17])[0]
                self.info['total_sectors'] = struct.unpack_from("<I", boot_sector[32:36])[0]
                self.info['sectors_per_fat'] = struct.unpack_from("<I", boot_sector[36:40])[0]
                self.info['root_cluster'] = struct.unpack_from("<I", boot_sector[44:48])[0]
                self.info['partition_start_sector'] = partition_start_sector

                #Tính toán vị trí bắt đầu của FAT và root directory
                self.info['fat_start'] = self.info['partition_start_sector'] + self.info['reserved_sectors']
                self.info['first_data_sector'] = self.info['fat_start'] + (self.info['nums_of_fats'] * self.info['sectors_per_fat'])
                self.info['root_dir_start'] = self.info['first_data_sector'] + ((self.info['root_cluster'] - 2) * self.info['sectors_per_cluster'])
                return self.info
        except PermissionError:
            return f"Permission denied: {self.file_path}"
        except FileNotFoundError:
            return f"File not found: {self.file_path}"
        except Exception as e:
            return f"Error handling boot sector: {e}"

    #Hàm đọc nội dung file theo first cluster va size
    def read_file_content(self, first_cluster, size):
        if not self.info:
            boot_info = self.read_boot_sector()
            if not isinstance(boot_info, dict):
                return b""

        if first_cluster < 2 or size <= 0:
            return b""

        try:
            with open(self.file_path, 'rb') as f:
                return self.read_cluster_data(f, first_cluster, max_bytes=size)
        except Exception:
            return b""

    #Hàm parse nội dung txt theo format gần giống Project 01
    def parse_scheduler_text(self, text):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        algorithm = "Unknown"
        time_slice = "N/A"
        processes = []

        for line in lines:
            lower_line = line.lower()
            if "algorithm" in lower_line or "scheduling" in lower_line:
                right = line.split(":", 1)
                algorithm = right[1].strip() if len(right) > 1 else line.strip()
                continue

            if "time slice" in lower_line or "quantum" in lower_line:
                numbers = re.findall(r"\d+", line)
                if numbers:
                    time_slice = numbers[0]
                continue

            if lower_line.startswith("pid") or "arrival" in lower_line:
                continue

            pid_match = re.search(r"\bP\d+\b", line, flags=re.IGNORECASE)
            numbers = [int(x) for x in re.findall(r"\d+", line)]
            if len(numbers) < 3:
                continue

            if pid_match:
                pid = pid_match.group(0).upper()
                if len(numbers) >= 3:
                    arrival = numbers[-3]
                    burst = numbers[-2]
                    priority = numbers[-1]
                else:
                    continue
            else:
                if len(numbers) >= 4:
                    pid = f"P{numbers[0]}"
                    arrival, burst, priority = numbers[1], numbers[2], numbers[3]
                else:
                    pid = f"P{len(processes) + 1}"
                    arrival, burst, priority = numbers[0], numbers[1], numbers[2]

            processes.append({
                "process_id": pid,
                "arrival_time": arrival,
                "cpu_burst_time": burst,
                "priority_queue_id": priority,
            })

        return {
            "algorithm": algorithm,
            "time_slice": time_slice,
            "processes": processes,
        }

    #Hàm lấy chi tiết file txt đã chọn
    def get_txt_file_details(self, txt_path):
        txt_files = self.list_all_txt_files()
        selected = next((item for item in txt_files if item.get("path") == txt_path), None)
        if not selected:
            return None

        raw_data = self.read_file_content(selected["first_cluster"], selected["size"])
        decoded = raw_data.decode("utf-8", errors="ignore")
        parsed = self.parse_scheduler_text(decoded)

        return {
            "name": selected["name"],
            "path": selected["path"],
            "created_date": selected.get("created_date", "N/A"),
            "created_time": selected.get("created_time", "N/A"),
            "size": selected["size"],
            "algorithm": parsed["algorithm"],
            "time_slice": parsed["time_slice"],
            "processes": parsed["processes"],
        }

    #Hàm duyệt đệ quy từ root hoac 1 cluster thu muc bat ky
    def list_directory_recursive(self, start_cluster=None, base_path="/", visited=None):
        if not self.info:
            boot_info = self.read_boot_sector()
            if not isinstance(boot_info, dict):
                return []

        if visited is None:
            visited = set()

        if start_cluster is None:
            start_cluster = self.info['root_cluster']

        if start_cluster in visited or start_cluster < 2:
            return []

        visited.add(start_cluster)
        entries = self.list_directory(start_cluster)
        if not isinstance(entries, list):
            return []

        results = []
        for entry in entries:
            name = entry.get("name", "")
            if name in (".", ".."):
                continue

            entry_path = (base_path.rstrip("/") + "/" + name).replace("//", "/")
            item = dict(entry)
            item["path"] = entry_path
            results.append(item)

            if item.get("type") == "Directory":
                child_cluster = item.get("first_cluster", 0)
                if child_cluster >= 2:
                    results.extend(
                        self.list_directory_recursive(
                            start_cluster=child_cluster,
                            base_path=entry_path,
                            visited=visited,
                        )
                    )

        return results
        

def is_supported_source(path):
    normalized = path.strip()
    return normalized.lower().endswith('.img') or normalized.startswith('/dev/sd')


def print_two_column_table(rows, title):
    print(f"\n{title}")
    print("-" * 70)
    key_width = max(len(k) for k, _ in rows)
    for key, value in rows:
        print(f"{key:<{key_width}} : {value}")


def print_process_table(processes):
    if not processes:
        print("No process rows parsed from this txt file.")
        return

    header = (
        f"{'Process ID':<12}"
        f"{'Arrival Time':<14}"
        f"{'CPU Burst Time':<16}"
        f"{'Priority Queue ID':<18}"
    )
    print(header)
    print("-" * len(header))
    for process in processes:
        print(
            f"{process['process_id']:<12}"
            f"{process['arrival_time']:<14}"
            f"{process['cpu_burst_time']:<16}"
            f"{process['priority_queue_id']:<18}"
        )



if __name__ == "__main__":
    # Ham main de chay chuong trinh
    # Chay voi file .img: python3 fat32_reader.py disk.img
    # Chay voi USB Linux: sudo python3 fat32_reader.py /dev/sdb
    if len(sys.argv) > 1:
        source_path = sys.argv[1].strip()
    else:
        source_path = input("Enter source path (.img or /dev/sdb): ").strip()

    #Kiểm tra nguồn đâu vào có hợp lệ hay không
    if not is_supported_source(source_path):
        print("Unsupported source. Please provide a .img file or a /dev/sdX device path.")
        sys.exit(1)

    if source_path.lower().endswith('.img') and not os.path.isfile(source_path):
        print(f"Image file not found: {source_path}")
        sys.exit(1)

    print("Reading FAT32 boot sector from:", source_path)
    reader = FAT32Reader(source_path)
    boot_sector_info = reader.read_boot_sector()

    if isinstance(boot_sector_info, dict):
        # Requirement 1: Display boot sector info in table format.
        with open(source_path, 'rb') as fsrc:
            root_chain = reader.read_cluster_chain(fsrc, boot_sector_info['root_cluster'])
        rdet_sectors = len(root_chain) * boot_sector_info['sectors_per_cluster']

        boot_rows = [
            ("Bytes per sector", boot_sector_info['bytes_per_sector']),
            ("Sectors per cluster", boot_sector_info['sectors_per_cluster']),
            ("Number of sectors in Boot Sector region", boot_sector_info['reserved_sectors']),
            ("Number of FAT tables", boot_sector_info['nums_of_fats']),
            ("Number of sectors per FAT table", boot_sector_info['sectors_per_fat']),
            ("Number of sectors for the RDET", rdet_sectors),
            ("Total number of sectors on the disk", boot_sector_info['total_sectors']),
        ]
        print_two_column_table(boot_rows, "Boot Sector Information")

        # Requirement 2: List all *.txt files across the disk.
        txt_files = reader.list_all_txt_files()
        print("\nAll .txt files across disk:")
        if not txt_files:
            print("No .txt file found.")
            sys.exit(0)

        for index, txt_file in enumerate(txt_files, 1):
            print(f"{index}. {txt_file['path']}")

        # Requirement 3: View detailed information of a selected *.txt file.
        selected_index = input("\nSelect a .txt file by number: ").strip()
        if not selected_index.isdigit() or not (1 <= int(selected_index) <= len(txt_files)):
            print("Invalid selection.")
            sys.exit(1)

        selected_path = txt_files[int(selected_index) - 1]['path']
        details = reader.get_txt_file_details(selected_path)
        if not details:
            print("Cannot load selected txt file details.")
            sys.exit(1)

        detail_rows = [
            ("Name", details['name']),
            ("Path", details['path']),
            ("Date created", details['created_date']),
            ("Time created", details['created_time']),
            ("Total Size", f"{details['size']} bytes"),
            ("Scheduling Algorithm Name", details['algorithm']),
            ("Time slice", details['time_slice']),
        ]
        print_two_column_table(detail_rows, "Selected TXT File Details")
        print("\nProcess Information Table")
        print_process_table(details['processes'])

    else:
        print(boot_sector_info)

    
    

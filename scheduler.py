from fat32_reader import FAT32Reader


def choose_txt_file(reader, input_fn=input, print_fn=print):
	txt_files = reader.list_all_txt_files()
	if not txt_files:
		print_fn("No .txt file found.")
		return None

	print_fn("All .txt files across disk:")
	for index, txt_file in enumerate(txt_files, 1):
		print_fn(f"{index}. {txt_file['path']}")

	selected_index = input_fn("Select a .txt file by number: ").strip()
	if not selected_index.isdigit():
		print_fn("Invalid selection.")
		return None

	selected_number = int(selected_index)
	if selected_number < 1 or selected_number > len(txt_files):
		print_fn("Invalid selection.")
		return None

	return txt_files[selected_number - 1]["path"]


def print_selected_txt_summary(reader, txt_path, print_fn=print):
	details = reader.get_txt_file_details(txt_path)
	if not details:
		print_fn("Cannot load selected txt file details.")
		return None

	print_fn("\nSelected TXT File Details")
	print_fn("-------------------------")
	print_fn(f"Name: {details['name']}")
	print_fn(f"Date created: {details['created_date']}")
	print_fn(f"Time created: {details['created_time']}")
	print_fn(f"Total Size: {details['size']} bytes")
	return details


def run_txt_selection_flow(source_path, input_fn=input, print_fn=print):
	reader = FAT32Reader(source_path)
	boot_info = reader.read_boot_sector()
	if not isinstance(boot_info, dict):
		print_fn(boot_info)
		return None

	txt_path = choose_txt_file(reader, input_fn=input_fn, print_fn=print_fn)
	if not txt_path:
		return None

	return print_selected_txt_summary(reader, txt_path, print_fn=print_fn)

#Hàm để parse input lab01
def parse_lab01_input(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    queue_info = []
    process_table = []
    for line in lines:
        line  = line.strip()
        if line.startswith("Q"):
            parts = line.split()
            queue_info.append({
                'queue_id': parts[0],
                'time_slice': int(parts[1]),
                'algorithm': parts[2]
            })

        elif line.startswith("P"):
            parts = line.split()
            process_table.append({
                'process_id': parts[0],
                'arrival_time': int(parts[1]),
                'burst_time': int(parts[2]),
                'priority': int(parts[3])
            })
    
    return queue_info, process_table

#Hàm parse file txt để lấy thông tin về queue và process table cho lab01
def parse_scheduler_config_file(file_path):
    #Lấy queue
    queue_info,_ = parse_lab01_input(file_path)
    return queue_info

def parse_process_table(file_path):
    #lấy process table
    _, process_table = parse_lab01_input(file_path)
    return process_table

###Nhóm chuẩn hóa dữ liệu cho lab01
def normalize_queue_info(queue_info):
    # Chuẩn hóa thông tin queue
    normalized_queues = []
    for queue in queue_info:
        normalized_queues.append({
            'queue_id': queue['queue_id'],
            'time_slice': queue['time_slice'],
            'algorithm': queue['algorithm'],
            'remaining_time': queue['time_slice']  # Thêm trường remaining_time để theo dõi thời gian còn lại của queue
        })
    normalized_queues.sort(key= lambda x: x['queue_id'])  # Sắp xếp theo queue_id để đảm bảo thứ tự
    return normalized_queues
#Chuẩn hóa process table để đảm bảo thứ tự và định dạng nhất quán
def normalize_process_table(process_table):
    # Chuẩn hóa thông tin process table
    normalized_processes = []
    for process in process_table:
        normalized_processes.append({
            'process_id': process['process_id'],
            'arrival_time': process['arrival_time'],
            'burst_time': process['burst_time'],
            'priority': process['priority']
        })
    normalized_processes.sort(key= lambda x: x['arrival_time'])  # Sắp xếp theo arrival_time để đảm bảo thứ tự
    return normalized_processes

#Nhóm hàm thuật toán scheduling
def run_sjf_algorithm(process_table):
    # Thuật toán SJF (Shortest Job First)
    process_table = normalize_process_table(process_table)
    ready_queue = []
    time = 0
    completed_processes = []

    while process_table or ready_queue:
        # Thêm các process đã đến vào ready queue
        while process_table and process_table[0]['arrival_time'] <= time:
            ready_queue.append(process_table.pop(0))
        
        if ready_queue:
            # Chọn process có burst time ngắn nhất
            ready_queue.sort(key=lambda x: x['burst_time'])
            current_process = ready_queue.pop(0)
            time += current_process['burst_time']
            completed_processes.append(current_process)
        else:
            time += 1  # Nếu không có process nào sẵn sàng, tăng thời gian

    return completed_processes

def run_srtn_algorithm(process, table):
    # Thuật toán SRTN (Shortest Remaining Time Next)
    process_table = normalize_process_table(table)
    ready_queue = []
    time = 0
    completed_processes = []

    while process_table or ready_queue:
        # Thêm các process đã đến vào ready queue
        while process_table and process_table[0]['arrival_time'] <= time:
            ready_queue.append(process_table.pop(0))
        
        if ready_queue:
            # Chọn process có thời gian còn lại ngắn nhất
            ready_queue.sort(key=lambda x: x['burst_time'])
            current_process = ready_queue[0]
            current_process['burst_time'] -= 1  # Giảm thời gian còn lại của process
            
            if current_process['burst_time'] == 0:
                completed_processes.append(current_process)
                ready_queue.pop(0)  # Loại bỏ process đã hoàn thành
        time += 1  # Tăng thời gian sau mỗi bước

    return completed_processes

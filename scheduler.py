from fat32_reader import FAT32Reader

#Hàm để chọn file txt từ FAT32 và hiển thị thông tin chi tiết của file đó
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

#Hàm để hiển thị thông tin chi tiết của file txt đã chọn
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
def parse_lab01_text(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if not lines:
        return [], []

    queue_count = int(lines[0])
    queue_lines = lines[1:1 + queue_count]
    process_lines = lines[1 + queue_count:]

    queue_info = []
    for line in queue_lines:
        parts = line.split()
        if len(parts) < 3:
            raise ValueError(f"Invalid queue line: {line}")
        queue_info.append({
            'queue_id': parts[0],
            'time_slice': int(parts[1]),
            'algorithm': parts[2].upper(),
        })

    process_table = []
    for line in process_lines:
        parts = line.split()
        if len(parts) < 4:
            raise ValueError(f"Invalid process line: {line}")
        process_table.append({
            'process_id': parts[0],
            'arrival_time': int(parts[1]),
            'burst_time': int(parts[2]),
            'queue_id': parts[3],
        })

    return queue_info, process_table

def parse_lab01_input(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return parse_lab01_text(f.read())

#Hàm parse file txt để lấy thông tin về queue và process table cho lab01
def parse_scheduler_config_file(file_path):
    #Lấy queue
    queue_info,_ = parse_lab01_input(file_path)
    return queue_info

def parse_process_table(file_path):
    #lấy process table
    _, process_table = parse_lab01_input(file_path)
    return process_table

def build_queue_lookup(queue_info):
    return {
        queue['queue_id']: {
            'time_slice': queue['time_slice'],
            'algorithm': queue['algorithm'].upper(),
        }
        for queue in queue_info
    }

def load_lab01_from_txt_file(reader, txt_path):
    txt_files = reader.list_all_txt_files()
    selected = next((item for item in txt_files if item.get('path') == txt_path), None)
    if not selected:
        return None, [], []

    raw_bytes = reader.read_file_content(selected['first_cluster'], selected['size'])
    text = raw_bytes.decode('utf-8', errors='ignore')
    queue_info, process_table = parse_lab01_text(text)
    return selected, queue_info, process_table

###Nhóm chuẩn hóa dữ liệu cho lab01
def normalize_queue_info(queue_info):
    # Chuẩn hóa thông tin queue
    normalized_queues = []
    for queue in queue_info:
        normalized_queues.append({
            'queue_id': queue['queue_id'],
            'time_slice': queue['time_slice'],
            'algorithm': queue['algorithm'].upper(),
            'remaining_time': queue['time_slice']  # Thêm trường remaining_time để theo dõi thời gian còn lại của queue
        })
    normalized_queues.sort(key=lambda x: int(x['queue_id'][1:]) if x['queue_id'][1:].isdigit() else x['queue_id'])
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
            'priority': process.get('priority', 0),
            'queue_id': process.get('queue_id')
        })
    normalized_processes.sort(key=lambda x: (x['arrival_time'], x['process_id']))
    return normalized_processes

def attach_queue_metadata(process_table, queue_lookup):
    enriched = []
    for process in process_table:
        queue_id = process['queue_id']
        queue_config = queue_lookup.get(queue_id, {})
        enriched.append({
            **process,
            'algorithm': queue_config.get('algorithm', 'UNKNOWN'),
            'time_slice': queue_config.get('time_slice'),
        })
    return enriched

def normalize_timeline(timeline):
    normalized = []
    for segment in timeline:
        if normalized and normalized[-1]['pid'] == segment['pid'] and normalized[-1]['end'] == segment['start']:
            normalized[-1]['end'] = segment['end']
        else:
            normalized.append(dict(segment))
    return normalized

def queue_sort_key(queue_id):
    digits = ''.join(ch for ch in queue_id if ch.isdigit())
    return int(digits) if digits else queue_id

def build_queue_groups(queue_info, process_table):
    groups = {}
    for queue in queue_info:
        groups[queue['queue_id']] = {
            'queue_id': queue['queue_id'],
            'algorithm': queue['algorithm'].upper(),
            'time_slice': queue['time_slice'],
            'processes': [],
        }

    for process in process_table:
        queue_id = process.get('queue_id')
        if queue_id not in groups:
            groups[queue_id] = {
                'queue_id': queue_id,
                'algorithm': 'UNKNOWN',
                'time_slice': None,
                'processes': [],
            }
        groups[queue_id]['processes'].append(dict(process))

    ordered_queue_ids = sorted(groups.keys(), key=queue_sort_key)
    return [groups[queue_id] for queue_id in ordered_queue_ids]

#Nhóm hàm thuật toán scheduling
def run_sjf_algorithm(process_table, start_time=0):
    # Thuật toán SJF (Shortest Job First) non-preemptive
    pending = normalize_process_table(process_table)
    ready_queue = []
    time = start_time
    timeline = []
    completion_times = {}
    completed_processes = []

    while pending or ready_queue:
        while pending and pending[0]['arrival_time'] <= time:
            ready_queue.append(pending.pop(0))

        if not ready_queue:
            if pending:
                next_time = pending[0]['arrival_time']
                if next_time > time:
                    timeline.append({'pid': 'IDLE', 'start': time, 'end': next_time})
                    time = next_time
                continue
            break

        ready_queue.sort(key=lambda x: (x['burst_time'], x['arrival_time'], x['process_id']))
        current_process = ready_queue.pop(0)
        start_time = time
        end_time = time + current_process['burst_time']
        timeline.append({'pid': current_process['process_id'], 'start': start_time, 'end': end_time})
        time = end_time

        completion_times[current_process['process_id']] = end_time
        completed_processes.append(current_process)

    return {
        'timeline': normalize_timeline(timeline),
        'completion_times': completion_times,
        'completed_processes': completed_processes,
    }

def run_srtn_algorithm(process_table, start_time=0):
    # Thuật toán SRTN (Shortest Remaining Time Next)
    pending = normalize_process_table(process_table)
    for process in pending:
        process['remaining_time'] = process['burst_time']

    ready_queue = []
    time = start_time
    timeline = []
    completion_times = {}
    active_pid = None
    active_start = None

    def close_active_segment(end_time):
        nonlocal active_pid, active_start
        if active_pid is not None and active_start is not None and end_time > active_start:
            timeline.append({'pid': active_pid, 'start': active_start, 'end': end_time})
        active_pid = None
        active_start = None

    while pending or ready_queue:
        while pending and pending[0]['arrival_time'] <= time:
            ready_queue.append(pending.pop(0))

        if not ready_queue:
            close_active_segment(time)
            if pending:
                next_time = pending[0]['arrival_time']
                if next_time > time:
                    timeline.append({'pid': 'IDLE', 'start': time, 'end': next_time})
                    time = next_time
                continue
            break

        ready_queue.sort(key=lambda x: (x['remaining_time'], x['arrival_time'], x['process_id']))
        current_process = ready_queue[0]

        if active_pid != current_process['process_id']:
            close_active_segment(time)
            active_pid = current_process['process_id']
            active_start = time

        current_process['remaining_time'] -= 1
        time += 1

        if current_process['remaining_time'] == 0:
            completion_times[current_process['process_id']] = time
            ready_queue.pop(0)
            close_active_segment(time)

    close_active_segment(time)

    return {
        'timeline': normalize_timeline(timeline),
        'completion_times': completion_times,
    }

def schedule_by_queues(queue_info, process_table):
    normalized_queues = normalize_queue_info(queue_info)
    normalized_processes = normalize_process_table(process_table)
    queue_groups = build_queue_groups(normalized_queues, normalized_processes)

    timeline = []
    completion_times = {}
    current_time = 0
    queue_results = []

    for queue_group in queue_groups:
        queue_processes = queue_group['processes']
        if not queue_processes:
            continue

        algorithm = queue_group['algorithm'].upper()
        if algorithm == 'SJF':
            result = run_sjf_algorithm(queue_processes, start_time=current_time)
        elif algorithm in ('SRTN', 'SRTF'):
            result = run_srtn_algorithm(queue_processes, start_time=current_time)
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        queue_results.append({
            'queue_id': queue_group['queue_id'],
            'algorithm': algorithm,
            'time_slice': queue_group['time_slice'],
            'timeline': result['timeline'],
        })
        timeline.extend(result['timeline'])
        completion_times.update(result['completion_times'])
        if timeline:
            current_time = timeline[-1]['end']

    turnaround_times = compute_turnaround_times(normalized_processes, completion_times)
    waiting_times = compute_waiting_times(normalized_processes, turnaround_times)

    avg_wt = sum(waiting_times.values()) / len(waiting_times) if waiting_times else 0
    avg_tat = sum(turnaround_times.values()) / len(turnaround_times) if turnaround_times else 0

    return {
        'queue_info': normalized_queues,
        'process_table': normalized_processes,
        'queue_results': queue_results,
        'timeline': normalize_timeline(timeline),
        'completion_times': completion_times,
        'waiting_times': waiting_times,
        'turnaround_times': turnaround_times,
        'average_waiting_time': avg_wt,
        'average_turnaround_time': avg_tat,
    }

def compute_turnaround_times(process_table, completion_times):
    return {
        process['process_id']: completion_times[process['process_id']] - process['arrival_time']
        for process in process_table
        if process['process_id'] in completion_times
    }

def compute_waiting_times(process_table, turnaround_times):
    return {
        process['process_id']: turnaround_times[process['process_id']] - process['burst_time']
        for process in process_table
        if process['process_id'] in turnaround_times
    }

def format_gantt_timeline(timeline):
    if not timeline:
        return "No timeline to display."

    parts = []
    for segment in timeline:
        parts.append(f"[{segment['start']}-{segment['end']}:{segment['pid']}]")
    return " ".join(parts)

def render_ascii_gantt_chart(timeline):
    if not timeline:
        return "No timeline to display."

    top = []
    bottom = []
    time_markers = []

    for index, segment in enumerate(timeline):
        duration = max(segment['end'] - segment['start'], 1)
        width = max(duration * 2, len(segment['pid']) + 2)
        label = segment['pid']
        top.append("+" + "-" * width + "+")
        bottom.append("|" + label.center(width) + "|")
        time_markers.append((segment['start'], len("".join(top)) - len(top[-1]) - 1))

    top_line = "".join(top)
    label_line = "".join(bottom)

    time_line_parts = []
    for segment in timeline:
        duration = max(segment['end'] - segment['start'], 1)
        width = max(duration * 2, len(segment['pid']) + 2)
        time_line_parts.append(str(segment['start']).ljust(width + 1))
    time_line_parts.append(str(timeline[-1]['end']))

    return "\n".join([
        top_line,
        label_line,
        top_line,
        "".join(time_line_parts),
    ])

def print_process_metrics(process_table, waiting_times, turnaround_times, print_fn=print):
    header = f"{'PID':<10}{'AT':<8}{'BT':<8}{'WT':<8}{'TAT':<8}"
    print_fn(header)
    print_fn('-' * len(header))
    for process in process_table:
        pid = process['process_id']
        print_fn(
            f"{pid:<10}{process['arrival_time']:<8}{process['burst_time']:<8}"
            f"{waiting_times.get(pid, 0):<8}{turnaround_times.get(pid, 0):<8}"
        )

def print_schedule_result(schedule_result, print_fn=print):
    print_fn("\nScheduling Diagram")
    print_fn(render_ascii_gantt_chart(schedule_result['timeline']))
    print_fn("\nTimeline Summary")
    print_fn(format_gantt_timeline(schedule_result['timeline']))

    if schedule_result.get('queue_results'):
        print_fn("\nQueue Summary")
        for queue_result in schedule_result['queue_results']:
            print_fn(
                f"{queue_result['queue_id']}: {queue_result['algorithm']} "
                f"(time slice={queue_result['time_slice']})"
            )

    print_fn("\nProcess Metrics")
    print_process_metrics(
        schedule_result['process_table'],
        schedule_result['waiting_times'],
        schedule_result['turnaround_times'],
        print_fn=print_fn,
    )
    print_fn(f"\nAverage Waiting Time: {schedule_result['average_waiting_time']:.2f}")
    print_fn(f"Average Turnaround Time: {schedule_result['average_turnaround_time']:.2f}")

def run_scheduler_for_selected_txt(reader, txt_path, print_fn=print):
    selected, queue_info, process_table = load_lab01_from_txt_file(reader, txt_path)
    if not selected:
        print_fn("Cannot load selected txt file details.")
        return None

    details = reader.get_txt_file_details(txt_path)
    if details:
        print_fn(f"Name: {details['name']}")
        print_fn(f"Date created: {details['created_date']}")
        print_fn(f"Time created: {details['created_time']}")
        print_fn(f"Total Size: {details['size']} bytes")

    schedule_result = schedule_by_queues(queue_info, process_table)
    print_schedule_result(schedule_result, print_fn=print_fn)

    return {
        'details': details,
        **schedule_result,
    }

def run_lab01_from_image(source_path, input_fn=input, print_fn=print):
    reader = FAT32Reader(source_path)
    boot_info = reader.read_boot_sector()
    if not isinstance(boot_info, dict):
        print_fn(boot_info)
        return None

    txt_path = choose_txt_file(reader, input_fn=input_fn, print_fn=print_fn)
    if not txt_path:
        return None

    return run_scheduler_for_selected_txt(reader, txt_path, print_fn=print_fn)


#Hàm để test code
if __name__ == "__main__":
    source_path = r"C:\Users\Admin\Downloads\fat32_test.img"
    run_lab01_from_image(source_path)
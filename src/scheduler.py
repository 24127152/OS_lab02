from fat32_reader import FAT32Reader

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

#Load file txt input.txt
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

#Hàm thực hiện thuật toán scheduling theo yêu cầu
def schedule_by_queues(queue_info, process_table):
    normalized_queues = normalize_queue_info(queue_info)
    base_processes = normalize_process_table(process_table)

    queue_index_map = {queue['queue_id']: index for index, queue in enumerate(normalized_queues)}

    normalized_processes = []
    for process in base_processes:
        queue_id = process.get('queue_id')
        queue_index = queue_index_map.get(queue_id, len(normalized_queues))
        normalized_processes.append({
            **process,
            'remaining_time': process['burst_time'],
            'start_time': None,
            'end_time': None,
            'current_queue_level': queue_index + 1,
        })

    timeline = []
    queue_results = [
        {
            'queue_id': queue['queue_id'],
            'algorithm': queue['algorithm'].upper(),
            'time_slice': queue['time_slice'],
            'timeline': [],
            'completion_times': {},
        }
        for queue in normalized_queues
    ]

    if not normalized_queues or not normalized_processes:
        return {
            'queue_info': normalized_queues,
            'process_table': normalized_processes,
            'queue_results': queue_results,
            'timeline': [],
            'completion_times': {},
            'waiting_times': {},
            'turnaround_times': {},
            'average_waiting_time': 0,
            'average_turnaround_time': 0,
        }

    completed = 0
    current_time = 0
    current_process_index = -1
    segment_start_time = 0

    current_queue_index = 0
    queue_time_remaining = normalized_queues[current_queue_index]['time_slice']
    locked_process_index = -1

    while completed < len(normalized_processes):
        idx = -1

        if (
            locked_process_index != -1
            and normalized_processes[locked_process_index]['remaining_time'] > 0
            and normalized_processes[locked_process_index]['arrival_time'] <= current_time
            and normalized_processes[locked_process_index]['current_queue_level'] == (current_queue_index + 1)
        ):
            idx = locked_process_index
        else:
            locked_process_index = -1

            for i, process in enumerate(normalized_processes):
                if (
                    process['arrival_time'] > current_time
                    or process['remaining_time'] <= 0
                    or process['current_queue_level'] != (current_queue_index + 1)
                ):
                    continue

                if idx == -1:
                    idx = i
                    continue

                # Q1: SRTN (preemptive theo remaining_time)
                if current_queue_index == 0:
                    if process['remaining_time'] < normalized_processes[idx]['remaining_time']:
                        idx = i
                    elif (
                        process['remaining_time'] == normalized_processes[idx]['remaining_time']
                        and process['arrival_time'] < normalized_processes[idx]['arrival_time']
                    ):
                        idx = i
                # SJF non-preemptive trong lượt queue
                else:
                    if process['burst_time'] < normalized_processes[idx]['burst_time']:
                        idx = i
                    elif (
                        process['burst_time'] == normalized_processes[idx]['burst_time']
                        and process['arrival_time'] < normalized_processes[idx]['arrival_time']
                    ):
                        idx = i

            if idx != -1 and current_queue_index > 0:
                locked_process_index = idx

        if idx == -1 or queue_time_remaining == 0:
            current_queue_index = (current_queue_index + 1) % len(normalized_queues)
            queue_time_remaining = normalized_queues[current_queue_index]['time_slice']
            locked_process_index = -1
            continue

        if idx != current_process_index:
            if current_process_index != -1:
                timeline.append({
                    'pid': normalized_processes[current_process_index]['process_id'],
                    'start': segment_start_time,
                    'end': current_time,
                })
            current_process_index = idx
            segment_start_time = current_time

        process = normalized_processes[idx]
        if process['start_time'] is None:
            process['start_time'] = current_time

        process['remaining_time'] -= 1
        current_time += 1
        queue_time_remaining -= 1

        finished = process['remaining_time'] == 0
        queue_slice_ended = queue_time_remaining == 0

        if finished or queue_slice_ended:
            timeline.append({
                'pid': process['process_id'],
                'start': segment_start_time,
                'end': current_time,
            })
            current_process_index = -1
            segment_start_time = current_time

            if finished:
                process['end_time'] = current_time
                completed += 1
                locked_process_index = -1

            if queue_slice_ended:
                current_queue_index = (current_queue_index + 1) % len(normalized_queues)
                queue_time_remaining = normalized_queues[current_queue_index]['time_slice']
                locked_process_index = -1

    completion_times = {
        process['process_id']: process['end_time']
        for process in normalized_processes
        if process['end_time'] is not None
    }

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

#Hàm tính TT
def compute_turnaround_times(process_table, completion_times):
    return {
        process['process_id']: completion_times[process['process_id']] - process['arrival_time']
        for process in process_table
        if process['process_id'] in completion_times
    }
#Hàm tính WT
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

#Hàm để hiển thị kết quả của quá trình scheduling
def print_process_metrics(process_table, waiting_times, completion_times, turnaround_times, queue_info=None, print_fn=print):
    header = f"{'Process':<10}{'Queue ID':<10}{'Arrival Time':<15}{'Burst Time':<15}{'Completion Time':<18}{'Turnaround Time':<18}{'Waiting Time':<15}{'Algorithm':<15}"
    print_fn(header)
    print_fn('-' * len(header))

    #Lấy thông tin queue vào một dict để tra cứu nhanh thuật toán của queue
    if isinstance(queue_info, dict):
        queue_lookup = queue_info
    else:
        queue_lookup = {
            queue.get('queue_id'): queue
            for queue in (queue_info or [])
            if isinstance(queue, dict)
        }

    for process in process_table:
        pid = process['process_id']
        #Thuật toán của queue tương ứng
        algorithm = queue_lookup.get(process['queue_id'], {}).get('algorithm', 'N/A')
        print_fn(
            f"{pid:<10}{process['queue_id']:<10}{process['arrival_time']:<15}{process['burst_time']:<15}"
            f"{completion_times.get(pid, 0):<18}{turnaround_times.get(pid, 0):<18}{waiting_times.get(pid, 0):<15}{algorithm:<15}"
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

    print_fn("\nProcess Statistics")
    print_process_metrics(
        schedule_result['process_table'],
        schedule_result['waiting_times'],
        schedule_result['completion_times'],
        schedule_result['turnaround_times'],
        schedule_result.get('queue_info', {}),
        print_fn=print_fn,
        
    )
    print_fn(f"\nAverage Waiting Time: {schedule_result['average_waiting_time']:.2f}")
    print_fn(f"Average Turnaround Time: {schedule_result['average_turnaround_time']:.2f}")

#Hàm schdule 
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


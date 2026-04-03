import os
import unittest

from scheduler import (
    parse_lab01_input,
    schedule_by_queues,
)


class SchedulerTests(unittest.TestCase):
    def test_parse_lab01_input_sample(self):
        sample_path = os.path.join(os.path.dirname(__file__), '..', '..', 'Lab01', 'input.txt')
        sample_path = os.path.normpath(sample_path)
        queue_info, process_table = parse_lab01_input(sample_path)

        self.assertEqual(len(queue_info), 3)
        self.assertEqual(queue_info[0]['queue_id'], 'Q1')
        self.assertEqual(queue_info[0]['algorithm'], 'SRTN')
        self.assertEqual(queue_info[1]['time_slice'], 5)
        self.assertEqual(len(process_table), 5)
        self.assertEqual(process_table[0]['process_id'], 'P1')
        self.assertEqual(process_table[-1]['queue_id'], 'Q3')

    def test_schedule_by_queues_sample(self):
        sample_path = os.path.join(os.path.dirname(__file__), '..', '..', 'Lab01', 'input.txt')
        sample_path = os.path.normpath(sample_path)
        queue_info, process_table = parse_lab01_input(sample_path)
        result = schedule_by_queues(queue_info, process_table)

        self.assertEqual(result['completion_times']['P2'], 7)
        self.assertEqual(result['completion_times']['P1'], 18)
        self.assertEqual(result['completion_times']['P4'], 22)
        self.assertEqual(result['completion_times']['P3'], 30)
        self.assertEqual(result['completion_times']['P5'], 40)

        self.assertAlmostEqual(result['average_waiting_time'], 13.4, places=1)
        self.assertAlmostEqual(result['average_turnaround_time'], 21.4, places=1)

        timeline_pids = [segment['pid'] for segment in result['timeline']]
        self.assertIn('P1', timeline_pids)
        self.assertIn('P2', timeline_pids)
        self.assertIn('P3', timeline_pids)
        self.assertIn('P4', timeline_pids)
        self.assertIn('P5', timeline_pids)


if __name__ == '__main__':
    unittest.main()

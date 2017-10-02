import json
import logging
import os
import socket
import struct
import sys
import threading
import time
import traceback
import zlib
import nsq
import requests
from result import Result


from dmoj import sysinfo
from dmoj.judgeenv import get_supported_problems, get_runtime_versions

logger = logging.getLogger('dmoj.judge')
timer = time.clock if os.name == 'nt' else time.time


class JudgeAuthenticationFailed(Exception):
    pass


class PacketManager(object):
    SIZE_PACK = struct.Struct('!I')

    def __init__(self, url='http://127.0.0.1:4151/pub?topic=submission', key='bojv4'):
        self.key = key
        self.url = url
        # Exponential backoff: starting at 4 seconds.
        # Certainly hope it won't stack overflow, since it will take days if not years.
        print "=================nsq-url==========================="
        print self.url

    def _send_packet(self, packet):

        try:
            packet['key'] = self.key
            resp = requests.post(self.url.strip(), data=json.dumps(packet)) 
            res = resp.content
            return res
        except Exception as ex:
            print ex
            return {'code': -1, 'msg': ex}

    def handshake(self, problems, runtimes, id, key):
        self._send_packet({'name': 'handshake',
                           'problems': problems,
                           'executors': runtimes,
                           'id': id,
                           'key': key})

    def test_case_status_packet(self, result, current_submission):
        self._send_packet({'submission-id': current_submission,
                           'position': result.case.position,
                           'status': result.get_result_name(),
                           'time': result.execution_time,
                           'memory': result.max_memory,
                           'output': result.output})

    def compile_start_packet(self, id):
        self._send_packet({'status': 'CL',
                           'submission-id': id})

    def compile_error_packet(self, log, current_submission):
        self.fallback = 4
        self._send_packet({'name': 'compile-error',
                           'status': 'CE',
                           'submission-id': current_submission,
                           'compile-message': log})

    def compile_message_packet(self, log, current_submission):
        logger.info('Compile message: %d', current_submission)
        self._send_packet({'status': 'JD',
                           'submission-id': current_submission,
                           'compile-message': log})

    def internal_error_packet(self, message, current_submission):
        logger.info('Internal error: %d', current_submission)
        self._send_packet({'name': 'internal-error',
                           'status': 'SE',
                           'submission-id': current_submission,
                           'message': message})

    def begin_grading_packet(self, current_submission):
        logger.info('Begin grading: %d', current_submission)
        self._send_packet({'status': 'JD',
                           'submission-id': current_submission})

    def grading_end_packet(self, current_submission):
        logger.info('End grading: %d', current_submission)
        self._send_packet({'position': 'end',
                           'submission-id': current_submission})

    def current_submission_packet(self, current_submission):
        logger.info('Current submission query: %d', current_submission)
        self._send_packet({'name': 'current-submission-id',
                           'submission-id': current_submission})

    def submission_terminated_packet(self, current_submission):
        logger.info('Submission aborted: %d', current_submission)
        self._send_packet({'name': 'submission-terminated',
                           'status': 'SE',
                           'submission-id': current_submission})

    def ping_packet(self, when):
        data = {'name': 'ping-response',
                'when': when,
                'time': time.time()}
        for fn in sysinfo.report_callbacks:
            key, value = fn()
            data[key] = value
        self._send_packet(data)

    def submission_acknowledged_packet(self, sub_id):
        self._send_packet({'name': 'submission-acknowledged',
                           'submission-id': sub_id})

    def invocation_acknowledged_packet(self, sub_id):
        self._send_packet({'name': 'submission-acknowledged',
                           'invocation-id': sub_id})

    def test_connect(self):
        self._send_packet({'test':'hhhhhhhh'})

import os
import subprocess
import zipfile
from functools import partial

import yaml
from yaml.parser import ParserError
from yaml.scanner import ScannerError

from dmoj import checkers
from dmoj.config import InvalidInitException, ConfigNode
from dmoj.generator import GeneratorManager
from dmoj.judgeenv import get_problem_root, env
from dmoj.utils.module import load_module_from_file
import redis
import requests


class Problem(object):
    def __init__(self, problem_id, time_limit, memory_limit, _problem_data):
        self.id = problem_id
        self.time_limit = time_limit
        self.memory_limit = memory_limit
        self.generator_manager = GeneratorManager()

        self.problem_data = ProblemDataManager(problem_id, _problem_data)

        # Checkers modules must be stored in a dict, for the duration of execution,
        # lest globals be deleted with the module.
        
        self.config = _problem_data

        # self.problem_data.archive = self._resolve_archive_files()

        # self.is_pretested = load_pretests_only and 'pretest_test_cases' in self.config
        self.cases = self._resolve_testcases(_problem_data)

    def load_checker(self, name):
        if name in self._checkers:
            return self._checkers[name]
        self._checkers[name] = checker = load_module_from_file(os.path.join(get_problem_root(self.id), name))
        return checker

    def _resolve_archive_files(self):
        if self.config.archive:
            archive_path = os.path.join(get_problem_root(self.id), self.config.archive)
            if not os.path.exists(archive_path):
                raise InvalidInitException('archive file "%s" does not exist' % archive_path)
            try:
                archive = zipfile.ZipFile(archive_path, 'r')
            except zipfile.BadZipfile:
                raise InvalidInitException('bad archive: "%s"' % archive_path)
            return archive
        return None

    def _resolve_testcases(self, cfg):
        cases = []
        for case_config in cfg:
            cases.append(TestCase(case_config, self))
        return cases


class ProblemDataManager(dict):

    data = {}

    def __init__(self, problem_id, problem_data, **kwargs):
        super(ProblemDataManager, self).__init__(**kwargs)
        self.problem_id = problem_id
        self.archive = None

        print "initial problem_data: ", problem_data
        try:
            for f in problem_data:
                i = f['in']
                o = f['out']
                # p_dir = get_problem_root(self.problem_id)
                self._get_file(i)
                self._get_file(o)

        except Exception as ex:
            print "error", ex

    def _get_file(self, key):
        # key = f['filename']
        # url = f['path']

        if key in self.data:
            return

        with open(key, 'rb') as fp:
            self.data[key] = fp.read()

    def __missing__(self, key):
        try:
            # local_path = os.path.join(get_problem_root(self.problem_id), key)
            return self.data[key]
            # return open(), 'r').read()
        except IOError:
            raise KeyError('file "%s" could not be found' % key)

    def __del__(self):
        if self.archive:
            self.archive.close()


class BatchedTestCase(object):
    def __init__(self, batch_no, config, problem):
        self.config = config
        self.batch_no = batch_no
        self.points = config.points
        self.batched_cases = problem._resolve_testcases(config['batched'], batch_no=batch_no)
        if any(isinstance(case, BatchedTestCase) for case in self.batched_cases):
            raise InvalidInitException("nested batches")
        self.problem = problem

    def __str__(self):
        return 'BatchedTestCase{cases=%s}' % str(self.batched_cases)


class TestCase(object):
    def __init__(self, config, problem):
        self.position = config['position']
        self.config = config
        self.problem = problem
        self.output_prefix_length = 100

    def _normalize(self, data):
        # Normalize all newline formats (\r\n, \r, \n) to \n, otherwise we have problems with people creating
        # data on Macs (\r newline) when judged programs assume \n
        return data.replace('\r\n', '\r').replace('\r', '\n')

    def input_data(self):
        # in file is optional
        return self._normalize(self.problem.problem_data[self.config['in']]) if self.config['in'] else ''

    def output_data(self):
        # if self.config[out]:
        return self._normalize(self.problem.problem_data[self.config['out']])

    def __str__(self):
        return 'TestCase{in=%s,out=%s}' % (self.config['in'], self.config['out'])


import argparse
import os
import sys

import yaml
from dmoj.config import ConfigNode

problem_dirs = ()
env = ConfigNode(defaults={
    'selftest_sandboxing': True,
    'runtime': {
    }
}, dynamic=False)
_root = os.path.dirname(__file__)
fs_encoding = os.environ.get('DMOJ_ENCODING', sys.getfilesystemencoding())

log_file = server_host = server_port = no_ansi = no_ansi_emu = no_watchdog = problem_regex = case_regex = None
api_listen = None

startup_warnings = []

only_executors = set()
exclude_executors = set()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def unicodify(string):
    if isinstance(string, str):
        return string.decode(fs_encoding)
    return string


def load_env(cli=False):  # pragma: no cover
    global log_file, env, judge_key, server_url, problem_data_dir
    _parser = argparse.ArgumentParser(description='''
        Spawns a judge for a submission server.
    ''')
    if not cli:
        _parser.add_argument('judge_key', nargs='?', help='judge key (overrides configuration)')

        _parser.add_argument('-u', '--server-url', default='http://127.0.0.1:4151/pub?topic=submission',
                             help='Server Host address to listen for judge API')
        _parser.add_argument('-p', '--problem-dir', default=os.path.join(BASE_DIR, 'problemdata'))
        _parser.add_argument('-n', '--nsq-url', default='http://127.0.0.1:4161')
        _parser.add_argument('-D', '--data-url', default='http://127.0.0.1')

    _parser.add_argument('-c', '--config', type=str, default=None, required=True,
                         help='file to load judge configurations from')

    _args = _parser.parse_args()

    judge_key = _args.judge_key

    server_url = _args.server_url

    problem_data_dir = _args.problem_dir

    nsq_url = _args.nsq_url

    log_file = '/var/log/judge.log'
    env['server_url'] = server_url
    env['judge_key'] = judge_key
    env['problem_data_dir'] = problem_data_dir
    env['nsq_url'] = nsq_url
    env['data_url'] = _args.data_url
    env['log_file'] = log_file
    if not os.path.exists(problem_data_dir):
        os.mkdir(problem_data_dir)

    model_file = _args.config

    with open(model_file) as init_file:
        env.update(yaml.safe_load(init_file))

    # log_file = getattr(_args, 'log_file', None)


def get_problem_root(pid):
    path = os.path.join(env['problem_data_dir'], str(pid))
    if not os.path.exists(path):
        os.mkdir(path)
    return path



def get_problem_roots():
    return problem_dirs


def get_supported_problems():
    """
    Fetches a list of all problems supported by this judge.
    :return:
        A list of all problems in tuple format: (problem id, mtime)
    """
    problems = []
    for dir in get_problem_roots():
        for problem in os.listdir(dir):
            if isinstance(problem, str):
                problem = problem.decode(fs_encoding)
            if os.access(os.path.join(dir, problem, 'init.yml'), os.R_OK):
                problems.append((problem, os.path.getmtime(os.path.join(dir, problem))))
    return problems


def get_runtime_versions():
    from dmoj.executors import executors
    return {name: clazz.Executor.get_runtime_versions() for name, clazz in executors.iteritems()}

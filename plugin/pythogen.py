# -*- coding: utf-8 -*-
#!/usr/bin/env python
from __future__ import absolute_import, unicode_literals

import functools
import inspect
import json
import logging
import os
import sys
import textwrap
import traceback
import subprocess as sub

from importlib import import_module
from logging.handlers import WatchedFileHandler

import vim


_storage = {}

RUNTIME_PATH = vim.eval("&runtimepath").split(',')

SETTINGS_PLACE = '.vimrcpy'


def eval_vim_args_with_python(fn, argnames, varargs):
    def vim_eval_a(name):
        return vim.eval('a:%s' % name)

    def vim_eval_range(*args):
        return (vim.eval('a:firstline'), vim.eval('a:lastline'))

    def get_evaluator(name):
        return {
            'vimrange': vim_eval_range,
        }.get(name, vim_eval_a)

    args = [get_evaluator(name)(name) for name in argnames]

    if varargs:
        argn = int(vim.eval('a:0'))

        for j in xrange(1, argn + 1):
            args.append(vim.eval('a:%s' % j))

    vim.command('return "{}"'.format(fn(*args)))


def carbonate():
    """ Load all python modules from bundle directory """

    gin = Gen(__name__)

    gin.settings.option('enabled', default=True)

    if not gin.settings['enabled']:
        return

    for path in RUNTIME_PATH:
        unused, plugin_name = os.path.split(path)

        plugin_path = os.path.join(path, 'plugin')

        if plugin_path not in sys.path:
            sys.path.append(plugin_path)
            path_was_appended = True

        else:
            path_was_appended = False

        try:
            plugin_module = import_module(plugin_name)

        except Exception as e:
            gin.log.info('Import module error: %r %r', plugin_name, e)

            if path_was_appended:
                sys.path.remove(plugin_path)

            continue

        vim.command('let g:loaded_python_plugin_%s = 1' %
                    plugin_name.replace('-', '_'))

        gin.log.info('Loaded: %r', plugin_module)


class TextObject(object):
    """ Base class for custom vim textobject """
    pass


class ExCommand(object):
    """ Base class for custom vim commands """
    pass


class Operator(object):
    """ Base class for custom vim operator """
    pass


class Movement(object):
    """ Base class for custom vim movement """
    pass


class Settings(object):
    def __init__(self, name):
        self.name = name
        self._storage = {}
        self._options = {}

        self.force_load()

    @property
    def file_name(self):
        return os.path.join(os.environ['HOME'], SETTINGS_PLACE,
                            self.name) + '.json'

    def force_load(self):
        try:
            self.load()

        except Exception:
            if os.path.exists(self.file_name):
                # If file exists and load failed, create backup before saving
                # clean settings.
                sub.check_call(['mv', self.file_name, self.file_name + '~'])

            # Save clean
            self.save()
            self.load()

    def load(self):
        with open(self.file_name, 'rb') as f:
            self._storage = json.load(f)

    def save(self):
        sub.check_call(['mkdir', '-p', os.path.dirname(self.file_name)])

        with open(self.file_name, 'wb') as f:
            json.dump(dict(self.items()), f,
                      ensure_ascii=False, sort_keys=True, indent=4)

    def option(self, name, *args, **kwargs):
        if 'default' not in kwargs:
            kwargs['default'] = None

        self._options[name] = kwargs

        if name not in self._storage:
            self.save()
            self.load()

    def items(self):
        return {k: self[k] for k in self._options.keys()}

    def __getattr__(self, name):
        try:
            return self[name]
        except Exception:
            return super(Settings, self).__getattr__(name)

    def __getitem__(self, name):
        # Return stored value or default value for this option
        return self._storage[name] if name in self._storage else \
            self._options[name]['default']

    def __setitem__(self, name, value):
        self.force_load()
        self._storage[name] = value
        self.save()


class Plugins(dict):
    def register(self, name, plugin):
        if name in self:
            raise Exception('Already existed plugin: %r', name)

        self[name] = plugin


_plugins = Plugins()


class Gen(object):
    """ Main entry-point for individual plugin """

    def __init__(self, name):
        self.name = name

        _plugins.register(self.name, self)

        self._methods = {}

        self.log = logging.getLogger(self.name)
        # self.log.setLevel(logging.DEBUG)

        self.settings.option('LOG_PATH', default=None)

        if self.settings.LOG_PATH:
            if not os.path.exists(self.settings.LOG_PATH):
                os.makedirs(self.settings.LOG_PATH)

            log_file_name = '%s.log' % os.path.join(self.settings.LOG_PATH,
                                                    self.name)

            handler = WatchedFileHandler(log_file_name, 'w')
            fm = logging.Formatter('%(levelname)s: %(message)s')
            handler.setFormatter(fm)
            self.log.addHandler(handler)

    @property
    def settings(self):
        if not getattr(self, '_settings', False):
            self._settings = Settings(self.name)

        return self._settings

    @classmethod
    def get(cls, name):
        return _plugins.get(name)

    def get_method(self, name):
        return self._methods[name]

    def vim_func(self, fn):
        """
        Decorator to create vim-script-function that call wraped
        python-function
        """

        name = '_'.join([self.name.capitalize(), fn.__name__]). \
            replace('-', '_')

        self.make_vim_function(fn, name)

        return fn

    def make_vim_function(self, fn, name):
        log.debug('Make vim function %s %r', name, fn)

        template = """
            function! %(vim_function)s(%(vim_args)s) %(range)s
            python << endpython
            from pythogen import Gen
            Gen.get('%(plugin_name)s').get_method('%(python_method)s')()
            endpython
            endfunction
        """

        spec = inspect.getargspec(fn)

        vim_args = [a for a in spec.args if a not in ['vimrange']]

        if spec.varargs:
            vim_args.append('...')

        declaration = textwrap.dedent(template) % {
            'vim_function': name,
            'vim_args': ', '.join(vim_args),
            'range': 'range' if 'vimrange' in spec.args else '',
            'plugin_name': self.name,
            'python_method': fn.__name__,
        }

        log.debug('make_vim_function declaration: %s', declaration)

        @functools.wraps(fn)
        def wrapper():
            eval_vim_args_with_python(
                fn,
                spec.args,
                varargs=bool(spec.varargs)
            )

        self._methods[fn.__name__] = wrapper

        vim.command(declaration)

# -*- coding: utf-8 -*-
#!/usr/bin/env python

import functools
import inspect
import textwrap

import vim


_storage = {}


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


def _make_vimfunction(fn):
    template = """
        function! %(vim_function)s(%(vim_args)s) %(range)s
        python << endpython
        import pythogen
        pythogen._storage['%(python_method)s']()
        endpython
        endfunction
    """

    spec = inspect.getargspec(fn)

    vim_args = [a for a in spec.args if a not in ['vimrange']]

    if spec.varargs:
        vim_args.append('...')

    declaration = textwrap.dedent(template) % {
        'vim_function': fn.__name__.capitalize(),
        'vim_args': ', '.join(vim_args),
        'range': 'range' if 'vimrange' in spec.args else '',
        'python_method': fn.__name__,
    }

    @functools.wraps(fn)
    def wrapper():
        eval_vim_args_with_python(
            fn,
            spec.args,
            varargs=bool(spec.varargs)
        )

    _storage[fn.__name__] = wrapper

    vim.command(declaration)


def make_vimfunction(fn):
    _make_vimfunction(fn)

    return fn


def run(*args, **kwargs):
    def decorator(fn):
        fn(*args, **kwargs)

        return fn

    return decorator


def carbonate():
    # TODO load all python modules from bundle directory
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

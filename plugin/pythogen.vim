" pythogen.vim -- Vim python plugins autoloader and helper
" @Author       : Sergey Ivanov (ivanov.waltz@gmail.com)
" vi: ft=vim:tw=80:sw=4:ts=4:fdm=marker

if ! has('python') || v:version < 703
	echoerr "Unable to start orgmode. Orgmode depends on Vim >= 7.3 with Python support complied in."
	finish
endif

" load plugin just once
if &cp || exists("g:loaded_pythogen")
    finish
endif
let g:loaded_pythogen = 1

python << endpython
import os
import sys
import vim
for path in vim.eval("&runtimepath").split(','):
    unused, name = os.path.split(path)

    if name == 'vim-pythogen':
        plugin_path = os.path.join(path, 'plugin')

        if plugin_path not in sys.path:
            sys.path.append(plugin_path)
            try:
                import pythogen
            except Exception:
                pass
            else:
                pythogen.carbonate()

            break
endpython

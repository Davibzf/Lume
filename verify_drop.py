"""Verificação de drops assíncronos no loop real, também usada no EXE empacotado."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import struct
import tempfile


def post_files(hwnd, paths):
    data = struct.pack('<IiiII', 20, 0, 0, 0, 1) + ('\0'.join(map(str, paths)) + '\0\0').encode('utf-16-le')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel.GlobalLock.restype = ctypes.c_void_p
    kernel.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel.GlobalFree.argtypes = [wintypes.HGLOBAL]
    handle = kernel.GlobalAlloc(0x42, len(data))
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    pointer = kernel.GlobalLock(handle)
    if not pointer:
        kernel.GlobalFree(handle)
        raise ctypes.WinError(ctypes.get_last_error())
    ctypes.memmove(pointer, data, len(data))
    kernel.GlobalUnlock(handle)
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user.PostMessageW.restype = wintypes.BOOL
    if not user.PostMessageW(hwnd, 0x233, handle, 0):
        kernel.GlobalFree(handle)
        raise ctypes.WinError(ctypes.get_last_error())


def exercise_drop(root, app):
    with tempfile.TemporaryDirectory() as folder:
        media = [Path(folder) / f'gravação reunião {index}.{"wav" if index % 2 else "mp4"}' for index in range(20)]
        for path in media:
            path.touch()
        errors = []
        received = []
        original_error = root.report_callback_exception
        original_receive = app.file_drop.on_files
        root.report_callback_exception = lambda kind, error, tb: errors.append(str(error))
        def receive(paths):
            received.append(paths)
            original_receive(paths)
        app.file_drop.on_files = receive
        app.editor.insert('1.0', 'Texto editado preservado.')
        for index, path in enumerate(media):
            root.after(100 + index * 50, lambda path=path: post_files(app.file_drop.hwnd, [path]))
        root.after(1600, root.quit)
        try:
            root.mainloop()
        finally:
            app.file_drop.on_files = original_receive
            root.report_callback_exception = original_error
        result = {'success': app.source.get() == str(media[-1]) and len(received) == 20 and not errors,
                  'posted_drops': len(received), 'errors': errors,
                  'editor_preserved': app.editor.get('1.0', 'end-1c') == 'Texto editado preservado.'}
        assert result['success'] and result['editor_preserved'], result
        return result

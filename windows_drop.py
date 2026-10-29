"""Recebe arquivos do Explorer com a API nativa, sem dependências adicionais."""
import ctypes
from ctypes import wintypes
import logging


class WindowsFileDrop:
    def __init__(self, root, on_files):
        self.root = root
        self.on_files = on_files
        self.active = False
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        self.shell = ctypes.WinDLL('shell32', use_last_error=True)
        self.controls = ctypes.WinDLL('comctl32', use_last_error=True)
        self.user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        self.user.GetAncestor.restype = wintypes.HWND
        self.shell.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
        self.shell.DragAcceptFiles.restype = None
        self.shell.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
        self.shell.DragQueryFileW.restype = wintypes.UINT
        self.shell.DragFinish.argtypes = [wintypes.HANDLE]
        self.shell.DragFinish.restype = None
        prototype = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                                     wintypes.WPARAM, wintypes.LPARAM, ctypes.c_size_t, ctypes.c_size_t)
        self.callback = prototype(self.dispatch)
        self.controls.SetWindowSubclass.argtypes = [wintypes.HWND, prototype, ctypes.c_size_t, ctypes.c_size_t]
        self.controls.SetWindowSubclass.restype = wintypes.BOOL
        self.controls.RemoveWindowSubclass.argtypes = [wintypes.HWND, prototype, ctypes.c_size_t]
        self.controls.RemoveWindowSubclass.restype = wintypes.BOOL
        self.controls.DefSubclassProc.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.controls.DefSubclassProc.restype = ctypes.c_ssize_t
        root.update_idletasks()
        self.hwnd = self.user.GetAncestor(root.winfo_id(), 2)
        if not self.hwnd or not self.controls.SetWindowSubclass(self.hwnd, self.callback, id(self), 0):
            raise OSError('Não foi possível ativar a seleção por arrastar e soltar.')
        self.active = True
        self.shell.DragAcceptFiles(self.hwnd, True)
        root.bind('<Destroy>', self.on_destroy, add='+')

    def dispatch(self, hwnd, message, wparam, lparam, subclass_id, reference):
        if message == 0x233:  # WM_DROPFILES: o receptor passa a ser dono do HDROP.
            try:
                count = self.shell.DragQueryFileW(wparam, 0xFFFFFFFF, None, 0)
                paths = []
                # Dois nomes bastam para a interface rejeitar seleção múltipla.
                for index in range(min(count, 2)):
                    size = self.shell.DragQueryFileW(wparam, index, None, 0)
                    buffer = ctypes.create_unicode_buffer(size + 1)
                    self.shell.DragQueryFileW(wparam, index, buffer, size + 1)
                    paths.append(buffer.value)
                # Não chamar Tk aqui: o callback nativo interrompe o loop Tcl.
                self.on_files(paths)
            except Exception:
                logging.exception('Falha ao receber arquivo arrastado')
            finally:
                self.shell.DragFinish(wparam)
            return 0
        return self.controls.DefSubclassProc(hwnd, message, wparam, lparam)

    def on_destroy(self, event):
        if event.widget is self.root and self.active:
            self.shell.DragAcceptFiles(self.hwnd, False)
            self.controls.RemoveWindowSubclass(self.hwnd, self.callback, id(self))
            self.active = False

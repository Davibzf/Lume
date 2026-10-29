"""Testes da interface Tk real; nenhuma mídia ou modelo usa a rede."""
import os
from pathlib import Path
import tempfile
import threading
import tkinter as tk
import unittest
from unittest.mock import patch

from app import App
from engine import Cancelled, Segment, Transcript


@unittest.skipIf(os.name != "nt" and not os.environ.get("DISPLAY"), "Tk precisa de um desktop")
class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.app = App(self.root)
        self.root.update_idletasks()

    def tearDown(self):
        if self.app.worker and self.app.worker.is_alive():
            self.app.cancel.set()
            self.app.worker.join(timeout=5)
        try:
            self.root.update_idletasks()
            for callback in self.root.tk.call("after", "info"):
                self.root.after_cancel(callback)
            self.root.destroy()
        except tk.TclError:
            pass

    def test_progress_shows_engine_percentage_and_completion(self):
        self.app.queue.put(("progress", ("transcribe", .42, "Transcrevendo localmente…")))
        self.app.poll()
        self.assertEqual(self.app.progress["value"], 42)
        self.assertIn("42%", self.app.status.get())
        self.assertGreaterEqual(self.app.progress.winfo_height(), 10)
        self.app.queue.put(("progress", ("transcribe", None, "Carregando modelo…")))
        self.app.poll()
        self.assertNotIn("%", self.app.status.get())
        self.app.queue.put(("result", Transcript([Segment(0, 1, "Olá")], "pt")))
        self.app.poll()
        self.assertEqual(self.app.progress["value"], 100)

    def test_dropped_media_validates_selection_and_preserves_edits(self):
        with tempfile.TemporaryDirectory() as folder:
            media = Path(folder) / 'reunião ação com espaços.MP3'
            media.touch()
            other = Path(folder) / 'outro.wav'
            other.touch()
            invalid = Path(folder) / 'texto.txt'
            invalid.touch()
            self.app.editor.insert('1.0', 'Texto que ainda não salvei.')
            self.app.receive_files([str(media)])
            self.assertEqual(self.app.source.get(), str(media))
            self.assertEqual(self.app.file_display.get(), media.name)
            self.assertIn('Arquivo selecionado', self.app.file_hint['text'])
            self.assertEqual(self.app.editor.get('1.0', 'end-1c'), 'Texto que ainda não salvei.')
            with patch('app.messagebox.showwarning') as warning:
                for files in ([str(media), str(other)], [folder], [str(invalid)], [str(media.parent / 'sumiu.mp4')]):
                    self.app.receive_files(files)
                    self.assertEqual(self.app.source.get(), str(media))
                self.assertEqual(warning.call_count, 4)
            self.app.set_busy(True)
            self.app.status.set('Transcrevendo… 42%')
            self.app.receive_files([str(other)])
            self.assertEqual(self.app.source.get(), str(media))
            self.assertEqual(self.app.status.get(), 'Transcrevendo… 42%')
            self.assertIn('Lume', self.root.title())

    def test_windows_drop_dispatches_unicode_paths(self):
        import ctypes
        from ctypes import wintypes
        import struct
        self.root.update()
        with tempfile.TemporaryDirectory() as folder:
            media = Path(folder) / 'vídeo reunião com espaços.mp4'
            media.touch()
            data = struct.pack('<IiiII', 20, 0, 0, 0, 1) + (str(media) + '\0\0').encode('utf-16-le')
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
            kernel.GlobalAlloc.restype = wintypes.HGLOBAL
            kernel.GlobalLock.argtypes = [wintypes.HGLOBAL]
            kernel.GlobalLock.restype = ctypes.c_void_p
            kernel.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
            handle = kernel.GlobalAlloc(0x42, len(data))
            self.assertTrue(handle)
            pointer = kernel.GlobalLock(handle)
            ctypes.memmove(pointer, data, len(data))
            kernel.GlobalUnlock(handle)
            user = ctypes.WinDLL('user32', use_last_error=True)
            user.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user.SendMessageW.restype = ctypes.c_ssize_t
            # Mensagem real dirigida somente à janela Tk criada por este teste.
            user.SendMessageW(self.app.file_drop.hwnd, 0x233, handle, 0)
            self.app.poll()
            self.root.update()
            self.assertEqual(self.app.source.get(), str(media))
            self.assertTrue(self.app.file_drop.active)
            self.root.destroy()
            self.assertFalse(self.app.file_drop.active)

    def test_queue_result_and_progress(self):
        self.app.editor.configure(state="disabled")
        self.app.queue.put(("progress", ("transcribe", .42, "Teste")))
        self.app.queue.put(("result", Transcript([Segment(0, 1, "Olá teste")], "pt")))
        self.app.poll()
        self.assertEqual(self.app.progress["value"], 100)
        self.assertEqual(self.app.editor.get("1.0", "end-1c"), "Olá teste")
        self.assertEqual(str(self.app.editor["state"]), "normal")
        self.assertEqual(str(self.app.export_buttons[0]["state"]), "normal")

    def test_discard_confirmation(self):
        self.app.transcript = Transcript([Segment(0, 1, "Teste")], "pt")
        self.app.editor.insert("1.0", "Teste")
        with patch("app.messagebox.askyesno", return_value=False) as ask:
            self.assertFalse(self.app.confirm_discard())
            ask.assert_called_once()
        self.app.saved_text = "Teste"
        self.assertTrue(self.app.confirm_discard())

    def test_file_selection_has_visible_confirmation_and_swap_action(self):
        self.app.source.set(str(Path(tempfile.gettempdir()) / 'minha gravação.mp3'))
        self.assertIn('Trocar arquivo', self.app.select_button['text'])
        self.assertEqual(self.app.file_hint['text'], '✓  Arquivo selecionado')
        self.assertEqual(self.app.file_display.get(), 'minha gravação.mp3')
        self.assertIn('Clique em Transcrever', self.app.status.get())
        self.app.set_busy(True)
        self.app.status.set('Transcrevendo localmente…')
        self.app.source.set(str(Path(tempfile.gettempdir()) / 'outro.mp4'))
        self.assertIn('disabled', self.app.select_button.state())
        self.assertEqual(self.app.status.get(), 'Transcrevendo localmente…')
        self.app.source.set('')
        self.assertIn('Abrir vídeo', self.app.select_button['text'])
        self.assertIn('MP4', self.app.file_hint['text'])

    def test_selectors_have_one_surface_and_arrow_still_opens_menu(self):
        self.root.update()
        self.assertEqual(
            self.app.style.lookup('TCombobox', 'background', ('readonly',)),
            self.app.style.lookup('Soft.TFrame', 'background'),
        )
        for combo in (self.app.model_combo, self.app.language_combo):
            self.assertNotIn(combo.identify(combo.winfo_width() - 1, combo.winfo_height() // 2), ('downarrow', 'Rounded.downarrow'))
            self.assertEqual(combo.identify(combo.winfo_width() - 20, combo.winfo_height() // 2), 'Rounded.downarrow')
            try:
                combo.event_generate('<Button-1>', x=combo.winfo_width() - 20, y=combo.winfo_height() // 2)
                self.root.update()
                popup = self.root.tk.call('ttk::combobox::PopdownWindow', str(combo))
                self.assertTrue(int(self.root.tk.call('winfo', 'ismapped', popup)))
            finally:
                self.root.tk.call('ttk::combobox::Unpost', str(combo))

    def test_unsaved_typing_is_protected_without_a_transcript(self):
        self.app.editor.insert("1.0", "Anotação não salva")
        with patch("app.messagebox.askyesno", return_value=False):
            self.assertFalse(self.app.confirm_discard())

    def test_preserve_original_file(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "original.wav"
            source.write_bytes(b"original")
            self.app.source.set(str(source))
            self.app.transcript = Transcript([Segment(0, 1, "Teste")], "pt")
            with patch("app.filedialog.asksaveasfilename", return_value=str(source)), patch("app.messagebox.showerror") as error:
                self.app.save("txt")
                error.assert_called_once()
            self.assertEqual(source.read_bytes(), b"original")

    def test_geometry_keeps_controls_visible(self):
        for geometry in ("1160x800", "980x780", "900x700", "760x660", "640x640"):
            with self.subTest(geometry=geometry):
                self.app.source.set(str(Path(tempfile.gettempdir()) / 'gravação selecionada.mp3'))
                self.app.model_status.set("○ Modelo ainda não baixado (aproximadamente 600 MB–1,1 GB)")
                self.app.status.set("Preparando seu arquivo e verificando o modelo local. Aguarde alguns instantes para continuar a transcrição.")
                self.root.geometry(geometry)
                self.root.update()
                def inspect(widget):
                    for child in widget.winfo_children():
                        if child.winfo_manager():
                            self.assertTrue(child.winfo_ismapped(), str(child))
                            x = child.winfo_rootx() - self.root.winfo_rootx()
                            y = child.winfo_rooty() - self.root.winfo_rooty()
                            self.assertGreaterEqual(x, 0, str(child))
                            self.assertGreaterEqual(y, 0, str(child))
                            self.assertLessEqual(x + child.winfo_width(), self.root.winfo_width(), str(child))
                            self.assertLessEqual(y + child.winfo_height(), self.root.winfo_height(), str(child))
                        inspect(child)
                inspect(self.root)
                for button in self.app.export_buttons + [self.app.folder_button]:
                    self.assertGreater(button.winfo_width(), 50)
                    self.assertGreater(button.winfo_height(), 20)
                self.assertGreater(self.app.editor.winfo_height(), 30)
                placeholder = self.app.empty_state
                if placeholder.winfo_ismapped():
                    self.assertGreaterEqual(placeholder.winfo_y(), 0)
                    self.assertGreaterEqual(placeholder.winfo_x(), 0)
                    self.assertLessEqual(placeholder.winfo_y() + placeholder.winfo_height(), self.app.editor.frame.winfo_height())
                    self.assertLessEqual(placeholder.winfo_x() + placeholder.winfo_width(), self.app.editor.frame.winfo_width())

    def test_reflow_preserves_editor_contents_and_configuration(self):
        self.app.editor.insert("1.0", "Revisão que não pode se perder.")
        self.app.language.set("Inglês")
        self.app.source.set(str(Path(tempfile.gettempdir()) / "gravação.mp4"))
        for width, mode in ((640, "narrow"), (1160, "wide"), (760, "narrow"), (900, "wide"), (640, "narrow")):
            self.root.geometry(f"{width}x700")
            self.root.update()
            self.assertEqual(self.app.layout_mode, mode)
            self.assertEqual(self.app.editor.get("1.0", "end-1c"), "Revisão que não pode se perder.")
            self.assertEqual(self.app.language.get(), "Inglês")
            self.assertEqual(self.app.file_display.get(), "gravação.mp4")
            config, editor = self.app.config_card, self.app.editor_card
            if mode == "narrow":
                self.assertGreater(editor.winfo_y(), config.winfo_y() + config.winfo_height())
                self.assertGreater(editor.winfo_width(), self.root.winfo_width() - 80)
            else:
                self.assertGreater(editor.winfo_x(), config.winfo_x() + config.winfo_width())

    def test_resize_preserves_running_and_result_states(self):
        self.app.set_busy(True)
        self.app.editor.configure(state="disabled")
        self.app.queue.put(("progress", ("transcribe", .42, "Transcrevendo localmente…")))
        self.app.poll()
        for geometry in ("640x640", "760x660", "900x700", "1160x800"):
            with self.subTest(state="running", geometry=geometry):
                self.root.geometry(geometry)
                self.root.update()
                self.assertEqual(self.app.progress["value"], 42)
                self.assertEqual(str(self.app.editor["state"]), "disabled")
                self.assertIn("disabled", self.app.start_button.state())
                self.assertNotIn("disabled", self.app.cancel_button.state())
                self.assertTrue(self.app.status_label.winfo_ismapped())
        self.app.queue.put(("result", Transcript([Segment(0, 1, "Resultado revisável")], "pt")))
        self.app.queue.put(("done", None))
        self.app.poll()
        for geometry in ("640x640", "760x660", "900x700", "1160x800"):
            with self.subTest(state="result", geometry=geometry):
                self.root.geometry(geometry)
                self.root.update()
                self.assertEqual(self.app.editor.get("1.0", "end-1c"), "Resultado revisável")
                self.assertEqual(str(self.app.editor["state"]), "normal")
                self.assertEqual(self.app.empty_state.winfo_manager(), "")
                self.assertTrue(all("disabled" not in button.state() for button in self.app.export_buttons))
                self.assertIn("disabled", self.app.cancel_button.state())

    def test_empty_state_disappears_without_polluting_transcript(self):
        self.root.update()
        self.app.editor.focus_get = lambda: None
        self.app.refresh_empty_state()
        self.assertEqual(self.app.empty_state.winfo_manager(), "place")
        self.assertEqual(self.app.editor.get("1.0", "end-1c"), "")
        self.app.editor.insert("1.0", "Minha primeira frase.")
        self.root.update()
        self.assertEqual(self.app.empty_state.winfo_manager(), "")
        self.assertEqual(self.app.editor.get("1.0", "end-1c"), "Minha primeira frase.")

    def test_file_display_shows_filename_and_preserves_path(self):
        path = str(Path(tempfile.gettempdir()) / "pasta de vídeos" / "minha reunião.mp4")
        self.app.source.set(path)
        self.assertEqual(self.app.file_display.get(), "minha reunião.mp4")
        self.assertEqual(self.app.source.get(), path)
        self.app.source.set("")
        self.assertEqual(self.app.file_display.get(), "Nenhum arquivo selecionado")

    def test_preserve_transcript_source_after_selecting_another_file(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "gravacao_a.wav"
            original.write_bytes(b"original A")
            self.app.pending_source = original.resolve()
            self.app.queue.put(("result", Transcript([Segment(0, 1, "Teste")], "pt")))
            self.app.poll()
            self.app.source.set(str(Path(directory) / "gravacao_b.wav"))
            with patch("app.filedialog.asksaveasfilename", return_value=str(original)) as dialog, patch("app.messagebox.showerror") as error:
                self.app.save("txt")
                error.assert_called_once()
                self.assertEqual(dialog.call_args.kwargs["initialfile"], "gravacao_a.txt")
            self.assertEqual(original.read_bytes(), b"original A")

    def test_transcribe_locks_editor_until_worker_finishes(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "audio.wav"
            source.write_bytes(b"test")
            self.app.source.set(str(source))
            with patch.object(self.app.models, "ensure", side_effect=Cancelled()):
                self.app.start("transcribe")
                self.assertEqual(str(self.app.editor["state"]), "disabled")
                self.app.worker.join(timeout=5)
            with patch("app.messagebox.showerror"):
                self.app.poll()
            self.assertEqual(str(self.app.editor["state"]), "normal")
            self.assertFalse(self.app.worker.is_alive())

    def test_close_download_preserves_unsaved_text_on_refusal(self):
        self.app.transcript = Transcript([Segment(0, 1, "Teste")], "pt")
        self.app.editor.insert("1.0", "Teste")
        self.app.worker = threading.Thread(target=self.app.cancel.wait, daemon=False)
        self.app.worker.start()
        with patch("app.messagebox.askyesno", side_effect=[True, False]) as ask:
            self.app.close()
            self.assertEqual(ask.call_count, 2)
        self.assertFalse(self.app.closing)
        self.assertFalse(self.app.cancel.is_set())
        self.assertEqual(self.app.editor.get("1.0", "end-1c"), "Teste")


if __name__ == "__main__":
    unittest.main()

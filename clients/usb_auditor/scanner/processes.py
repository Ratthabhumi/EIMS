"""Do not pass the frozen application's DLL search directory to Windows tools."""
import ctypes
import logging
import subprocess
import sys


def run_readonly(*args, **kwargs):
    kernel, previous = None, None
    if getattr(sys, 'frozen', False) and sys.platform == 'win32':
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetDllDirectoryW.argtypes = [ctypes.c_ulong, ctypes.c_wchar_p]
        kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        buf = ctypes.create_unicode_buffer(32768)
        kernel.GetDllDirectoryW(len(buf), buf)
        previous = buf.value
        if not kernel.SetDllDirectoryW(None):
            raise ctypes.WinError(ctypes.get_last_error())
    if sys.platform == 'win32':
        kwargs.setdefault('creationflags', subprocess.CREATE_NO_WINDOW)
    try:
        result = subprocess.run(*args, **kwargs)
        logging.getLogger(__name__).info('Collector process executed: %s; exit=%s', args[0][0], result.returncode)
        return result
    finally:
        if kernel:
            kernel.SetDllDirectoryW(previous or None)

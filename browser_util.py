"""打开系统默认浏览器，失败时保留可手动访问的网址。"""
import subprocess
import sys
import webbrowser


def open_browser(url):
    try:
        if sys.platform == 'darwin':
            result = subprocess.run(['/usr/bin/open', url], stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=10)
            opened = result.returncode == 0
        else:
            opened = webbrowser.open(url)
    except (OSError, subprocess.TimeoutExpired):
        opened = False
    if not opened:
        print('请在浏览器地址栏打开：' + url, flush=True)
    return opened

"""为当前文件夹启动服务，重复打开时复用同一实例。"""
import hashlib
import json
import socket
import sys
from pathlib import Path
from urllib import request, error
from browser_util import open_browser

ROOT = Path(__file__).resolve().parent
INSTANCE = hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]


def main():
    available = None
    for port in range(8878, 8899):
        url = 'http://127.0.0.1:' + str(port)
        try:
            with request.urlopen(url + '/api/health', timeout=.4) as response:
                health = json.load(response)
            if health.get('app') == '知研' and health.get('instance') == INSTANCE:
                opened = open_browser(url)
                print(('系统已在运行，已打开浏览器。' if opened else '系统已在运行。') + '\n' + url)
                return
        except (error.URLError, ValueError, OSError):
            pass
        if available is None:
            with socket.socket() as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    probe.bind(('127.0.0.1', port))
                    available = port
                except OSError:
                    pass
    if available is None:
        print('可用端口均被占用，请关闭之前的系统窗口后重试。')
        input('按回车关闭此窗口。')
        return
    import server
    sys.argv = ['server.py', '--port', str(available), '--open']
    server.main()


if __name__ == '__main__':
    main()

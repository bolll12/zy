#!/bin/zsh
cd -- "${0:A:h}" || exit 1
export PYTHONDONTWRITEBYTECODE=1
if [[ -x .venv/bin/python ]]; then
  .venv/bin/python launcher.py
elif command -v python3 >/dev/null 2>&1; then
  python3 launcher.py
else
  print '未找到Python 3。请安装Python 3.9或更新版本，再打开本文件。'
  read 'reply?按回车关闭窗口。'
fi

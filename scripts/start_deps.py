#!/usr/bin/env python3
"""启动本地 Docker 依赖服务，保留已有数据卷。

仅依赖 Python 标准库，可在任意工作目录运行。
"""

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request


# 以脚本所在位置确定项目根目录，避免依赖调用者当前所在目录。
ROOT = Path(__file__).resolve().parent.parent
DOCKER_APP = Path('/Applications/Docker.app')
# Compose 文件中各服务对应的本机健康检查地址。
URLS = {
    'elasticsearch': 'http://127.0.0.1:9200/_cluster/health?wait_for_status=yellow&timeout=1s',
    'qdrant': 'http://127.0.0.1:6333/readyz',
    'embedding': 'http://127.0.0.1:8081/health',
    'kibana': 'http://127.0.0.1:5601/api/status',
}
# 本机健康检查绕过代理，防止 localhost 请求被代理转发。
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def positive_int(value):
    """校验命令行传入的等待秒数必须为正整数。"""
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('Timeout must be a positive integer.') from None
    if number <= 0:
        raise argparse.ArgumentTypeError('Timeout must be a positive integer.')
    return number


def run(command, quiet=False, timeout=None):
    """运行外部命令；失败时抛出异常，由 main 输出诊断信息。"""
    return subprocess.run(
        command, check=True, timeout=timeout,
        stdout=subprocess.DEVNULL if quiet else None,
        stderr=subprocess.DEVNULL if quiet else None,
    )


def succeeds(command, timeout=10):
    """静默执行检查命令，返回命令是否成功。"""
    try:
        run(command, quiet=True, timeout=timeout)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def discover_compose():
    """找到 Docker 和 Compose；macOS 上兼容 Docker Desktop 未加入 PATH 的情况。"""
    if DOCKER_APP.is_dir():
        resources = DOCKER_APP / 'Contents/Resources'
        os.environ['PATH'] = os.pathsep.join([
            os.environ.get('PATH', ''), str(resources / 'bin'),
            str(resources / 'cli-plugins'),
        ])
    if not shutil.which('docker'):
        raise RuntimeError('请先安装 Docker Desktop 或 Docker Engine。')
    if succeeds(['docker', 'compose', 'version']):
        command = ['docker', 'compose']
    elif shutil.which('docker-compose') and succeeds(['docker-compose', 'version']):
        command = ['docker-compose']
    else:
        raise RuntimeError('未找到可用的 Docker Compose，请检查安装。')
    return command + ['-f', str(ROOT / 'docker/docker-compose.yaml')]


def ensure_docker(timeout):
    """确认 Docker 引擎可用；macOS 上引擎未启动时尝试打开 Docker Desktop。"""
    if succeeds(['docker', 'info']):
        return
    if platform.system() != 'Darwin' or not DOCKER_APP.is_dir():
        raise RuntimeError('无法连接 Docker，请启动引擎并检查权限和 Docker context。')
    print('正在启动 Docker Desktop...', flush=True)
    run(['open', '-a', 'Docker'], timeout=15)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if succeeds(['docker', 'info'], timeout=min(10, max(0.1, deadline - time.monotonic()))):
            return
        time.sleep(min(3, max(0, deadline - time.monotonic())))
    raise RuntimeError('等待 Docker 引擎超时，请检查 Docker Desktop 后重试。')


def check_model():
    """在启动容器前检查本地 BGE 配置和模型权重是否存在。"""
    model = ROOT / 'docker/embedding/bge-large-zh-v1.5'

    def nonempty(name):
        path = model / name
        return path.is_file() and path.stat().st_size > 0

    if not nonempty('config.json') or not any(
        nonempty(name) for name in ('pytorch_model.bin', 'model.safetensors')
    ):
        raise RuntimeError(f'缺少 BGE 模型配置或权重，请先下载到 {model}')


def ready(service, compose, timeout=5):
    """检查单个服务健康；MySQL 检查应用账号及两个初始化数据库表。"""
    if service == 'mysql':
        # TCP avoids the temporary socket-only server used during initialization.
        # Confirm that the application account can read both initialized schemas.
        command = (
            'MYSQL_PWD="$MYSQL_PASSWORD" mysql --protocol=TCP '
            '-h 127.0.0.1 -u "$MYSQL_USER" -N -e '
            '"SELECT 1 FROM dw.fact_order LIMIT 1; '
            'SELECT 1 FROM meta.table_info LIMIT 1;"'
        )
        return succeeds(compose + ['exec', '-T', 'mysql', 'sh', '-c', command], timeout)
    try:
        with HTTP.open(URLS[service], timeout=timeout) as response:
            if service == 'elasticsearch':
                return json.load(response).get('status') in ('yellow', 'green')
            return response.status == 200
    except (OSError, urllib.error.URLError, ValueError):
        return False


def wait_ready(compose, services, timeout):
    """轮询服务健康状态，全部就绪返回，超时则指出未就绪服务。"""
    deadline = time.monotonic() + timeout
    pending = list(services)
    while pending:
        for service in pending[:]:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            if ready(service, compose, timeout=min(5, remaining)):
                print(f'已就绪：{service}', flush=True)
                pending.remove(service)
        if not pending:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError(f'等待服务就绪超时：{", ".join(pending)}')
        print(f'等待服务：{", ".join(pending)}', flush=True)
        time.sleep(min(3, max(0, deadline - time.monotonic())))


def diagnostics(compose, services):
    """启动失败时显示容器状态和各依赖的最近日志。"""
    print('容器状态与最近日志：', file=sys.stderr, flush=True)
    for args in (['ps', '-a'], ['logs', '--tail=40', *services]):
        try:
            run(compose + args, timeout=20)
        except (OSError, subprocess.SubprocessError):
            pass


def main():
    """解析参数、拉取镜像、构建并启动依赖，最后等待健康检查通过。"""
    parser = argparse.ArgumentParser(description='拉取镜像、启动依赖并等待就绪，保留已有数据卷。')
    parser.add_argument('--with-kibana', action='store_true', help='同时启动 Kibana')
    parser.add_argument('--timeout', type=positive_int,
                        default=os.environ.get('WAIT_TIMEOUT', '300'),
                        help='就绪等待秒数，默认 WAIT_TIMEOUT 环境变量或 300；不含镜像拉取和构建')
    args = parser.parse_args()
    # Kibana 为可选管理界面，默认只启动 API 所需的四个依赖服务。
    services = ['mysql', 'elasticsearch', 'qdrant', 'embedding']
    pull_services = ['mysql', 'qdrant', 'embedding']
    if args.with_kibana:
        services.append('kibana')
        pull_services.append('kibana')
    compose = None
    started = False
    try:
        check_model()
        compose = discover_compose()
        ensure_docker(args.timeout)
        started = True
        # 先验证 Compose 配置，避免拉取镜像后才发现 YAML 配置错误。
        run(compose + ['config', '--quiet'])
        print('正在拉取依赖镜像...', flush=True)
        run(compose + ['pull', *pull_services])
        # Elasticsearch 使用自定义 Dockerfile 安装 IK 插件，因此单独构建。
        print('正在更新基础镜像并构建 Elasticsearch（含 IK 插件）...', flush=True)
        run(compose + ['build', '--pull', 'elasticsearch'])
        print('正在启动服务，保留已有数据卷...', flush=True)
        run(compose + ['up', '-d', *services])
        # up 不代表服务已完成初始化；逐个检查 HTTP 健康状态和 MySQL 表。
        wait_ready(compose, services, args.timeout)
        run(compose + ['ps'], timeout=20)
    except KeyboardInterrupt:
        print('\n已中断；已启动的容器及数据卷保留。', file=sys.stderr)
        return 130
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f'启动失败：{exc}', file=sys.stderr)
        if started and compose:
            diagnostics(compose, services)
        return 1
    print(f'\n依赖已就绪。请在项目目录 {ROOT} 执行：\n'
          '  source .venv/bin/activate\n'
          '  python -m app.scripts.build_meta_knowledge -c conf/meta_config.yaml\n'
          '  python -m uvicorn main:app --reload\n\n'
          'MySQL 初始化 SQL 仅在空数据卷首次启动时自动执行。')
    return 0


if __name__ == '__main__':
    sys.exit(main())

# 1、安装依赖服务 docker 镜像,  启动
# python3 scripts/start_deps.py --help


# 2、依赖已就绪
# 激活 Python 虚拟环境, .venv 是项目本地的虚拟环境目录。激活后，python、pip 会指向该环境，确保使用项目安装的依赖，而不是系统全局 Python。
    # source .venv/bin/activate
# 元知识构建”脚本。
    # python -m app.scripts.build_meta_knowledge -c conf/meta_config.yaml
# 启动 FastAPI 后端服务。
    # python -m uvicorn main:app --reload

"""
访问:
curl -N http://127.0.0.1:8000/api/query \
    -H 'Content-Type: application/json' \
    -d '{"query":"统计各地区销售总额"}'
"""




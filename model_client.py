"""调用用户配置的Chat Completions服务，密钥只用于当次请求。"""
import ipaddress
import json
import socket
import time
from urllib import error, request
from urllib.parse import urlsplit, urlunsplit

DEFAULT_BASE_URL = 'https://api.deepseek.com'
DEFAULT_MODEL = 'deepseek-flash'


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 不把认证信息跟随重定向发送到另一个接口。
        return None


def configuration(base_url, model, api_key):
    if not all(isinstance(v, str) for v in (base_url, model, api_key)):
        raise ValueError('API地址、模型名称和密钥需要使用文本。')
    base_url, model, api_key = base_url.strip(), model.strip(), api_key.strip()
    if not base_url or len(base_url) > 2000 or any(c.isspace() for c in base_url):
        raise ValueError('请填写有效的API基础地址。')
    try:
        parsed = urlsplit(base_url)
        host = parsed.hostname
        parsed.port
        if parsed.scheme not in ('https', 'http') or not host:
            raise ValueError()
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError()
        try:
            local = ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = host.lower() == 'localhost'
        if parsed.scheme == 'http' and not local:
            raise ValueError('远程API请使用HTTPS地址；本机模型服务可使用HTTP。')
    except ValueError as exc:
        if str(exc).startswith('远程API'):
            raise
        raise ValueError('API地址需以https://开头（本机可用http://），不能包含账号、查询参数或锚点。') from None
    if not model or len(model) > 200 or any(c.isspace() or ord(c) < 32 for c in model):
        raise ValueError('请填写服务商提供的模型名称，名称中不能包含空格或换行。')
    if len(api_key) > 4000 or any(c.isspace() or not 33 <= ord(c) <= 126 for c in api_key):
        raise ValueError('API密钥格式不正确，请检查是否多复制了空格或换行。')
    if not api_key and not local:
        raise ValueError('请在模型设置中填写API密钥。本机免密服务可留空。')
    path = parsed.path.rstrip('/')
    if not path.endswith('/chat/completions'):
        path += '/chat/completions'
    endpoint = urlunsplit((parsed.scheme, parsed.netloc, path, '', ''))
    return endpoint, model, api_key


def chat(base_url, model, api_key, messages, max_tokens=4000, timeout=100):
    endpoint, model, api_key = configuration(base_url, model, api_key)
    body = {'model': model, 'stream': False, 'max_tokens': max_tokens, 'messages': messages}
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    if api_key:
        headers['Authorization'] = 'Bearer ' + api_key
    req = request.Request(endpoint, data=json.dumps(body).encode(), headers=headers, method='POST')
    try:
        with request.build_opener(NoRedirect()).open(req, timeout=timeout) as response:
            raw = response.read(2000001)
        if len(raw) > 2000000:
            raise ValueError('模型响应过长，请换用支持文本回答的模型。')
        payload = json.loads(raw)
    except error.HTTPError as exc:
        hints = {400: '请检查模型名称和接口是否支持Chat Completions。',
                 401: '密钥无效或已过期，请重新填写。',
                 402: '账户余额不足，请检查服务商账户。',
                 403: '当前密钥没有使用该模型的权限。',
                 404: '接口或模型不存在，请检查基础地址及模型名称。',
                 429: '请求频率或额度已达上限，请稍后重试。'}
        hint = '接口发生重定向，请填写最终API地址。' if 300 <= exc.code < 400 else hints.get(exc.code, '模型服务暂时不可用，请稍后重试。')
        # 不回显服务商响应、密钥或请求正文。
        raise ValueError('模型请求未成功（HTTP ' + str(exc.code) + '）。' + hint) from None
    except (socket.timeout, TimeoutError):
        raise ValueError('模型响应超时，请稍后重试，或更换响应更快的模型。') from None
    except (error.URLError, OSError):
        raise ValueError('无法连接模型API，请检查地址、网络，以及本机模型服务是否已启动。') from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError('API未返回有效JSON，请检查是否填写了网页地址而非API地址。') from None
    try:
        text = payload['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError):
        raise ValueError('模型未返回可用正文，请确认接口兼容Chat Completions。') from None
    if not isinstance(text, str) or not text.strip():
        raise ValueError('模型返回正文为空，请换用可直接输出文本的模型后重试。')
    return text.strip()


def test_connection(base_url, model, api_key):
    started = time.perf_counter()
    chat(base_url, model, api_key, [{'role': 'user', 'content': '请只回复OK，不要解释。'}],
         max_tokens=256, timeout=45)
    return {'ok': True, 'model': model.strip(),
            'elapsed_ms': round((time.perf_counter() - started)*1000),
            'message': '连接成功，模型已返回有效回答。'}

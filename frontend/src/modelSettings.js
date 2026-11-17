const STORAGE_KEY = 'zhiyan.model-settings.v1';
export const DEFAULT_SETTINGS = {mode:'local', provider:'deepseek', baseUrl:'https://api.deepseek.com', model:'deepseek-flash', key:''};

export function loadSettings() {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    return {...DEFAULT_SETTINGS,
      mode:value.mode === 'api' ? 'api' : 'local',
      provider:['deepseek','custom','ollama'].includes(value.provider) ? value.provider : 'deepseek',
      baseUrl:typeof value.baseUrl === 'string' ? value.baseUrl : DEFAULT_SETTINGS.baseUrl,
      model:typeof value.model === 'string' ? value.model : DEFAULT_SETTINGS.model,
      key:'',
    };
  } catch { return {...DEFAULT_SETTINGS}; }
}

export function rememberSettings(values) {
  try {
    const {mode,provider,baseUrl,model} = values;
    localStorage.setItem(STORAGE_KEY, JSON.stringify({mode,provider,baseUrl,model}));
    return true;
  } catch { return false; }
}

export function validateSettings(values) {
  if (values.mode === 'local') return '';
  const base = values.baseUrl.trim();
  let url;
  try { url = new URL(base); } catch { return '请填写有效的API基础地址。'; }
  if (!['http:','https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash || /\s/.test(base)) {
    return 'API地址需要以https://开头（本机可用http://），不能包含账号、查询参数或锚点。';
  }
  const local = ['localhost','[::1]'].includes(url.hostname) || /^127(?:\.\d{1,3}){3}$/.test(url.hostname);
  if (url.protocol === 'http:' && !local) return '远程API请使用HTTPS地址。';
  if (!values.model.trim() || /\s/.test(values.model.trim())) return '请填写服务商提供的模型名称。';
  if (!local && !values.key.trim()) return '请填写API密钥；本机免密服务可留空。';
  return '';
}

export function modelRequest(values) {
  return {mode:values.mode, model:values.model.trim(), base_url:values.baseUrl.trim(), api_key:values.key.trim()};
}

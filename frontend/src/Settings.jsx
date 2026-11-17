import React,{useState} from 'react';
import {api} from './api';
import {Icon,useDialog} from './ui';
import {modelRequest,validateSettings} from './modelSettings';

const PRESETS = {
  deepseek:{baseUrl:'https://api.deepseek.com',model:'deepseek-flash'},
  custom:{baseUrl:'',model:''},
  ollama:{baseUrl:'http://127.0.0.1:11434/v1',model:''},
};

export default function Settings({settings,onSave,onClose,onKnowledge}) {
  const [values,setValues]=useState(settings);
  const [testing,setTesting]=useState(false);
  const [result,setResult]=useState(null);
  const dialogRef=useDialog(onClose);
  function update(patch) {
    setValues(current=>({...current,...patch,...('baseUrl' in patch ? {key:''} : {})}));
    setResult(null);
  }
  function chooseProvider(provider) { update({provider,...PRESETS[provider],key:''}); }
  async function test() {
    const error=validateSettings(values);
    if(error){setResult({error:true,message:error});return;}
    setTesting(true);setResult(null);
    try {
      const response=await api('/model/test',modelRequest(values));
      setResult({error:false,message:`连接成功 · ${response.model} · ${(response.elapsed_ms/1000).toFixed(1)}秒`});
    } catch(error) { setResult({error:true,message:error.message}); }
    finally { setTesting(false); }
  }
  function save(event) {
    event.preventDefault();
    const error=validateSettings(values);
    if(error){setResult({error:true,message:error});return;}
    onSave({...values,baseUrl:values.baseUrl.trim(),model:values.model.trim(),key:values.key.trim()});
    onClose();
  }
  return <div className="modal-backdrop centered" onClick={onClose}>
    <section ref={dialogRef} className="settings-dialog" role="dialog" aria-modal="true" aria-label="模型设置" onClick={event=>event.stopPropagation()}>
      <header><div><h2>模型设置</h2><p>配置这次研究使用的模型服务</p></div><button className="icon-button" aria-label="关闭设置" onClick={onClose}><Icon name="close"/></button></header>
      <div className="settings-knowledge"><span>补充研究资料</span><button type="button" className="text-link" onClick={onKnowledge}><Icon name="folder" size={16}/>管理与上传知识<Icon name="arrow" size={15}/></button></div>
      <form onSubmit={save}>
        <div className="mode-choices">
          {[['local','本地证据整理','检索全文与已有评述，无需模型API。'],['api','模型API归纳','使用你配置的模型，根据原文证据形成回答。']].map(([value,title,detail])=><label className={'mode-choice '+(values.mode===value?'active':'')} key={value}>
            <input type="radio" name="mode" checked={values.mode===value} disabled={testing} onChange={()=>update({mode:value})}/><div><b>{title}</b><p>{detail}</p></div>
          </label>)}
        </div>
        {values.mode==='api'&&<fieldset className="model-fields" disabled={testing}>
          <label className="field-label" htmlFor="provider">服务类型</label>
          <select id="provider" value={values.provider} onChange={event=>chooseProvider(event.target.value)}>
            <option value="deepseek">DeepSeek</option><option value="custom">自定义兼容接口</option><option value="ollama">Ollama本机服务</option>
          </select>
          <label className="field-label" htmlFor="baseurl">API基础地址（Base URL）</label>
          <input id="baseurl" type="text" inputMode="url" autoComplete="off" spellCheck={false} maxLength={2000} placeholder="https://你的服务地址/v1" value={values.baseUrl} onChange={event=>update({baseUrl:event.target.value})}/>
          <p className="field-hint">填写服务商提供的基础地址，保留其中的 /v1 等路径；也可填写完整 /chat/completions 地址。</p>
          <label className="field-label" htmlFor="model">模型名称</label>
          <input id="model" type="text" autoComplete="off" spellCheck={false} maxLength={200} placeholder={values.provider==='ollama'?'填写本机已安装的模型名称':'填写账户可用的模型ID'} value={values.model} onChange={event=>update({model:event.target.value})}/>
          <label className="field-label" htmlFor="apikey">API密钥{values.provider==='ollama'?'（本机免密服务可留空）':''}</label>
          <input id="apikey" type="password" autoComplete="off" spellCheck={false} maxLength={4000} placeholder="仅在当前页面会话中使用" value={values.key} onChange={event=>update({key:event.target.value})}/>
          <p className="muted">地址和模型名称会记住；密钥不写入数据库或浏览器存储，刷新后需重新填写。研究时会向此地址发送问题和相关文献片段。</p>
          <div className="model-test"><button className="secondary" type="button" onClick={test}>测试连接</button><span className="field-hint">发送一条简短请求，按服务商规则计费。</span></div>
        </fieldset>}
        {testing&&<p className="model-result" role="status">正在连接模型，请稍候…</p>}
        {result&&<p className={'model-result '+(result.error?'error':'success')} role={result.error?'alert':'status'}>{result.message}</p>}
        <footer><button className="secondary" type="button" onClick={onClose}>取消</button><button className="primary" type="submit" disabled={testing}>保存设置</button></footer>
      </form>
    </section>
  </div>;
}

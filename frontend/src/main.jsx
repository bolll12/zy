import React,{useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {api} from './api';
import {Icon,Spinner} from './ui';
import Library from './Library';
import PaperDrawer from './PaperDrawer';
import Assistant from './Assistant';
import {Collection,Workbench,Process} from './Workbench';
import Settings from './Settings';
import Knowledge from './Knowledge';
import {loadSettings,rememberSettings} from './modelSettings';
import './styles.css';

const NAV=[['library','book','文献库'],['knowledge','folder','知识管理'],['research','spark','研究助手'],['collection','bookmark','证据收藏'],['workbench','edit','综述工作台'],['process','clock','过程记录']];
function App(){
  const [data,setData]=useState(null);const [error,setError]=useState('');const [view,setView]=useState('library');const [selected,setSelected]=useState(null);const [toast,setToast]=useState(null);const [showSettings,setShowSettings]=useState(false);const [settings,setSettings]=useState(loadSettings);const [seed,setSeed]=useState(null);
  const [draft,setDraft]=useState(null);const [saving,setSaving]=useState('saved');const draftRef=useRef(null);const savedRef=useRef('');const revisionRef=useRef(1);const savePromise=useRef(null);const toastTimer=useRef(null);
  const notify=useCallback((text,error=false)=>{setToast({text,error});clearTimeout(toastTimer.current);toastTimer.current=setTimeout(()=>setToast(null),6000);},[]);
  useEffect(()=>{Promise.all([api('/bootstrap'),api('/draft')]).then(([b,d])=>{setData(b);setDraft(d);draftRef.current=d;savedRef.current=d.text;revisionRef.current=d.revision;}).catch(e=>setError(e.message));},[]);
  useEffect(()=>{draftRef.current=draft;},[draft]);
  const saveDraft=useCallback(async()=>{
    if(savePromise.current)await savePromise.current;
    const latest=draftRef.current;if(!latest||latest.text===savedRef.current)return;
    setSaving('saving');
    const text=latest.text;
    const task=api('/draft',{text,revision:revisionRef.current});savePromise.current=task;
    try{const result=await task;revisionRef.current=result.revision;savedRef.current=text;setDraft(d=>({...d,revision:result.revision,updated:result.updated}));setSaving(draftRef.current.text===text?'saved':'dirty');}
    catch(e){setSaving('error');throw e;}
    finally{savePromise.current=null;}
  },[]);
  useEffect(()=>{if(!draft||draft.text===savedRef.current)return;setSaving('dirty');const timer=setTimeout(()=>saveDraft().catch(e=>notify(e.message,true)),900);return()=>clearTimeout(timer);},[draft?.text,notify,saveDraft]);
  useEffect(()=>{const handler=e=>{if(draftRef.current&&draftRef.current.text!==savedRef.current){e.preventDefault();e.returnValue='';}};window.addEventListener('beforeunload',handler);return()=>window.removeEventListener('beforeunload',handler);},[]);
  const collected=useMemo(()=>new Set(data?.collection.map(x=>x.chunk_id)||[]),[data?.collection]);
  async function collect(chunk_id,selected){try{const x=await api('/collection',{chunk_id,selected});setData(d=>({...d,collection:x.collection}));notify(selected?'证据已收藏':'已取消收藏');}catch(e){notify(e.message,true);}}
  function open(paperId,page){const paper=data.papers.find(p=>p.id===paperId);if(!paper){notify('该文献编号不在当前知识库中',true);return;}setSelected({id:paperId,page:Math.min(paper.pages,Math.max(1,page||1)),source:!!page});}
  function research(question='',paper_ids=null){setSelected(null);setSeed({question,paper_ids,key:Date.now()});setView('research');window.scrollTo(0,0);}
  function appendText(text){setDraft(d=>({...d,text:d.text.trimEnd()+'\n\n'+text+'\n'}));notify('已追加到综述末尾');}
  function append(h){appendText(`### 证据摘录：${h.display_title||h.title}\n\n${h.text}\n\n[${h.paper_id}·第${h.page}${h.source_unit||'页'}]`);}
  function noteSaved(id,note,status){setData(d=>({...d,papers:d.papers.map(p=>p.id===id?{...p,note,reading_status:status}:p)}));}
  function navigate(v){setView(v);window.scrollTo(0,0);}
  async function refreshKnowledge(){const latest=await api('/bootstrap');setData(latest);}
  function saveSettings(values){setSettings(values);const remembered=rememberSettings(values);notify(remembered?'模型设置已应用':'设置已应用；浏览器未允许记住地址和模型名称');}
  if(error)return <div className="startup-error"><Icon name="info" size={36}/><h1>系统暂时未连接</h1><p>{error}</p><button className="primary" onClick={()=>window.location.reload()}>重新连接</button></div>;
  if(!data)return <div className="startup-error"><Spinner text="正在载入文献研究系统…"/></div>;
  const common={data,collected,onOpen:open,onCollect:collect,onAppend:append,notify};
  return <div className="app-shell"><aside className="sidebar"><a className="brand" href="#" onClick={e=>{e.preventDefault();navigate('library');}}><div className="brand-mark"><Icon name="book" size={23}/></div><div><strong>知研</strong><span>Agent文献研究系统</span></div></a><div className="sidebar-label">研究空间</div><nav aria-label="主导航">{NAV.map(([id,icon,label])=><button key={id} className={view===id?'active':''} onClick={()=>navigate(id)}><Icon name={icon}/><span>{label}</span>{id==='collection'&&collected.size>0&&<small>{collected.size}</small>}</button>)}</nav><div className="sidebar-bottom"><div className="library-ready"><i/><span>本地知识库已就绪</span><small>{data.papers.length}份资料 · 随时查证</small></div><button className="settings-link" onClick={()=>setShowSettings(true)}><Icon name="settings"/><span>模型设置</span><Icon name="chevron" size={15}/></button><div className="profile"><span className="avatar">知</span><div><strong>知研</strong><span>本机研究空间</span></div></div></div></aside><div className="app-right"><header className="topbar"><div><span>知研</span><Icon name="chevron" size={13}/><strong>工作空间</strong></div><span className="topbar-right">文献研究工作空间<span className="mini-avatar">知</span></span></header><main className="main-content">
      {view==='library'&&<Library {...common} onResearch={research} onKnowledge={()=>navigate('knowledge')}/>}
      {view==='knowledge'&&<Knowledge {...common} onRefresh={refreshKnowledge} onResearch={research}/>}
      {view==='research'&&<Assistant key={seed?.key||'default'} {...common} seed={seed} settings={settings} onAppendText={appendText} onSettings={()=>setShowSettings(true)}/>}
      {view==='collection'&&<Collection {...common} onNavigate={navigate}/>}
      {view==='workbench'&&<Workbench {...common} draft={draft} setDraft={setDraft} saveDraft={saveDraft} saving={saving} onAppendText={appendText}/>}
      {view==='process'&&<Process notify={notify}/>}
    </main></div>{selected&&<PaperDrawer key={selected.id+':'+selected.page} paper={data.papers.find(p=>p.id===selected.id)} initialPage={selected.page} startSource={selected.source} onClose={()=>setSelected(null)} onSaved={noteSaved} onResearch={research} notify={notify}/>} {showSettings&&<Settings settings={settings} onSave={saveSettings} onClose={()=>setShowSettings(false)} onKnowledge={()=>{setShowSettings(false);navigate('knowledge');}}/>} {toast&&<div className={'toast '+(toast.error?'error':'')} role="status"><Icon name={toast.error?'info':'check'} size={18}/>{toast.text}<button className="icon-button" aria-label="关闭提示" onClick={()=>setToast(null)}><Icon name="close" size={15}/></button></div>}</div>;
}
createRoot(document.getElementById('root')).render(<App/>);

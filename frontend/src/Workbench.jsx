import React,{useEffect,useState} from 'react';
import {api,localTime} from './api';
import {Icon,Empty,EvidenceItem,Markdown,Spinner} from './ui';

export function Collection({collected,onCollect,onOpen,onAppend,onNavigate,notify}) {
  const [items,setItems]=useState(null);
  useEffect(()=>{api('/collection').then(setItems).catch(e=>notify(e.message,true));},[collected]);
  return <><div className="page-heading"><div><h1>证据收藏</h1><p>保留原文、页码和来源，写作时随时取用</p></div><button className="secondary" onClick={()=>onNavigate('research')}><Icon name="search" size={17}/>继续研究</button></div><section className="surface"><div className="section-top"><div><h2>已收藏证据</h2><span className="muted">{collected.size} 个片段</span></div></div>{items===null?<Spinner/>:items.length?items.map(h=><EvidenceItem key={h.chunk_id} item={h} collected onCollect={onCollect} onOpen={onOpen} onAppend={onAppend}/>):<Empty title="还没有收藏证据" text="在全文检索或研究结果中，点击“收藏证据”即可保留原文片段。" action={<button className="primary" onClick={()=>onNavigate('library')}>去文献库</button>}/>}</section></>;
}

export function Workbench({draft,setDraft,saveDraft,saving,data,onOpen,onAppendText,notify,collected}) {
  const [preview,setPreview]=useState(false);const [pick,setPick]=useState('');const [exporting,setExporting]=useState(false);
  const count=draft?.text?.replace(/\s/g,'').length||0;
  async function download(fmt){setExporting(true);try{await saveDraft();window.location.assign('/api/export?format='+fmt);}catch(e){notify(e.message,true);}finally{setExporting(false);}}
  const selectedPaper=data.papers.find(p=>p.id===pick)||data.papers[0];
  function addReview(){const p=selectedPaper;if(!p)return;onAppendText(`### ${p.id}　${p.display_title}\n\n${p.review}${p.note?`\n\n我的笔记：${p.note}`:''}`);}
  return <><div className="page-heading"><div><h1>综述工作台</h1><p>在同一份正文里，整理逐篇评述与跨文献分析</p></div><div className="button-row"><button className="secondary" disabled={exporting||!draft} onClick={()=>download('md')}><Icon name="download" size={17}/>Markdown</button><button className="primary" disabled={exporting||!draft} onClick={()=>download('docx')}><Icon name="download" size={17}/>导出Word</button></div></div>
    <div className="editor-layout"><section className="surface editor-surface"><div className="editor-toolbar"><div className="segmented"><button className={!preview?'active':''} onClick={()=>setPreview(false)}><Icon name="edit" size={15}/>编辑</button><button className={preview?'active':''} onClick={()=>setPreview(true)}><Icon name="book" size={15}/>预览</button></div><span className={'save-state '+(saving==='error'?'save-error':'')}>{saving==='saving'?'正在保存…':saving==='dirty'?'待保存':saving==='error'?'保存未成功，请重试':`已保存${draft?.updated?' · '+localTime(draft.updated):''}`}</span><button className="subtle" disabled={!draft||saving==='saving'} onClick={()=>saveDraft().then(()=>notify('综述已保存')).catch(e=>notify(e.message,true))}>保存</button></div>{!draft?<Spinner/>:preview?<div className="document-preview"><Markdown text={draft.text} onSource={onOpen}/></div>:<textarea className="review-editor" aria-label="综述正文" value={draft.text} onChange={e=>setDraft(d=>({...d,text:e.target.value}))} spellCheck={false}/>}<footer className="editor-status"><span>{count.toLocaleString()} 字符 · 支持Markdown标题</span><span>知研 · 本地草稿</span></footer></section>
    <aside className="writer-aside"><section className="surface side-panel"><h3>写作材料</h3><p className="muted">把证据和笔记整理到可编辑的综述中。</p><div className="writing-stat"><span>资料总量</span><b>{data.papers.length} 份</b></div><div className="writing-stat"><span>证据收藏</span><b>{collected.size} 个片段</b></div><label className="field-label" htmlFor="paper-pick">补充文献评述</label><select id="paper-pick" value={selectedPaper?.id||''} disabled={!selectedPaper} onChange={e=>setPick(e.target.value)}>{data.papers.map(p=><option key={p.id} value={p.id}>{p.id} {p.display_title}</option>)}</select><button className="secondary full" disabled={!selectedPaper} onClick={addReview}><Icon name="plus" size={16}/>追加到正文末尾</button></section></aside></div>
  </>;
}

export function Process({notify}) {
  const [events,setEvents]=useState(null);const [kind,setKind]=useState('');
  function load(){api('/events').then(setEvents).catch(e=>notify(e.message,true));}
  useEffect(load,[]);
  const visible=events?.filter(e=>!kind||e.kind===kind);
  return <><div className="page-heading"><div><h1>过程记录</h1><p>记录实际完成的检索、阅读、研究与导出</p></div><a className="secondary" href="/api/export?format=json"><Icon name="download" size={17}/>导出研究记录</a></div><section className="surface"><div className="section-top"><div><h2>操作时间线</h2><span className="muted">本机最近200条实际操作</span></div><div className="button-row"><select aria-label="筛选操作类型" value={kind} onChange={e=>setKind(e.target.value)}><option value="">全部操作</option>{[...new Set(events?.map(x=>x.kind))].map(x=><option key={x}>{x}</option>)}</select><button className="subtle" onClick={load}>刷新</button></div></div>{events===null?<Spinner/>:visible.length?<div className="event-list">{visible.map(e=><div className="event-row" key={e.id}><span className="event-node"/><time>{localTime(e.created)}</time><span className="event-kind">{e.kind}</span><p>{e.detail}</p></div>)}</div>:<Empty title="这里会留下你的研究过程" text="检索全文、查看PDF、保存笔记或导出文档后，真实操作会自动记入时间线。"/>}</section></>;
}

import React,{useMemo,useState} from 'react';
import {api} from './api';
import {Icon,Empty,Spinner,EvidenceItem} from './ui';

export default function Library({data,collected,onOpen,onCollect,onResearch,onAppend,onKnowledge,notify}) {
  const [query,setQuery]=useState(''); const [language,setLanguage]=useState(''); const [topic,setTopic]=useState(''); const [status,setStatus]=useState('');
  const [search,setSearch]=useState(null);const [busy,setBusy]=useState(false);
  const papers=useMemo(()=>data.papers.filter(p=>(!language||p.language===language)&&(!topic||p.topic===topic)&&(!status||p.reading_status===status)),[data.papers,language,topic,status]);
  const read=data.papers.filter(p=>p.reading_status==='已读').length;
  async function submit(e) {
    e?.preventDefault();if(!query.trim()){setSearch(null);return;}
    setBusy(true);try{setSearch(await api('/search',{query,language,topic,paper_ids:status?papers.map(p=>p.id):null}));}catch(e){notify(e.message,true);}finally{setBusy(false);}
  }
  function reset(){setQuery('');setLanguage('');setTopic('');setStatus('');setSearch(null);}
  return <>
    <div className="page-heading"><div><h1>文献库</h1><p>研究文献与自建知识，共{data.papers.length}份资料</p></div><div className="button-row"><button className="secondary" onClick={onKnowledge}><Icon name="plus" size={17}/>上传知识</button><button className="primary" onClick={()=>onResearch()}><Icon name="spark"/>开始研究<Icon name="arrow" size={17}/></button></div></div>
    <section className="stats-strip" aria-label="知识库概况">{[[data.stats.documents,'篇文献',`${data.stats.zh}份中文 · ${data.stats.en}份英文`],[data.stats.pages,'页PDF全文',data.stats.segments?`另有${data.stats.segments}个文本段`:'原始PDF与页序已保留'],[data.stats.chunks.toLocaleString(),'个证据片段','支持回到原文核对'],[read,'篇已读','阅读进度由你记录']].map(([n,label,help])=><div key={label}><strong>{n}</strong><span>{label}</span><small>{help}</small></div>)}</section>
    <section className="surface library-surface">
      <div className="section-top"><div><h2>研究资料</h2><span className="muted">全文已解析，可直接检索与阅读</span></div></div>
      <form className="search-bar" onSubmit={submit}><Icon name="search"/><input aria-label="全文检索" placeholder="输入题名、编号或研究问题，检索文献全文…" value={query} onChange={e=>setQuery(e.target.value)} maxLength={600}/>{query&&<button type="button" className="icon-button" aria-label="清空检索" onClick={()=>{setQuery('');setSearch(null);}}><Icon name="close" size={16}/></button>}<button className="primary" disabled={busy} type="submit">{busy?'检索中…':'全文检索'}</button></form>
      <div className="filter-bar"><div className="language-tabs" role="group" aria-label="语种">{[['','全部语种'],['中文',`中文 ${data.stats.zh}`],['英文',`英文 ${data.stats.en}`]].map(([v,l])=><button key={v} className={v===language?'active':''} onClick={()=>{setLanguage(v);setSearch(null);}}>{l}</button>)}</div><select aria-label="筛选研究主题" value={topic} onChange={e=>{setTopic(e.target.value);setSearch(null);}}><option value="">全部研究主题</option>{data.topics.map(t=><option key={t}>{t}</option>)}</select><select aria-label="筛选阅读状态" value={status} onChange={e=>{setStatus(e.target.value);setSearch(null);}}><option value="">全部阅读状态</option>{['未读','阅读中','已读'].map(t=><option key={t}>{t}</option>)}</select>{(language||topic||status||search)&&<button className="text-link" onClick={reset}>重置</button>}<span className="result-count">{search?`${search.hits.length} 个片段`:`${papers.length} 篇文献`}</span></div>
      {busy ? <Spinner text="正在检索全文证据…"/> : search ? <div className="search-results"><div className="search-summary">“{search.query}”的检索结果 <span>分数用于相关排序，不代表答案正确率。</span></div>{search.hits.length?search.hits.map(h=><EvidenceItem key={h.chunk_id} item={h} collected={collected.has(h.chunk_id)} onCollect={onCollect} onOpen={onOpen} onAppend={onAppend}/>):<Empty title="未找到匹配证据" text="试试更具体的研究术语，或清除筛选条件。"/>}</div> : <div className="paper-table"><div className="table-head"><span>文献名称</span><span>研究主题</span><span>全文</span><span>阅读状态</span><span/></div>{papers.map(p=><button key={p.id} className="paper-row" onClick={()=>onOpen(p.id)}><div className="paper-identity"><span className={'paper-number '+(p.language==='英文'?'english':'')}>{p.id}</span><div><h3>{p.display_title}</h3><p>{p.authors.slice(0,2).join('、')}{p.authors.length>2?' 等':''}<span> · {p.year} · {p.language}</span></p></div></div><span className="topic-label">{p.topic}</span><span className="page-count">{p.pages} {p.source_unit||'页'}</span><span className={'read-status '+(p.reading_status==='已读'?'done':'')}>{p.reading_status==='已读'?<Icon name="check" size={14}/>:<i/>}{p.reading_status}</span><Icon name="chevron" size={16}/></button>)}{!papers.length&&<Empty title="没有符合条件的资料" text="请上传资料，或调整研究主题和阅读状态筛选。"/>}</div>}
    </section>
    <div className="workspace-foot"><span><i className="status-dot"/>资料保存在本机，笔记与收藏可持续积累</span><button className="text-link" onClick={()=>onResearch('如何评价RAG知识库的检索与生成质量？')}>从一个研究问题开始<Icon name="arrow" size={15}/></button></div>
  </>;
}

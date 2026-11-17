import React,{useEffect,useRef} from 'react';

export function useDialog(onClose) {
  const dialogRef=useRef(null);const closeRef=useRef(onClose);closeRef.current=onClose;
  useEffect(()=>{
    const previous=document.activeElement;const overflow=document.body.style.overflow;
    const dialog=dialogRef.current;
    const targets=()=>[...dialog.querySelectorAll('button:not(:disabled),a[href],input:not(:disabled),textarea:not(:disabled),select:not(:disabled)')].filter(el=>el.getClientRects().length);
    targets()[0]?.focus();document.body.style.overflow='hidden';
    const keydown=e=>{
      if(e.key==='Escape'){e.preventDefault();closeRef.current();}
      if(e.key==='Tab'){
        const list=targets();const first=list[0];const last=list.at(-1);
        if(!list.length){e.preventDefault();return;}
        if(e.shiftKey&&(document.activeElement===first||!dialog.contains(document.activeElement))){e.preventDefault();last.focus();}
        else if(!e.shiftKey&&(document.activeElement===last||!dialog.contains(document.activeElement))){e.preventDefault();first.focus();}
      }
    };
    document.addEventListener('keydown',keydown);
    return()=>{document.removeEventListener('keydown',keydown);document.body.style.overflow=overflow;if(previous?.isConnected)previous.focus();};
  },[]);
  return dialogRef;
}

const paths = {
  book: <><path d="M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-2H4z"/><path d="M20 4h-4a3 3 0 0 0-3 3v14a4 4 0 0 1 4-2h3z"/></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/></>,
  spark: <><path d="m12 3 2.2 6.8L21 12l-6.8 2.2L12 21l-2.2-6.8L3 12l6.8-2.2z"/></>,
  bookmark: <path d="M6 3h12v18l-6-4-6 4z"/>,
  edit: <><path d="M13 5H4v15h15v-9"/><path d="m14 3 7 7M9 15l2-6 7-7 4 4-7 7z"/></>,
  clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  settings: <><path d="m9 3-1 3-3 1 1 3-2 2 2 2-1 3 3 1 1 3h6l1-3 3-1-1-3 2-2-2-2 1-3-3-1-1-3z"/><circle cx="12" cy="12" r="3"/></>,
  arrow: <path d="M5 12h14m-5-5 5 5-5 5"/>,
  download: <><path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/></>,
  close: <path d="m6 6 12 12M6 18 18 6"/>,
  check: <path d="m5 12 4 4L19 6"/>,
  external: <><path d="M14 3h7v7m0-7L10 14M10 4H4v16h16v-6"/></>,
  chevron: <path d="m9 5 7 7-7 7"/>,
  plus: <path d="M12 4v16M4 12h16"/>,
  folder: <path d="M3 6h7l2 3h9v12H3z"/>,
  info: <><circle cx="12" cy="12" r="9"/><path d="M12 10v7M12 6v1"/></>,
  menu: <path d="M4 6h16M4 12h16M4 18h16"/>,
};
export function Icon({name, size=19, ...props}) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name] || paths.book}</svg>;
}
export function Empty({title, text, action}) {
  return <div className="empty"><Icon name="folder" size={34}/><h3>{title}</h3><p>{text}</p>{action}</div>;
}
export function Spinner({text='正在读取…'}) { return <div className="loading"><span className="spinner"/>{text}</div>; }

function Inline({text, onSource}) {
  const parts = text.split(/(\[(?:[CE]\d{2}|U\d{6,})·第\d+[页段]\])/g);
  return parts.map((part,i)=> {
    const m=part.match(/^\[((?:[CE]\d{2}|U\d{6,}))·第(\d+)([页段])\]$/);
    return m ? <button key={i} className="citation" onClick={()=>onSource?.(m[1],+m[2])}>{m[1]} · 第{m[2]}{m[3]}</button> : <React.Fragment key={i}>{part}</React.Fragment>;
  });
}
export function Markdown({text='', onSource}) {
  const lines=text.split('\n');
  return <div className="markdown">{lines.map((line,i)=> {
    if (!line.trim()) return null;
    const h=line.match(/^(#{1,3})\s+(.+)/);
    if(h) {const Tag='h'+Math.min(4,h[1].length+1);return <Tag key={i}>{h[2]}</Tag>;}
    if(line.startsWith('!['))return <p className="muted" key={i}>草稿预览不加载 Markdown 图片。</p>;
    if(line.startsWith('|'))return /^[|\s:\-]+$/.test(line) ? null : <p className="md-tableline" key={i}>{line.split('|').filter(x=>x.trim()).map((x,j)=><span key={j}>{x.trim()}</span>)}</p>;
    return <p key={i}><Inline text={line} onSource={onSource}/></p>;
  })}</div>;
}

export function EvidenceItem({item, collected, onCollect, onOpen, onAppend}) {
  return <article className="evidence-item">
    <div className="evidence-meta"><span>{item.paper_id}</span><span>{item.source_unit==='段'?'原文':'PDF'} 第{item.page}{item.source_unit||'页'}</span>{item.score !== undefined && <span className="score">{item.score===0?'按编号定位':`相关排序 ${item.score.toFixed(1)}`}</span>}</div>
    <button className="text-link evidence-title" onClick={()=>onOpen(item.paper_id,item.page)}>{item.display_title || item.title}</button>
    <p className="excerpt">{item.excerpt || item.text}</p>
    <div className="evidence-actions"><button className="subtle" onClick={()=>onOpen(item.paper_id,item.page)}><Icon name="book" size={16}/>查看原文</button><button className={'subtle '+(collected?'selected':'')} onClick={()=>onCollect(item.chunk_id,!collected)}><Icon name={collected?'check':'bookmark'} size={16}/>{collected?'已收藏':'收藏证据'}</button>{onAppend && <button className="subtle" onClick={()=>onAppend(item)}><Icon name="plus" size={16}/>加入综述</button>}</div>
  </article>;
}

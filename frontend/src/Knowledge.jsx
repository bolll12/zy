import React,{useRef,useState} from 'react';
import {api,localTime} from './api';
import {Icon,Empty} from './ui';

const MAX_BYTES=10*1024*1024;
const ACCEPT='.pdf,.docx,.txt,.md';
function fileContent(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(new Error('无法读取这个文件，请重新选择。'));reader.readAsDataURL(file);});}
function fileSize(bytes){return bytes>=1024*1024?`${(bytes/1024/1024).toFixed(1)} MB`:`${Math.max(1,Math.round(bytes/1024))} KB`;}

export default function Knowledge({data,onRefresh,onOpen,onResearch,notify}){
  const [items,setItems]=useState([]);const [topic,setTopic]=useState('自建知识');const [language,setLanguage]=useState('自动识别');const [busy,setBusy]=useState(false);const [dragging,setDragging]=useState(false);
  const input=useRef(null);const uploading=useRef(false);
  const uploaded=data.papers.filter(p=>p.uploaded);
  const pending=items.filter(item=>item.status==='待上传'||item.status==='失败');
  function choose(files){
    if(uploading.current)return;
    const chosen=Array.from(files).slice(0,20);
    if(files.length>20)notify('每批最多选择20个文件，其余文件请下一批上传。',true);
    setItems(chosen.map((file,i)=>{const valid=/\.(pdf|docx|txt|md)$/i.test(file.name)&&file.size>0&&file.size<=MAX_BYTES;return {key:`${Date.now()}-${i}`,file,title:file.name.replace(/\.[^.]+$/,''),status:valid?'待上传':'格式或大小不符',message:valid?'':!file.size?'文件为空':file.size>MAX_BYTES?'单个文件最大10MB':'请使用PDF、DOCX、TXT或MD'};}));
  }
  function update(key,patch){setItems(current=>current.map(item=>item.key===key?{...item,...patch}:item));}
  async function upload(){
    if(uploading.current||!pending.length)return;
    uploading.current=true;setBusy(true);let added=0;
    try{
      for(const item of pending){
        update(item.key,{status:'解析中',message:'正在读取原文、解析并建立检索索引…'});
        try{
          const content=await fileContent(item.file);
          const result=await api('/knowledge/upload',{filename:item.file.name,title:item.title.trim(),topic,language,content});
          update(item.key,{status:result.duplicate?'已存在':'已入库',paper:result.paper,message:result.duplicate?`已在知识库中：${result.paper.id}`:`${result.paper.pages}${result.paper.source_unit} · ${result.paper.chunks}个片段 · 可立即检索`});
          if(!result.duplicate)added++;
        }catch(error){update(item.key,{status:'失败',message:error.message});}
      }
      await onRefresh();
      notify(added?`已新增${added}份知识资料，可以开始检索`:'本批处理完成，请查看每个文件的结果');
    }catch(error){notify(`文件已处理，列表刷新失败：${error.message}`,true);}
    finally{uploading.current=false;setBusy(false);}
  }
  return <>
    <div className="page-heading"><div><h1>知识管理</h1><p>把自己的文档加入研究空间，问答时可回查原文</p></div><span className="knowledge-total">已上传 <b>{uploaded.length}</b> 份</span></div>
    <section className="surface knowledge-upload">
      <div className="section-top"><div><h2>上传知识文档</h2><span className="muted">保存在本机，成功入库后自动参与全文检索</span></div><Icon name="folder" size={21}/></div>
      <div className="upload-body">
        <label className={'upload-drop '+(dragging?'dragging':'')+(busy?' disabled':'')} onDragOver={event=>{event.preventDefault();if(!busy)setDragging(true);}} onDragLeave={()=>setDragging(false)} onDrop={event=>{event.preventDefault();setDragging(false);choose(event.dataTransfer.files);}}>
          <input ref={input} type="file" aria-label="选择知识文件" accept={ACCEPT} multiple disabled={busy} onChange={event=>{choose(event.target.files);event.target.value='';}}/>
          <span className="upload-symbol"><Icon name="plus" size={25}/></span><strong>点击选择文件，或拖到这里</strong><span>PDF、Word（DOCX）、TXT、Markdown</span><small>单个最大10MB · 每批最多20份 · 扫描PDF需先进行文字识别</small>
        </label>
        <div className="upload-options"><label>研究主题<select aria-label="上传资料主题" disabled={busy} value={topic} onChange={event=>setTopic(event.target.value)}>{data.topics.map(t=><option key={t}>{t}</option>)}</select></label><label>资料语种<select aria-label="上传资料语种" disabled={busy} value={language} onChange={event=>setLanguage(event.target.value)}>{['自动识别','中文','英文'].map(l=><option key={l}>{l}</option>)}</select></label><p>PDF按原始页序定位；Word与文本按内容分段，保留原文件供核对。</p></div>
        {items.length>0&&<div className="upload-queue" aria-live="polite">{items.map(item=><div className="upload-item" key={item.key}><Icon name="book" size={20}/><div className="upload-file"><div><strong>{item.file.name}</strong><small>{fileSize(item.file.size)}</small></div>{['待上传','失败'].includes(item.status)&&<input aria-label={`资料标题：${item.file.name}`} disabled={busy} value={item.title} maxLength={200} onChange={event=>update(item.key,{title:event.target.value})}/>}<p className={item.status==='失败'||item.status==='格式或大小不符'?'upload-error':''}>{item.message||'可修改资料标题后上传'}</p></div><span className={'upload-state '+(item.status==='已入库'||item.status==='已存在'?'done':'')}>{item.status==='解析中'&&<span className="spinner"/>}{item.status}</span></div>)}</div>}
        <div className="upload-footer"><span>上传过程在本机完成；模型归纳时会发送命中的证据片段。</span><div className="button-row">{items.length>0&&<button className="subtle" disabled={busy} onClick={()=>setItems([])}>清空本批</button>}<button className="primary" disabled={busy||!pending.length} onClick={upload}><Icon name={busy?'clock':'plus'} size={17}/>{busy?'正在解析入库…':`上传并加入检索${pending.length?`（${pending.length}）`:''}`}</button></div></div>
      </div>
    </section>
    <section className="surface knowledge-list"><div className="section-top"><div><h2>已上传的知识</h2><span className="muted">原有{data.papers.length-uploaded.length}篇研究文献仍可在文献库中查看</span></div><button className="subtle" onClick={()=>onRefresh().catch(error=>notify(error.message,true))}>刷新</button></div>{uploaded.length?<div>{[...uploaded].reverse().map(p=><article className="knowledge-row" key={p.id}><span className="knowledge-format">{p.format}</span><div className="knowledge-identity"><button className="text-link" onClick={()=>onOpen(p.id)}>{p.display_title}</button><p>{p.id} · {p.pages}{p.source_unit} · {p.chunks}个片段 · {p.topic}</p><small>{p.filename} · {fileSize(p.bytes)} · {localTime(p.created)}</small></div><div className="knowledge-actions"><button className="subtle" onClick={()=>onOpen(p.id,1)}><Icon name="book" size={16}/>查看原文</button><button className="secondary small" onClick={()=>onResearch(`请整理这份资料的主要内容，并给出原文依据。`,[p.id])}><Icon name="spark" size={16}/>基于资料研究</button></div></article>)}</div>:<Empty title="还没有上传知识" text="加入项目文档、研究材料或工作笔记后，就能在研究助手中引用它们。"/>}</section>
  </>;
}

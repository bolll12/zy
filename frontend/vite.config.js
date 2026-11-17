import {defineConfig} from 'vite';
const backend='http://127.0.0.1:8878';
export default defineConfig({build:{outDir:'../web',emptyOutDir:true},server:{proxy:{
  '/api':{target:backend,changeOrigin:true,configure:proxy=>proxy.on('proxyReq',(request,incoming)=>{
    if(incoming.headers.origin===`http://${incoming.headers.host}`)request.setHeader('Origin',backend);
  })},
  '/papers':{target:backend,changeOrigin:true},
}}});

import crypto from "node:crypto";

export const sleep = (ms)=>new Promise(r=>setTimeout(r,ms));
export const hash = (s)=>crypto.createHash("sha256").update(String(s)).digest("hex").slice(0,16);
export const clean = (s)=>String(s||"").replace(/\s+/g," ").trim();
export const clamp = (n,min,max)=>{ n=Number(n); if(Number.isNaN(n)) return undefined; return Math.min(max,Math.max(min,n)); };
export function priceNumber(x){ return Number(String(x||"").replace(/[^0-9.]/g,""))||Infinity; }
export function withAffiliate(u){
  try{ const url=new URL(u); if(/amazon\./i.test(url.hostname)) url.searchParams.set("tag","kayce25-20"); return url.toString(); }
  catch{ return u; }
}
export function polish(text){
  let t=clean(text);
  t=t.replace(/\b(bestest|so much awesome)\b/gi,"excellent");
  t=t.replace(/\s{2,}/g," ");
  t=t.replace(/(^\w|\.\s+\w)/g,m=>m.toUpperCase());
  if(t.length>180) t=t.slice(0,177)+"…";
  return t;
}

import fs from "node:fs";
import path from "node:path";
import slugify from "slugify";
import { priceNumber } from "./util.mjs";

const HISTORY = path.join("data","topics_history.json");
const COOLDOWN_DAYS = 30;

function loadHistory(){ try{ return JSON.parse(fs.readFileSync(HISTORY,"utf8")); }catch{ return []; } }
function saveHistory(hist){ fs.mkdirSync("data",{recursive:true}); fs.writeFileSync(HISTORY, JSON.stringify(hist,null,2)); }
function daysAgo(n){ const d=new Date(); d.setDate(d.getDate()-n); return d; }
function cap(s){ return s.replace(/\b\w/g,m=>m.toUpperCase()); }

export function pickTopics(items, targetCount=15){
  const hist = loadHistory();
  const cutoff = daysAgo(COOLDOWN_DAYS);
  const blocked = new Set(hist.filter(h=>new Date(h.date)>cutoff).map(h=>h.slug));

  const cats = new Set(items.map(i=>(i.category||"").toLowerCase()).filter(Boolean));
  const brands = new Set(items.map(i=>(i.brand||"").toLowerCase()).filter(Boolean));
  const priceBands = [
    {label:"Under $25", test:(i)=>priceNumber(i.price)<=25},
    {label:"Under $50", test:(i)=>priceNumber(i.price)<=50},
    {label:"Under $100",test:(i)=>priceNumber(i.price)<=100},
  ];

  const candidates = [];
  for(const c of cats){
    candidates.push(`Top 20 ${cap(c)} Gifts`);
    candidates.push(`Best ${cap(c)} Gifts Right Now`);
    for(const p of priceBands) candidates.push(`Top 20 ${cap(c)} Gifts ${p.label}`);
  }
  for(const b of brands){
    candidates.push(`Top 20 Gifts from ${cap(b)}`);
    candidates.push(`${cap(b)} Gifts Under $50`);
  }
  candidates.push("Top 20 Weird but Useful Gifts");
  candidates.push("Top 20 Cozy Home Gifts");
  candidates.push("Top 20 Gifts for Coffee Lovers");
  candidates.push("Top 20 Gifts for Desk Setups");

  const seen = new Set(); const out=[];
  for(const t of candidates){
    const slug = slugify(t,{lower:true});
    if(seen.has(slug)) continue;
    if(blocked.has(slug)) continue;
    seen.add(slug);
    out.push({title:t, slug});
    if(out.length>=targetCount) break;
  }
  return {
    topics: out,
    commit: ()=>{
      const now = new Date().toISOString();
      const newHist = hist.concat(out.map(x=>({slug:x.slug,title:x.title,date:now})));
      saveHistory(newHist);
    }
  };
}

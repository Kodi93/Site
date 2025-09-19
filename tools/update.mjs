import fs from "node:fs";
import path from "node:path";
import { ebaySearch } from "./ebay.mjs";
import { amazonSearch } from "./amazon.mjs";
import { normalizeItem } from "./normalize.mjs";
import { hash } from "./util.mjs";

const OUT = path.join("data","items.json");
const SEEN = path.join("data","seen_items.json");
const COOLDOWN_DAYS = 30;

function loadSeen(){
  try{ return JSON.parse(fs.readFileSync(SEEN,"utf8")); }catch{ return {}; }
}
function saveSeen(obj){ fs.mkdirSync("data",{recursive:true}); fs.writeFileSync(SEEN, JSON.stringify(obj,null,2)); }
function tooRecent(iso, days){
  return iso && (Date.now() - new Date(iso).getTime()) < days*86400*1000;
}

async function run(){
  const queries = [
    "gift for him","gift for her","gaming accessories","home gadgets",
    "fandom collectibles","tech gifts under 50","desk gadgets","smart home gifts"
  ];

  let raw = [];
  for(const q of queries){
    const [eb, amz] = await Promise.allSettled([ebaySearch(q, 25), amazonSearch(q, 25)]);
    if(eb.status==="fulfilled") raw = raw.concat(eb.value);
    if(amz.status==="fulfilled") raw = raw.concat(amz.value);
  }

  let items = raw.map(normalizeItem);

  // Deduplicate by id
  const byId = new Map();
  for(const i of items){ if(i.id && !byId.has(i.id)) byId.set(i.id, i); }
  items = Array.from(byId.values());

  // 30-day repost lock
  const seen = loadSeen();
  items = items.filter(i => !tooRecent(seen[i.id]?.lastSeenISO, COOLDOWN_DAYS));

  if(items.length < 50){
    console.error("Inventory too small:", items.length);
    process.exit(1);
  }

  // Update seen timestamps
  const now = new Date().toISOString();
  for(const i of items){ seen[i.id] = { lastSeenISO: now }; }
  saveSeen(seen);

  fs.mkdirSync("data",{ recursive:true });
  fs.writeFileSync(OUT, JSON.stringify(items,null,2));
  console.info("Wrote", items.length, "items →", OUT);
}

run().catch(e=>{ console.error(e); process.exit(1); });

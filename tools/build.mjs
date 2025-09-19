import fs from "node:fs";
import path from "node:path";
import slugify from "slugify";
import { pickTopics } from "./topics.mjs";
import { priceNumber } from "./util.mjs";

const IN = path.join("data","items.json");
const PUB = "public";

function filterByTopic(title, items){
  const t = title.toLowerCase();
  const under = t.match(/under\s+\$(\d+)/i);
  let filtered = items;
  if(under){ const cap = Number(under[1]); filtered = filtered.filter(i=>priceNumber(i.price)<=cap); }
  // category or brand tokens
  const tokens = t.split(/\s+/);
  filtered = filtered.filter(i=>{
    const s = `${(i.category||"").toLowerCase()} ${(i.brand||"").toLowerCase()} ${i.title.toLowerCase()}`;
    return tokens.some(tok => tok.length>3 && s.includes(tok));
  });
  if(filtered.length<10) filtered = items.slice(0,20); // fallback
  return filtered.slice(0,20);
}

function renderGuide(title, items){
  const lis = items.map(i=>`
    <li>
      <a href="${i.url}" rel="sponsored nofollow noopener" target="_blank">
        <img src="${i.image}" alt="${i.title}" loading="lazy" />
        <h3>${i.title}</h3>
        ${i.price?`<p class="price">${i.price}</p>`:""}
        <p class="updated">Updated ${i.updatedAt.split("T")[0]}</p>
      </a>
    </li>`).join("");
  const ld = {
    "@context":"https://schema.org",
    "@type":"ItemList",
    "name": title,
    "itemListElement": items.map((i,idx)=>(
      {
        "@type":"ListItem","position":idx+1,"url": i.url,"name": i.title
      }
    ))
  };
  return `<!doctype html><html lang="en"><head>
    <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>${title} — GrabGifts</title>
    <link rel="canonical" href="https://grabgifts.net/guides/${slugify(title,{lower:true})}/" />
    <meta name="robots" content="index,follow">
    <script type="application/ld+json">${JSON.stringify(ld)}</script>
    </head><body>
      <header><h1>${title}</h1>
        <p>Affiliate disclosure: We may earn from qualifying purchases.</p>
      </header>
      <ol class="grid">${lis}</ol>
    </body></html>`;
}

function writeFile(p, html){ fs.mkdirSync(path.dirname(p),{recursive:true}); fs.writeFileSync(p, html); }

function main(){
  const items = JSON.parse(fs.readFileSync(IN,"utf8"));
  const plan = pickTopics(items, 15);

  let made = 0;
  for(const {title, slug} of plan.topics){
    const picks = filterByTopic(title, items);
    if(picks.length<10) continue;
    const html = renderGuide(title, picks);
    writeFile(path.join(PUB,"guides",slug,"index.html"), html);
    made++;
  }
  if(made<15){ console.error("Generated guides:", made); process.exit(1); }
  plan.commit();
  console.info("Generated guides:", made);
}

main();

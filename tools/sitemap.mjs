import fs from "node:fs";
import path from "node:path";

const base = "https://grabgifts.net";
function* walk(dir){
  for(const e of fs.readdirSync(dir,{withFileTypes:true})){
    const p = path.join(dir,e.name);
    if(e.isDirectory()) yield* walk(p);
    else if(e.isFile() && e.name==="index.html") yield "/"+path.relative("public",path.dirname(p))+"/";
  }
}
const urls = Array.from(walk("public"));
const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n`+
  urls.map(u=>`  <url><loc>${base}${u}</loc><lastmod>${new Date().toISOString()}</lastmod></url>`).join("\n")+
  "\n</urlset>\n";
fs.writeFileSync("public/sitemap.xml", xml);
console.info("Wrote sitemap with", urls.length, "urls");

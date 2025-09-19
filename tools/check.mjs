import fs from "node:fs";

const items = JSON.parse(fs.readFileSync("data/items.json","utf8"));
if(new Set(items.map(i=>i.id)).size !== items.length) throw new Error("Duplicate item IDs");
if(items.length < 50) throw new Error("Too few items");
if(!fs.existsSync("public/guides")) throw new Error("Guides missing");
console.info("QA OK");

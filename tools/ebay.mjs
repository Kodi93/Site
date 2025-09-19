import fetch from "node-fetch";

const EBAY_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token";

async function getToken(){
  const id = process.env.EBAY_CLIENT_ID;
  if(!id) throw new Error("EBAY_CLIENT_ID missing");
  const body = new URLSearchParams({
    grant_type:"client_credentials",
    scope: process.env.EBAY_SCOPE || "https://api.ebay.com/oauth/api_scope"
  });
  const r = await fetch(EBAY_TOKEN_URL,{
    method:"POST",
    headers:{
      "Content-Type":"application/x-www-form-urlencoded",
      "Authorization":"Basic "+Buffer.from(`${id}:`).toString("base64")
    },
    body
  });
  if(!r.ok) throw new Error("ebay token failed: "+r.status);
  const j = await r.json();
  return j.access_token;
}

export async function ebaySearch(q, limit=30){
  const token = await getToken();
  const url = `https://api.ebay.com/buy/browse/v1/item_summary/search?q=${encodeURIComponent(q)}&limit=${Math.min(limit,50)}`;
  const r = await fetch(url,{ headers:{ Authorization:`Bearer ${token}` }});
  if(!r.ok) throw new Error("ebay search failed: "+r.status);
  const j = await r.json();
  return (j.itemSummaries||[]).map(s=>(
    {
      source:"ebay",
      id:s.itemId,
      title:s.title,
      url:s.itemWebUrl,
      image:(s.image&&s.image.imageUrl)||undefined,
      price:(s.price&&s.price.value)||undefined,
      rating: undefined,
      brand: s.brand||undefined,
      category:(s.categoryPath&&s.categoryPath.split(">").pop())||undefined,
    }
  ));
}

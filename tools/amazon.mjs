export async function amazonSearch(/* q, limit=30 */){
  if(!process.env.AMZ_ACCESS_KEY || !process.env.AMZ_SECRET_KEY){
    console.warn("Amazon keys missing — skipping Amazon search");
    return [];
  }
  // TODO: implement PA-API v5 once keys exist. For now return [] to avoid failing builds.
  return [];
}

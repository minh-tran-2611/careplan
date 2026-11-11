"""Optional: creates vectors for reference documents, never patient data."""
import asyncio
import httpx
import sys
import json
import hashlib
import argparse
from dataclasses import replace
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.settings import get_settings
from agent.tools.retrieval import Retriever
from llm.embeddings.embed import EmbeddingClient

async def main(http_client, args):
    settings=get_settings()
    if args.corpus:settings=replace(settings,corpus_path=Path(args.corpus).resolve())
    if args.collection:settings=replace(settings,qdrant_collection=args.collection)
    if not settings.embedding_model:raise SystemExit("Set EMBEDDING_MODEL before building the index. Keyword retrieval already works without it.")
    retriever=Retriever(settings);client=EmbeddingClient(settings,http_client);records=list(retriever.records.values());rows=[]
    if settings.qdrant_url:retriever.vectors.http_client=http_client
    completed=set()
    if settings.qdrant_url:
        try:
            offset=None
            while True:
                body={"limit":128,"with_payload":True,"with_vector":False}
                if offset is not None:body['offset']=offset
                page=await retriever.vectors.request('POST','/points/scroll',body)
                for point in page['points']:
                    payload=point['payload'];record=retriever.records.get(payload.get('id'))
                    if record and payload.get('embedding_model')==settings.embedding_model and all(payload.get(k)==v for k,v in record.items()):completed.add(record['id'])
                offset=page.get('next_page_offset')
                if offset is None:break
        except Exception as exc:
            if 'HTTP 404' not in str(exc):raise
        records=[r for r in records if r['id'] not in completed]
        print(f"Resume: {len(completed)} verified existing, {len(records)} remaining",flush=True)
    cache_path=settings.root / "data/processed/embedding_cache.json"
    cache=json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    semaphore=asyncio.Semaphore(4)
    async def vector_for(record):
        text=record["chapter"]+"\n"+record.get("embeddingText",record["text"])
        key=hashlib.sha256((settings.embedding_model+"\n"+text).encode()).hexdigest()
        if key in cache: return cache[key]
        for attempt in range(5):
            try:
                async with semaphore:
                    vector=(await client.embed([text],"passage"))[0]
                cache[key]=vector
                return vector
            except Exception as exc:
                print(f"Embedding retry {attempt+1}: {record['id']} ({type(exc).__name__})",flush=True)
                if attempt==4: raise
                await asyncio.sleep(2**attempt)
    for i in range(0,len(records),16):
        batch=records[i:i+16];vectors=await asyncio.gather(*(vector_for(r) for r in batch))
        temporary=cache_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(cache),encoding="utf-8");temporary.replace(cache_path)
        if settings.qdrant_url:
            if i == 0:
                await retriever.vectors.ensure_collection(len(vectors[0]))
                for field in ("id", "embedding_model"):
                    await retriever.vectors.request("PUT", "/index?wait=true", {"field_name":field,"field_schema":"keyword"})
            for attempt in range(4):
                try:
                    await retriever.vectors.upsert(batch, vectors)
                    break
                except Exception as exc:
                    print(f"Qdrant retry {attempt+1}: offset {i} ({type(exc).__name__})",flush=True)
                    if attempt==3:raise
                    await asyncio.sleep(2**attempt)
        rows.extend({"id":r["id"],"vector":v} for r,v in zip(batch,vectors))
        print(f"Indexed {len(completed)+len(rows)}/{len(retriever.records)}", flush=True)
    if not settings.qdrant_url: retriever.vectors.save(rows)
async def run():
    parser=argparse.ArgumentParser()
    parser.add_argument('--corpus')
    parser.add_argument('--collection')
    args=parser.parse_args()
    async with httpx.AsyncClient(timeout=25,limits=httpx.Limits(max_connections=4,max_keepalive_connections=0)) as client:
        await main(client,args)
if __name__=="__main__":asyncio.run(run())

"""Read-only integrity and retrieval checks; never invokes the chat LLM."""
import asyncio
import json
import sys
import argparse
from dataclasses import replace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config.settings import get_settings
from agent.tools.retrieval import Retriever

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--corpus');parser.add_argument('--collection')
    args=parser.parse_args();cfg=get_settings()
    if args.corpus:cfg=replace(cfg,corpus_path=Path(args.corpus).resolve())
    if args.collection:cfg=replace(cfg,qdrant_collection=args.collection)
    retriever=Retriever(cfg)
    store=retriever.vectors
    info=await store.request("GET")
    found={};offset=None
    while True:
        body={"limit":256,"with_payload":True,"with_vector":False}
        if offset is not None:body["offset"]=offset
        page=await store.request("POST","/points/scroll",body)
        for point in page["points"]:
            payload=point["payload"]
            found[payload["id"]]=payload
        offset=page.get("next_page_offset")
        if offset is None:break
    assert set(found)==set(retriever.records),"Missing or unexpected source IDs"
    for key,record in retriever.records.items():
        assert all(found[key].get(field)==value for field,value in record.items()),"Payload mismatch"
        assert found[key]["embedding_model"]==retriever.settings.embedding_model
    sources,mode=await retriever.retrieve("COPD khó thở ho có đàm","chapter_01")
    assert mode=="hybrid" and sources,"Hybrid search unavailable"
    assert all(s.chapter==retriever.corpus["chapters"][0]["title"] for s in sources)
    report={"records_verified":len(found),"dimensions":info["config"]["params"]["vectors"]["size"],
            "retrieval_mode":mode,"returned_sources":len(sources),"chapter_filter_verified":True,
            "source_pages":[s.page for s in sources]}
    if 'sourceBlocks' in retriever.corpus['stats']:
        assert {r['page'] for r in found.values()}==set(range(1,374))
        continuation,continuation_mode=await retriever.retrieve('Hút thông đường thở xác định nhu cầu hút chất tiết qua miệng khí quản','chapter_01')
        assert continuation_mode=='hybrid' and any(s.page==23 for s in continuation),'Continuation-page retrieval failed'
        report.update(pages_covered=373,tables_included=retriever.corpus['stats']['tablesIncluded'],
                      continuation_query_verified=True,continuation_pages=[s.page for s in continuation])
    output=retriever.settings.root/"logs/qdrant_verification.json"
    output.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report))

if __name__=="__main__":asyncio.run(main())

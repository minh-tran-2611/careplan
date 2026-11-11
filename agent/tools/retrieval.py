import json
import logging
import math
import re
import unicodedata
from collections import Counter
from api.models import Source
from llm.embeddings.embed import EmbeddingClient
from llm.providers.openai import ProviderError
from memory.vector_store.vector_db import VectorStore
from memory.vector_store.qdrant_store import QdrantStore

STOP={"va","la","cua","cho","nguoi","benh","ke","hoach","dieu","duong","cham","soc","toi","giup","lap","co","cac","nhung","mot","tai","trong","voi","duoc","can"}
def normalize(s:str)->str:
    return "".join(c for c in unicodedata.normalize("NFD",s or "") if unicodedata.category(c)!="Mn").replace("đ","d").replace("Đ","D").lower()
def tokens(s:str):return [w for w in re.findall(r"[a-z0-9]+",normalize(s)) if len(w)>1 and w not in STOP]

class Retriever:
    def __init__(self,settings):
        self.settings=settings
        self.corpus=json.loads(settings.corpus_path.read_text(encoding="utf-8"))
        self.records={r["id"]:r for r in self.corpus["records"]}
        if len(self.records)!=len(self.corpus["records"]):raise ValueError("Duplicate corpus IDs")
        self.vectors=QdrantStore(settings) if settings.qdrant_url else VectorStore(settings.vector_index_path)
        self.bags={i:Counter(tokens(r.get("embeddingText",r["text"])+" "+r["chapter"])) for i,r in self.records.items()}
        self.df=Counter(w for bag in self.bags.values() for w in bag)
        self.average_length=sum(sum(b.values()) for b in self.bags.values())/max(len(self.bags),1)

    def keyword(self,query:str,chapter_id:str="",limit:int=12):
        chapter=next((c for c in self.corpus["chapters"] if c["id"]==chapter_id),None)
        if chapter_id and not chapter:return []
        query=normalize(query).replace("copd","copd phoi tac nghen man tinh").replace("stroke","dot quy").replace("pci","can thiep dong mach vanh")
        terms=set(tokens(query));rank=[];n=len(self.records)
        for key,r in self.records.items():
            if chapter and r["chapter"]!=chapter["title"]:continue
            score=0.0;bag=self.bags[key];length=sum(bag.values())
            for term in terms:
                tf=bag.get(term,0)
                if not tf:continue
                idf=math.log(1+(n-self.df[term]+0.5)/(self.df[term]+0.5))
                score+=idf*tf*2.2/(tf+1.2*(0.25+0.75*length/self.average_length))
                if term in tokens(r.get("diagnosis","")):score+=1.5
            if chapter and r["type"]=="care_plan_row":score+=0.2
            if score>0:rank.append((key,score))
        return sorted(rank,key=lambda x:(-x[1],self.records[x[0]]["page"]))[:limit]

    def search(self,query:str,chapter:str="",limit:int=12):
        sources=[];seen_pages=set()
        for key,_ in self.keyword(query,chapter,limit*4):
            record=self.records[key]
            if record.get('type')=='page_content' and record['page'] in seen_pages:continue
            sources.append(Source.model_validate(record));seen_pages.add(record['page'])
            if len(sources)>=limit:break
        return sources

    async def retrieve(self,query:str,chapter:str=""):
        rank=self.keyword(query,chapter,self.settings.top_k*3);mode="keyword"
        if self.settings.embedding_model and (self.settings.qdrant_url or self.vectors.rows):
            allowed=set(self.records)
            if chapter:
                ch=next((c for c in self.corpus["chapters"] if c["id"]==chapter),None)
                allowed={i for i,r in self.records.items() if ch and r["chapter"]==ch["title"]}
            try:
                vector=(await EmbeddingClient(self.settings).embed([query],"query"))[0]
                semantic=await self.vectors.search(vector,allowed,self.settings.top_k*3) if self.settings.qdrant_url else self.vectors.search(vector,allowed,self.settings.top_k*3)
                if not semantic: raise ValueError("Empty semantic index")
                scores=Counter()
                for ranked in (rank,semantic):
                    for position,(key,_) in enumerate(ranked,1):scores[key]+=1/(60+position)
                rank=scores.most_common();mode="hybrid"
            except (ProviderError,ValueError,OSError) as exc:
                logging.getLogger("nursing").warning("retrieval.vector_fallback", extra={"exception_type":type(exc).__name__})
                mode="keyword_fallback"
        result=[];length=0;seen_pages=set()
        for key,_ in rank:
            r=self.records[key]
            if r.get('type')=='page_content' and r['page'] in seen_pages:continue
            if length+len(r["text"])>self.settings.max_context_characters:continue
            result.append(Source.model_validate(r));length+=len(r["text"])
            seen_pages.add(r['page'])
            if len(result)>=self.settings.top_k:break
        return result,mode

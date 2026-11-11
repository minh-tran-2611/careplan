"""Loss-preserving page chunks from the authoritative OCR JSONL, without clinical inference."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config.settings import ROOT

SOURCE=ROOT.parent/'NANDA_NIC_NOC_RAG'
OUTPUT=ROOT/'data/processed/corpus_full_v2.json'
EXCLUDE={'PageHeader','PageFooter'}

def build(source=SOURCE, output=OUTPUT):
    pages=[json.loads(line) for line in (source/'pages.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    blocks=[json.loads(line) for line in (source/'blocks.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    old=json.loads((ROOT/'data/processed/corpus.json').read_text(encoding='utf-8'))
    chapters=old['chapters']
    by_page={p['reader_page']:[] for p in pages}
    assert len(by_page)==373 and set(by_page)==set(range(1,374))
    assert len({b['id'] for b in blocks})==len(blocks)
    for block in blocks:by_page[block['reader_page']].append(block)
    records=[];included=[];excluded=[];previous_tables=[];previous_chapter=None
    for page in pages:
        number=page['reader_page']
        chapter=next((c['title'] for c in reversed(chapters) if c['page']<=number),'Phần đầu sách và hướng dẫn chung')
        if chapter!=previous_chapter:previous_tables=[]
        selected=[b for b in by_page[number] if b['block_type'] not in EXCLUDE]
        excluded.extend(b['id'] for b in by_page[number] if b['block_type'] in EXCLUDE)
        pieces=[];flags=set();tables=[]
        for block in selected:
            included.append(block['id']);flags.update(block.get('review_flags',[]))
            if block['block_type']=='Table':
                # HTML retains columns, empty cells, rowspan/colspan and superscripts exactly.
                body=block['html'];tables.append(block)
            else:body=block['text']
            if not body.strip():
                body='[Khối hình ảnh không có văn bản OCR; cần đối chiếu ảnh trang gốc.]'
                flags.add('image_requires_visual_review')
            pieces.append(f"[Nguồn {block['id']} · {block['block_type']}]\n{body}")
        context=[]
        if tables and previous_tables and any('empty_table_cells_check_previous_page' in b.get('review_flags',[]) for b in tables):
            # A separate quoted source, not a fabricated fill or automatic clinical merge.
            prior=previous_tables[-1]
            context=[{'block_id':prior['id'],'page':prior['reader_page']}]
            pieces.insert(0,f"[Ngữ cảnh bảng trước, trang {prior['reader_page']}, nguồn {prior['id']}. Ô trống ở trang hiện tại CHƯA được xác nhận là kế thừa; không tự ghép chẩn đoán/mục tiêu.]\n{prior['html']}")
            flags.add('continuation_context_requires_review')
        if pieces:
            record={'id':f'nanda2024_full_v2_p{number:03d}','page':number,'chapter':chapter,
                'type':'page_content','text':'\n\n'.join(pieces),'reviewFlags':sorted(flags),
                'blockIds':[b['id'] for b in selected], 'contextSources':context,
                'sourceImage':page['source_image'],'sourceFile':page['source_file'],
                'originalText':page['text'],'originalHtml':page['html']}
            # Hosted endpoint rejects some longer passages despite its advertised limit.
            # Index bounded plain-text windows, but retrieve the complete page/table evidence.
            plain='\n\n'.join(b['text'] or '[Ảnh cần đối chiếu trang gốc]' for b in selected)
            start=0;part=0
            while start<len(plain):
                end=min(start+1400,len(plain))
                if end<len(plain):
                    boundary=plain.rfind('\n',start+700,end)
                    if boundary>start:end=boundary+1
                records.append({**record,'id':record['id']+f'_c{part:02d}',
                                'embeddingText':plain[start:end],'chunkStart':start,'chunkEnd':end})
                start=end;part+=1
        if tables:previous_tables=tables
        previous_chapter=chapter
    assert len(included)+len(excluded)==len(blocks)
    assert set(included).isdisjoint(excluded)
    corpus={'title':old['title'],'source':str(source),'chapters':chapters,'records':records,
        'stats':{'pages':len(pages),'chapters':len(chapters),'records':len(records),'sourceBlocks':len(blocks),
                 'includedBlocks':len(included),'excludedHeaderFooterBlocks':len(excluded),
                 'tablesIncluded':sum(b['block_type']=='Table' for b in blocks),
                 'excludedContinuationTables':0,'imagesTranscribed':False},
        'provenance':{'sourceDirectory':str(source),'sourceHashes':{n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in ['pages.jsonl','blocks.jsonl']},
                      'includedBlockIds':included,'excludedHeaderFooterBlockIds':excluded,
                      'policy':'Page chunks retain original tables and footnotes. Prior table context is quoted, never clinically merged. Image-only content still needs visual review.'}}
    output.write_text(json.dumps(corpus,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(corpus['stats']))
    print('max_chunk_characters',max(len(r['text']) for r in records))
    return corpus

if __name__=='__main__':build()

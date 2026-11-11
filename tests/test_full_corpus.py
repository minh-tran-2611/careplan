import json
import unittest
from dataclasses import replace
from config.settings import get_settings
from agent.tools.retrieval import Retriever
from api.models import Source

class FullCorpusTests(unittest.TestCase):
    def setUp(self):
        cfg=get_settings()
        self.cfg=replace(cfg,corpus_path=cfg.root/'data/processed/corpus_full_v2.json',qdrant_url='',embedding_model='')
        self.corpus=json.loads(self.cfg.corpus_path.read_text(encoding='utf-8'))

    def test_all_pages_and_block_accounting(self):
        c=self.corpus
        self.assertEqual({r['page'] for r in c['records']},set(range(1,374)))
        included=c['provenance']['includedBlockIds'];excluded=c['provenance']['excludedHeaderFooterBlockIds']
        self.assertEqual(len(included),1237)
        self.assertEqual(len(excluded),758)
        self.assertEqual(len(set(included+excluded)),1995)
        self.assertEqual(c['stats']['tablesIncluded'],354)
        self.assertEqual(c['stats']['excludedContinuationTables'],0)

    def test_table_structure_and_original_page_are_preserved(self):
        r=next(r for r in self.corpus['records'] if r['page']==22)
        self.assertIn('rowspan="2"',r['text'])
        self.assertIn('<table>',r['originalHtml'])
        self.assertIn('p022_b002',r['blockIds'])
        self.assertEqual(Source.model_validate(r).sourceImage,'page_022.webp')

    def test_continuation_is_explicit_context_not_filled_cells(self):
        r=next(r for r in self.corpus['records'] if r['page']==23)
        self.assertIn('<td></td><td></td>',r['text'])
        self.assertEqual(r['contextSources'][0]['page'],22)
        self.assertIn('CHƯA được xác nhận',r['text'])
        self.assertIn('continuation_context_requires_review',r['reviewFlags'])

    def test_every_record_is_compatible_with_retrieval(self):
        retriever=Retriever(self.cfg)
        for r in retriever.records.values():Source.model_validate(r)
        sources=retriever.search('Hút thông đường thở','chapter_01')
        self.assertTrue(sources)
        self.assertTrue(any(s.page==23 for s in sources))

    def test_embedding_windows_cover_each_page_without_truncation(self):
        for page in range(1,374):
            chunks=sorted((r for r in self.corpus['records'] if r['page']==page),key=lambda r:r['chunkStart'])
            cursor=0
            for chunk in chunks:
                self.assertEqual(chunk['chunkStart'],cursor)
                self.assertEqual(chunk['chunkEnd']-cursor,len(chunk['embeddingText']))
                self.assertLessEqual(len(chunk['embeddingText']),1400)
                cursor=chunk['chunkEnd']
            self.assertGreater(cursor,0)

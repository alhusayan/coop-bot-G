"""Synthetic provider fixtures; every HTTP call is mocked. No paid requests."""
import asyncio
import copy
import importlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
import requests
import findzia_social as social


class SocialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = int(time.time())
        self.source = social.source_config(dict(username='testshop', merchant='Test Shop', countries=['kw'], enabled=True))
        path = Path(self.tmp.name)
        self.sources = path/'sources.json'
        self.sources.write_text(json.dumps({'sources':[self.source]}))
        self.env = dict(FINDZIA_SOCIAL_ENABLED='true', FINDZIA_SOCIAL_WORKER_ENABLED='false',
                       FINDZIA_SOCIAL_DB=str(path/'social.db'), FINDZIA_SOCIAL_SOURCES=str(self.sources),
                       PUBLIC_BASE_URL='https://api.findzia.com', APIFY_API_TOKEN='fake', GEMINI_API_KEY='fake',
                       FINDZIA_SOCIAL_ADMIN_TOKEN='test-admin')
        self.cfg = social.Config(self.env)
        self.store = social.Store(self.cfg)
        self.store.sync_sources([self.source])
        self.raw = dict(id='100', ownerUsername='testshop', type='Image',
                        url='https://www.instagram.com/p/Test100/', timestamp=social.iso(self.now-60),
                        displayUrl='https://scontent.cdninstagram.com/photo.jpg?sig=one',
                        caption='Apple iPhone 16 256GB Black 249.900 KWD')
        self.extraction = dict(media_text=[self.raw['caption']], offers=[dict(
            title='Apple iPhone 16 256GB Black', brand='Apple', model='iPhone 16', variant='256GB Black',
            titles={'ar':'ابل آيفون 16 256GB اسود', 'en':'Apple iPhone 16 256GB Black'},
            aliases=['ايفون 16', 'iphone 16', 'smartphone'], price_text='249.900', currency='KWD',
            price_quote='249.900 KWD', identity_quote='Apple iPhone 16 256GB Black',
            evidence='caption', media_index=0, countries=['kw'], valid_from='', valid_until='',
            conditional=False, price_kind='full', confidence=.98)])

    def post(self):
        self.store.accept_post(self.raw, self.source, self.now)
        with self.store.db() as db:
            return dict(db.execute('SELECT * FROM posts WHERE source=?', ('testshop',)).fetchone())

    def offers(self, extraction=None, source=None):
        post = self.post()
        return social.normalize_offers(extraction or self.extraction, post, source or self.source,
                                       ['a'*64], self.cfg.base, self.now)

    def seed(self):
        post = self.post()
        self.store.save_offers(post, self.offers(), self.now)
        return self.store.search('iphone 16', {'country':'kw'})[0]

    def test_seven_markets(self):
        self.assertEqual(set(social.MARKETS), {'sa','gb','es','it','fr','ae','kw'})

    def test_each_market_can_ingest_its_currency_and_native_alias(self):
        self.store.sync_sources([dict(self.source,username='shop_'+cc,countries=[cc]) for cc in social.MARKETS])
        for cc, meta in social.MARKETS.items():
            src=dict(self.source,username='shop_'+cc,countries=[cc])
            currency=meta['currency']
            raw=dict(self.raw,ownerUsername=src['username'],url='https://www.instagram.com/p/Post_'+cc+'/',
                     caption='Apple iPhone 16 256GB Black 249.90 '+currency)
            self.store.accept_post(raw,src,self.now)
            with self.store.db() as db:post=dict(db.execute('SELECT * FROM posts WHERE source=?',(src['username'],)).fetchone())
            data=copy.deepcopy(self.extraction)
            data['offers'][0].update(price_text='249.90',price_quote='249.90 '+currency,currency=currency,countries=[cc])
            offers=social.normalize_offers(data,post,src,['a'*64],self.cfg.base,self.now)
            self.assertEqual(len(offers),1,cc)
            self.store.save_offers(post,offers,self.now)
            rows=self.store.search('ايفون 16',{'country':cc})
            self.assertEqual(len(rows),1,cc)
            self.assertEqual(rows[0]['currency'],currency)

    def test_prices_decimal_and_thousands(self):
        for value, currency, expected in [('٢٤٩٫٩٠٠','KWD','249.900'), ('1.299,99','EUR','1299.99'),
                                          ('1,299.99','GBP','1299.99'), ('1 299,99','EUR','1299.99'),
                                          ('1,299','SAR','1299'), ('1.299','EUR','1299')]:
            self.assertEqual(social.number(value,currency), social.Decimal(expected))
        for value in ('-20','nan','1e8','2x','0'):
            self.assertIsNone(social.number(value,'KWD'))

    def test_unconditional_grounded_price(self):
        offers = self.offers()
        self.assertEqual(len(offers),1)
        self.assertEqual(offers[0]['price'],'249.900 KWD')
        self.assertEqual(offers[0]['expires_at'],self.now-60+48*3600)

    def test_missing_wrong_or_fabricated_price_rejected(self):
        for update in ({'price_quote':'300 KWD'}, {'price_text':'199'}, {'currency':'SAR'},
                       {'price_quote':''}, {'confidence':.6}, {'conditional':True},
                       {'price_kind':'installment'}, {'identity_quote':'Samsung Galaxy S25'}):
            with self.subTest(update=update):
                data=copy.deepcopy(self.extraction);data['offers'][0].update(update)
                self.assertEqual(self.offers(data),[])

    def test_discount_and_monthly_payment_rejected(self):
        for quote in ('Save 249.900 KWD','249.900 KWD monthly','خصم 249.900 KWD','249.900 KWD قسط'):
            self.raw['caption']=quote+' Apple iPhone 16 256GB Black'
            data=copy.deepcopy(self.extraction);data['offers'][0]['price_quote']=quote
            self.assertEqual(self.offers(data),[])

    def test_expired_and_invalid_dates_rejected(self):
        for end in (social.iso(self.now-10),'not-a-date'):
            data=copy.deepcopy(self.extraction);data['offers'][0]['valid_until']=end
            self.assertEqual(self.offers(data),[])

    def test_future_offer_is_not_searchable(self):
        data=copy.deepcopy(self.extraction)
        data['offers'][0].update(valid_from=social.iso(self.now+100),valid_until=social.iso(self.now+10000))
        self.store.save_offers(self.post(),self.offers(data),self.now)
        self.assertEqual(self.store.search('iphone',{'country':'kw'}),[])

    def test_carousel_each_price_and_image_stays_separate(self):
        post=self.post()
        data=copy.deepcopy(self.extraction)
        extra=copy.deepcopy(data['offers'][0])
        extra.update(title='Apple iPhone 17 512GB',model='iPhone 17',variant='512GB',
                     price_text='399.000',price_quote='399.000 KWD',identity_quote='Apple iPhone 17 512GB',
                     media_index=1,evidence='image',titles={'en':'Apple iPhone 17 512GB'})
        data['offers'].append(extra);data['media_text'].append('Apple iPhone 17 512GB 399.000 KWD')
        offers=social.normalize_offers(data,post,self.source,['a'*64,'b'*64],self.cfg.base,self.now)
        self.assertEqual(len(offers),2)
        self.store.save_offers(post,offers,self.now)
        rows=self.store.search('iphone',{'country':'kw'})
        self.assertEqual(len(rows),2)
        self.assertEqual(len({r['url'] for r in rows}),2)
        self.assertTrue(next(r for r in rows if '17' in r['raw_title'])['image'].endswith('b'*64+'.jpg'))

    def test_out_of_range_media_does_not_borrow_photo(self):
        data=copy.deepcopy(self.extraction);data['offers'][0]['media_index']=6
        self.assertEqual(self.offers(data),[])

    def test_country_and_currency_filter(self):
        self.seed()
        self.assertEqual(self.store.search('iphone',{'country':'sa'}),[])
        self.assertEqual(self.store.search('iphone',{'country':'fr'}),[])
        self.assertEqual(len(self.store.search('iphone',{'country':'sa','global_countries':['kw']})),1)

    def test_multicountry_account_requires_explicit_market(self):
        src=dict(self.source,countries=['es','fr'])
        data=copy.deepcopy(self.extraction);data['offers'][0].update(countries=[],currency='EUR',price_quote='249.90 EUR',price_text='249.90')
        self.raw['caption']='Apple iPhone 16 256GB Black 249.90 EUR'
        self.assertEqual(self.offers(data,src),[])

    def test_cross_language_search_and_model_number(self):
        self.seed()
        self.assertEqual(len(self.store.search('عروض آيفون ١٦',{'country':'kw'},'ar')),1)
        self.assertEqual(self.store.search('iphone 17',{'country':'kw'}),[])
        self.assertEqual(self.store.search('iphone 512GB',{'country':'kw'}),[])
        self.assertEqual(self.store.search('Samsung',{'country':'kw'}),[])

    def test_fts_metacharacters_are_not_query_operators(self):
        self.seed()
        self.assertEqual(self.store.search('iphone OR nonexistent',{'country':'kw'}),[])
        self.assertEqual(self.store.search('" OR *',{'country':'kw'}),[])

    def test_repeated_post_does_not_reprocess_or_extend_expiry(self):
        self.seed()
        before=self.store.search('iphone',{'country':'kw'})[0]['expires_at']
        self.raw['displayUrl']=self.raw['displayUrl'].replace('one','two')
        self.assertFalse(self.store.accept_post(self.raw,self.source,self.now+100))
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT state FROM posts').fetchone()[0],'ready')
        self.assertEqual(self.store.search('iphone',{'country':'kw'})[0]['expires_at'],before)

    def test_edited_post_hides_old_price_until_reprocessed(self):
        self.seed();self.raw['caption']=self.raw['caption'].replace('249.900','299.900')
        self.assertTrue(self.store.accept_post(self.raw,self.source,self.now+100))
        self.assertEqual(self.store.search('iphone',{'country':'kw'}),[])

    def test_newest_reposted_product_wins_without_mixing_prices(self):
        self.seed()
        self.raw.update(url='https://www.instagram.com/p/Test101/', timestamp=social.iso(self.now-5),
                        caption='Apple iPhone 16 256GB Black 299.900 KWD')
        data=copy.deepcopy(self.extraction);data['offers'][0].update(price_text='299.900',price_quote='299.900 KWD')
        self.store.accept_post(self.raw,self.source,self.now)
        with self.store.db() as db:post=dict(db.execute('SELECT * FROM posts ORDER BY published DESC LIMIT 1').fetchone())
        offers=social.normalize_offers(data,post,self.source,['b'*64],self.cfg.base,self.now)
        self.store.save_offers(post,offers,self.now)
        rows=self.store.search('iphone',{'country':'kw'})
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['price'],'299.900 KWD')
        self.assertIn('/Test101/',rows[0]['url'])

    def test_wrong_owner_private_url_and_future_timestamp_rejected(self):
        for update in ({'ownerUsername':'someoneelse'},{'url':'https://instagram.com.evil/p/X/'},
                       {'url':'http://127.0.0.1/p/X/'},{'timestamp':social.iso(self.now+600)}):
            raw=dict(self.raw,**update)
            self.assertFalse(self.store.accept_post(raw,self.source,self.now))

    def test_media_allowlist_rejects_redirect_and_credentials(self):
        for url in ('http://scontent.cdninstagram.com/a.jpg','https://cdninstagram.com.evil/a.jpg',
                    'https://user@cdninstagram.com/a.jpg','https://127.0.0.1/a.jpg'):
            self.assertFalse(social.media_url(url))

    def test_removed_source_and_stale_post_disappear(self):
        self.seed()
        self.assertEqual(self.store.search('iphone',{'country':'kw'},now=self.now+37*3600),[])
        self.store.sync_sources([])
        self.assertEqual(self.store.search('iphone',{'country':'kw'}),[])

    def test_signature_rejects_modified_price_and_country(self):
        row=self.seed();self.assertTrue(self.store.valid(row))
        for change in ({'price':'1 KWD'},{'country':'sa'},{'url':'https://evil.invalid/'}):
            self.assertFalse(self.store.valid(dict(row,**change)))

    def test_budget_atomic_across_threads(self):
        self.cfg.daily=.1
        outcomes=[]
        threads=[threading.Thread(target=lambda i=i:outcomes.append(self.store.reserve(str(i),'apify',.1,self.now))) for i in range(8)]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        self.assertEqual(sum(outcomes),1)
        self.assertFalse(self.store.reserve('extra','apify',.1,self.now))

    def test_monthly_budget_and_ai_budget_independent(self):
        self.cfg.monthly=.1;self.cfg.ai_daily=1
        self.assertTrue(self.store.reserve('a','apify',.1,self.now))
        self.assertFalse(self.store.reserve('b','apify',.1,self.now+86400))
        self.assertTrue(self.store.reserve('c','ai',1,self.now))
        self.assertFalse(self.store.reserve('d','ai',1,self.now))

    def test_leader_lease_survives_restart(self):
        self.assertTrue(self.store.acquire('one',self.now))
        second=social.Store(self.cfg)
        self.assertFalse(second.acquire('two',self.now+1))
        self.assertTrue(second.acquire('two',self.now+301))

    def test_launch_is_incremental_basic_and_capped(self):
        worker=social.Worker(self.cfg,self.store)
        with self.store.db() as db:src=db.execute('SELECT * FROM sources').fetchone()
        with patch.object(worker,'api',return_value={'data':{'id':'run123'}}) as api:
            worker.launch(src,self.now)
            worker.launch(src,self.now)
        self.assertEqual(api.call_count,1)
        kw=api.call_args.kwargs
        self.assertEqual(kw['json']['dataDetailLevel'],'basicData')
        self.assertEqual(kw['json']['username'],['testshop'])
        self.assertIn('onlyPostsNewerThan',kw['json'])
        self.assertEqual(kw['params']['maxTotalChargeUsd'],.1)

    def test_ambiguous_launch_never_retries_paid_post(self):
        worker=social.Worker(self.cfg,self.store)
        with self.store.db() as db:src=db.execute('SELECT * FROM sources').fetchone()
        with patch.object(worker,'api',side_effect=requests.Timeout) as api:
            worker.launch(src,self.now)
            worker.launch(src,self.now+4000)
        self.assertEqual(api.call_count,1)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT state FROM jobs').fetchone()[0],'uncertain')
            self.assertEqual(db.execute('SELECT amount FROM usage').fetchone()[0],.1)

    def test_completed_run_ingests_and_settles_actual_cost(self):
        worker=social.Worker(self.cfg,self.store)
        with self.store.db() as db:src=db.execute('SELECT * FROM sources').fetchone()
        with patch.object(worker,'api',return_value={'data':{'id':'run123'}}):worker.launch(src,self.now)
        with self.store.db() as db:job=db.execute('SELECT * FROM jobs').fetchone()
        replies=[{'data':{'status':'SUCCEEDED','defaultDatasetId':'dataset1','usageTotalUsd':.003}},[self.raw]]
        with patch.object(worker,'api',side_effect=replies):worker.poll(job,self.now+30)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM posts').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT amount FROM usage').fetchone()[0],.003)
            self.assertEqual(db.execute('SELECT cursor FROM sources').fetchone()[0],self.now)

    def test_hourly_new_posts_do_not_postpone_daily_offer_refresh(self):
        worker=social.Worker(self.cfg,self.store)
        due=self.now+1000
        with self.store.db() as db:
            db.execute('UPDATE sources SET next_refresh=?',(due,))
            src=db.execute('SELECT * FROM sources').fetchone()
        with patch.object(worker,'api',return_value={'data':{'id':'run123'}}):worker.launch(src,self.now)
        with self.store.db() as db:job=db.execute('SELECT * FROM jobs').fetchone()
        replies=[{'data':{'status':'SUCCEEDED','defaultDatasetId':'dataset1','usageTotalUsd':.003}},[]]
        with patch.object(worker,'api',side_effect=replies):worker.poll(job,self.now+30)
        with self.store.db() as db:self.assertEqual(db.execute('SELECT next_refresh FROM sources').fetchone()[0],due)

    def test_read_error_keeps_same_run_and_cursor(self):
        worker=social.Worker(self.cfg,self.store)
        with self.store.db() as db:src=db.execute('SELECT * FROM sources').fetchone()
        with patch.object(worker,'api',return_value={'data':{'id':'run123'}}):worker.launch(src,self.now)
        with patch.object(worker,'api',side_effect=requests.Timeout) as api:worker.tick(self.now+30)
        self.assertEqual(api.call_count,1)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT cursor FROM sources').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT state FROM jobs').fetchone()[0],'running')

    def test_full_extraction_request_uses_images_and_no_search_tools(self):
        post=self.post()
        worker=social.Worker(self.cfg,self.store)
        response=Mock(status_code=200)
        response.json.return_value={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(self.extraction)}]}}]}
        worker.http.post=Mock(return_value=response)
        image=io.BytesIO();Image.new('RGB',(128,128),'blue').save(image,'JPEG')
        with patch.object(worker,'download_image',return_value=image.getvalue()):
            worker.extract(post,self.source,self.now)
        payload=worker.http.post.call_args.kwargs['json']
        self.assertNotIn('tools',payload)
        self.assertEqual(payload['generationConfig']['responseMimeType'],'application/json')
        self.assertIn('inlineData',payload['contents'][0]['parts'][1])
        self.assertEqual(len(self.store.search('iphone',{'country':'kw'})),1)

    def test_reprocessing_identical_extraction_is_not_billed_again(self):
        post=self.post();worker=social.Worker(self.cfg,self.store)
        ident='ai:'+post['key']+':'+post['digest']+':0'
        self.store.reserve(ident,'ai',1,self.now)
        with patch.object(worker,'download_image',side_effect=AssertionError('duplicate image processing')):
            worker.extract(post,self.source,self.now)

    def test_disabled_no_database_or_network(self):
        with patch.object(requests.sessions.Session,'request',side_effect=AssertionError('HTTP')):
            service=social.Service(social.Config({}))
            service.start()
            self.assertIsNone(service.store)
            self.assertEqual(service.search('iphone',{'country':'kw'}),[])

    def test_database_failure_is_optional_to_search(self):
        service=social.Service(self.cfg)
        with patch.object(service.store,'search',side_effect=sqlite3.OperationalError('locked')):
            self.assertEqual(service.search('iphone',{'country':'kw'}),[])

    def test_admin_status_auth_and_media_routes(self):
        app=FastAPI()
        with patch.dict(os.environ,self.env,clear=True):service=social.install(app)
        img=io.BytesIO();Image.new('RGB',(4,4),'red').save(img,'JPEG')
        asset=service.store.put_media(img.getvalue(),self.now)
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/social/status').status_code,401)
            status=client.get('/api/social/status',headers={'Authorization':'Bearer test-admin'})
            self.assertEqual(status.status_code,200)
            self.assertFalse(status.json()['worker_running'])
            response=client.get('/api/social/media/'+asset+'.jpg')
            self.assertEqual(response.content,img.getvalue())
            self.assertEqual(client.get('/api/social/media/no.jpg').status_code,404)


class AppIntegrationTests(SocialTests):
    """Run the actual application with synthetic social rows and no network."""
    # Do not repeat the base test class's suite.
    def run(self, result=None):
        return super().run(result)

    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        env={'CACHE_DB_PATH':cls.temp.name+'/cache.db', 'FINDZIA_SOCIAL_ENABLED':'false'}
        with patch.dict(os.environ,env,clear=True), patch.object(requests.sessions.Session,'request',side_effect=AssertionError('HTTP')):
            cls.appmod=importlib.import_module('main')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        super().setUp()
        self.service=social.Service(self.cfg)
        self.seed()
        self.patch=patch.object(self.appmod,'_SOCIAL',self.service)
        self.patch.start();self.addCleanup(self.patch.stop)

    def test_app_social_price_is_accepted_but_not_checkout_verified(self):
        row=self.service.search('iphone 16',{'country':'kw'})[0]
        self.assertTrue(self.appmod._web_confirmable_price(row))
        self.assertFalse(self.appmod._web_price_page_verified(row))
        self.assertTrue(self.appmod._market_offer_allowed(row,{'country':'kw'}))
        self.assertFalse(self.appmod._market_offer_allowed(row,{'country':'sa'}))
        self.assertTrue(self.appmod.is_lens_product_url(row['url'],row))
        self.assertFalse(self.appmod.is_lens_product_url(row['url']))
        card=self.appmod._web_card_fields(row)
        self.assertEqual(card['price'],row['price'])
        self.assertFalse(card['best_price_eligible'])
        self.assertNotIn('merchant_rating_token',card)

    def test_app_social_carousel_ids_are_distinct(self):
        a='https://www.instagram.com/p/ABC/#findzia-'+'a'*32
        b='https://www.instagram.com/p/ABC/#findzia-'+'b'*32
        self.assertNotEqual(self.appmod._web_price_url_key(a),self.appmod._web_price_url_key(b))

    def test_app_merge_and_strict_text_model(self):
        rows=self.appmod._fz_social_merge([], 'iphone 16', {'country':'kw'}, 'en')
        self.assertEqual(len(rows),1)
        self.assertEqual(len(self.appmod._fz_social_merge(rows, 'iphone 16', {'country':'kw'}, 'en')),1)
        self.assertEqual(self.appmod._fz_social_merge([], 'iphone 17', {'country':'kw'}, 'en'),[])

    def test_app_preferred_text_can_return_social_without_external_results(self):
        app=self.appmod
        with patch.object(app,'_web_preferred_text_specs',return_value=[]), \
             patch.object(app,'_market_query_warm',return_value=None), \
             patch.object(requests.sessions.Session,'request',side_effect=AssertionError('HTTP')):
            result=app._web_preferred_text_search('iphone 16','kw','en',deadline_seconds=.2)
        self.assertTrue(any(r.get('social_id') for r in result.get('results',[])))
        self.assertEqual(result['retrieval_calls'],0)

    def test_app_image_candidates_still_require_visual_proof(self):
        app=self.appmod;row=self.service.search('iphone 16',{'country':'kw'})[0]
        image=io.BytesIO();Image.new('RGB',(128,128),'blue').save(image,'JPEG')
        import base64
        payload={'ok':True,'type':'results','query':'iphone 16','market':app._web_market('kw'),'results':[row],
                 '_reference_image_b64':base64.b64encode(image.getvalue()).decode(), '_reference_image_mime':'image/jpeg'}
        with patch.object(requests.sessions.Session,'request',side_effect=AssertionError('HTTP')):
            result=app._web_attach_captured_result_sections(payload,'en',allow_ai=False)
        self.assertTrue(any(r.get('social_id') for r in result.get('captured_results',[])))
        self.assertFalse(any(r.get('match_type')=='exact' for r in result.get('results',[])))

    def test_app_visual_evidence_reads_local_image_not_instagram(self):
        app=self.appmod;post=self.post()
        image=io.BytesIO();Image.new('RGB',(128,128),'blue').save(image,'JPEG')
        asset=self.store.put_media(image.getvalue(),self.now)
        offers=social.normalize_offers(self.extraction,post,self.source,[asset],self.cfg.base,self.now)
        self.store.save_offers(post,offers,self.now)
        row=self.service.search('iphone',{'country':'kw'})[0]
        with patch.object(requests.sessions.Session,'request',side_effect=AssertionError('HTTP')):
            evidence=app._web_visual_candidate_inline(row)
        self.assertIsNotNone(evidence)

    def test_app_live_prices_do_not_fetch_instagram_or_launch_rescue(self):
        row=self.service.search('iphone 16',{'country':'kw'})[0]
        async def exercise():
            async def source():
                yield self.appmod._web_stream_event({'event':'snapshot','results':[row]})
                yield self.appmod._web_stream_event({'event':'done'})
            return [json.loads(r) async for r in self.appmod._web_with_live_prices(source(),'en','kw',max_seconds=1)]
        with patch.object(requests.sessions.Session,'request',side_effect=AssertionError('HTTP')), \
             patch.object(self.appmod,'_web_live_page_price',side_effect=AssertionError('price fetch')):
            events=asyncio.run(exercise())
        rows=[r for e in events for r in e.get('results',[])]+[e['item'] for e in events if 'item' in e]
        self.assertTrue(any(r.get('price')=='249.900 KWD' for r in rows))
        self.assertEqual(events[-1]['event'],'done')


def load_tests(loader, tests, pattern):
    suite=loader.loadTestsFromTestCase(SocialTests)
    for name in AppIntegrationTests.__dict__:
        if name.startswith('test_app_'):
            suite.addTest(AppIntegrationTests(name))
    return suite


if __name__ == '__main__':
    unittest.main(verbosity=2)
